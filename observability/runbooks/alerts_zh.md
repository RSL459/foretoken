<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Foretoken 告警参考

[English](alerts.md) | 简体中文

在所属服务的 `spec.observability.alerts.rules` 中选择规则。列表为空表示关闭告警，指标仍然保留。Prometheus 需要选中工作负载命名空间及其 `PrometheusRule`；规则未出现时，先查看服务的 `AlertsReady` 状态。

## 配置准入告警

准入告警配置在 `FrontendService` 中，不归属某个模型。例如，在 `spec` 下添加以下配置，监测持续的容量拒绝：

```yaml
observability:
  alerts:
    rules:
      - ForetokenAdmissionCapacityRejectionRatioHigh
    thresholds:
      admission:
        capacityRejectionRatio: 0.05
        minResultRate: 1
```

重新部署服务配置后生效。示例在每秒至少一个准入调用结束时，容忍 5% 的容量拒绝；请按服务实际负载设定阈值。准入告警统一为 warning，只有显式选择的规则才启用。

| `thresholds.admission` 下的字段 | 哪条规则必需 | 含义 |
| --- | --- | --- |
| `capacityRejectionRatio` | 容量拒绝规则 | 容忍的拒绝比例，范围 0 至 1；入口和工作准入分别评估。 |
| `timeoutRatio` | 超时规则 | 工作准入以队列超时或请求预算耗尽结束的比例，范围 0 至 1。 |
| `admittedQueueP95Seconds` | 排队 p95 规则 | 实际排队后获准的调用可容忍的等待 p95，单位为秒。 |
| `minResultRate` | 两条比例规则 | 被评估范围内每秒结束的准入调用数下限。 |
| `minQueuedAdmissionRate` | 排队 p95 规则 | 被评估范围内每秒排队后获准的样本数下限。 |
| `scope` | 业务规则可选 | 默认为服务级 `service`，也可选逐副本 `pod`；只生成所选范围的告警。 |
| `window` | 业务规则可选 | 速率计算窗口，默认 `1m`；抓取间隔较长时应增大窗口。 |
| `for` | 业务规则可选 | 条件连续成立多久后触发，默认 `5m`。 |

业务阈值和最小样本速率没有默认值，只需填写选中规则所需的参数。时长使用整数秒、分钟或小时，例如 `90s` 或 `5m`。较长的窗口可能让已经结束的突发继续超过阈值；`for` 判断的是窗口计算结果持续多久，而非单个请求持续多久。

指标缺失规则无需阈值，始终按抓取目标逐个检查，持续 5 分钟后触发。准入通知按命名空间、前端服务、规则名和阶段分组，保留可用的 Pod 明细。通知接入见 [Lark](../integrations/lark/README_zh.md)、[Slack](../integrations/slack/README_zh.md) 或 [钉钉](../integrations/dingtalk/README_zh.md)。

## 定位告警

打开 Foretoken 系统概览，选择告警中的命名空间和前端服务。结合准入结果和 Pod 明细，区分前端容量、排队等待与请求预算，再关联模型队列、延迟和设备利用率。

### ForetokenAdmissionCapacityRejectionRatioHigh

容量拒绝比例超过配置阈值，且结果速率达到下限并持续指定时间。`intake` 表示 HTTP 请求进入时对驻留名额的即时准入；`work` 表示预处理或生成前的工作准入。两阶段分别以该阶段已结束的调用为分母，包含其他结果类别，不计入内部调用。

调整限额前，先查看前端容量配置和各 Pod 流量是否均衡。容量拒绝表示前端配置的准入限额已达到，不等于 GPU 已饱和。

### ForetokenAdmissionTimeoutRatioHigh

已结束的 HTTP 工作准入调用中，`queue_timeout` 与 `deadline_exceeded` 的合计比例超过阈值。分别查看这两个结果：前者耗尽队列等待期限，后者在完成准入前耗尽请求总预算。读取正文或推理执行期间的超时不计入此规则。

### ForetokenAdmissionAdmittedQueueP95High

获准等待 p95 超过配置的秒数阈值，且排队后获准的样本速率达到下限。只有实际排队并最终获准的调用参与计算；立即获准、超时和取消不参与。结合队列占用、后端容量和单独展示的超时结果定位等待原因。

### ForetokenAdmissionTelemetryMissing

抓取成功，但必要准入指标连续缺失 5 分钟。核对运行版本及各 Pod 的指标覆盖，尤其留意升级期间的差异。每个目标都应发布运行算法信息和 HTTP 入口、工作阶段的基础计数器；concurrency 还应发布资源占用及上限。无流量时不要求存在等待直方图样本。此告警表示指标不完整，不代表推理不可用；抓取失败由 `ForetokenMetricsTargetDown` 告警。

### ForetokenMetricsTargetDown

已发现的前端或 model-server `/metrics` 端点连续 1 分钟无法抓取。查看 Prometheus Targets、Pod 健康状态及抓取器网络访问。恢复抓取或端点退出服务发现时解除；未被发现的端点不在此规则的检测范围内。

### ForetokenFrontendHTTPResponseStart5xxRatioHigh

在 5 分钟计算窗口内，每秒至少 0.1 次 HTTP 响应开始事件时，5xx 比例连续 2 分钟超过 5%。统计的是响应开始，不是推理完成，也不包括 SSE 响应开始后才发生的错误。准入返回的 503/504 仍计入，结合准入结果判断其贡献。

### ForetokenNVIDIAGPUTemperatureHigh

归属到所选 ModelService 的 NVIDIA GPU 连续 2 分钟达到温度阈值。`thresholds.nvidiaTemperatureCelsius` 默认 85°C。按通知中的 Pod 和设备查看温度、散热及负载。

### ForetokenNVIDIAGPUPowerUsageHigh

归属到所选 ModelService 的 NVIDIA GPU 连续 5 分钟达到功耗阈值。选择规则时，必须填写正数 `thresholds.nvidiaPowerWatts`。结合工作负载和设备功耗设置判断是否超出预期运行范围。GPU 规则覆盖该服务拥有的 ModelGroup，不应用于沐曦设备。
