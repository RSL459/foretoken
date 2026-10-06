<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 告警参考

[English](alerts.md) | 简体中文

为前端或模型服务选择告警，填写所需阈值，再根据通知定位受影响的服务或设备。

## 选择告警

| 规则 | 配置在哪类服务 | 触发条件 |
| --- | --- | --- |
| [ForetokenMetricsTargetDown](#foretokenmetricstargetdown) | 前端或模型服务 | 指标端点连续 1 分钟无法抓取。 |
| [ForetokenFrontendHTTPResponseStart5xxRatioHigh](#foretokenfrontendhttpresponsestart5xxratiohigh) | 前端服务 | 5 分钟窗口内，每秒至少 0.1 次 HTTP 响应开始时，5xx 比例连续 2 分钟超过 5%。 |
| [ForetokenAdmissionCapacityRejectionRatioHigh](#foretokenadmissioncapacityrejectionratiohigh) | 前端服务 | 准入容量拒绝比例超过配置阈值。 |
| [ForetokenAdmissionTimeoutRatioHigh](#foretokenadmissiontimeoutratiohigh) | 前端服务 | 准入超时比例超过配置阈值。 |
| [ForetokenAdmissionAdmittedQueueP95High](#foretokenadmissionadmittedqueuep95high) | 前端服务 | 排队后获准请求的等待 p95 超过配置时长。 |
| [ForetokenAdmissionTelemetryMissing](#foretokenadmissiontelemetrymissing) | 前端服务 | 抓取成功，但必要准入指标连续缺失 5 分钟。 |
| [ForetokenNVIDIAGPUTemperatureHigh](#foretokennvidiagputemperaturehigh) | 模型服务 | NVIDIA GPU 温度连续 2 分钟达到阈值，默认 85°C。 |
| [ForetokenNVIDIAGPUPowerUsageHigh](#foretokennvidiagpupowerusagehigh) | 模型服务 | NVIDIA GPU 功耗连续 5 分钟达到配置阈值。 |

## 启用与配置

在服务的 `spec` 下添加需要的规则，例如：

```yaml
observability:
  alerts:
    rules:
      - ForetokenMetricsTargetDown
```

重新部署服务配置后生效。移除规则或设为 `rules: []` 即可关闭。完整可运行配置见[服务可观测性示例](../../examples/observability/README_zh.md)。

需要阈值的规则，将参数写在 `observability.alerts.thresholds` 下：

| 规则 | `thresholds` 下的配置字段 |
| --- | --- |
| 容量拒绝 | `admission.capacityRejectionRatio`、`admission.minResultRate` |
| 准入超时 | `admission.timeoutRatio`、`admission.minResultRate` |
| 获准排队 p95 | `admission.admittedQueueP95Seconds`、`admission.minQueuedAdmissionRate` |
| GPU 温度 | 可选 `nvidiaTemperatureCelsius`，默认 `85` |
| GPU 功耗 | 必填正数 `nvidiaPowerWatts` |

准入比例以对应阶段已结束的调用为分母，取值 0 至 1。排队时长阈值使用秒，最小速率使用调用次数/秒；排队规则的最小速率只计排队后获准的调用。

`thresholds.admission` 下还可选配：`scope` 默认 `service`，可设为 `pod`；计算窗口 `window` 默认 `1m`，触发前持续时间 `for` 默认 `5m`。时长支持整数秒、分钟或小时。

接收通知请配置 [Lark](../integrations/lark/README_zh.md)、[Slack](../integrations/slack/README_zh.md) 或[钉钉](../integrations/dingtalk/README_zh.md)。已选择的规则未出现时，查看服务的 `AlertsReady` 状态。

## 收到告警后

在 Grafana 打开 Foretoken 系统概览，选择通知中的命名空间和前端或模型服务。

### ForetokenMetricsTargetDown

查看 Prometheus Targets 中的抓取错误，再检查对应 Pod 和指标端点的网络访问。

### ForetokenFrontendHTTPResponseStart5xxRatioHigh

查看前端状态码趋势和日志。通过“准入”区域定位容量拒绝、超时响应，再检查模型可用性和后端错误。

### ForetokenAdmissionCapacityRejectionRatioHigh

比较各前端 Pod 的流量、占用和配置上限。`intake` 对应 HTTP 驻留名额，`work` 对应工作准入；调整前端限额前，同时查看后端负载。

### ForetokenAdmissionTimeoutRatioHigh

对照队列占用、等待时间、`queueTimeout` 和请求超时。结果分类可区分队列等待到期与获准前请求预算耗尽。

### ForetokenAdmissionAdmittedQueueP95High

结合获准等待曲线、队列占用和模型容量定位延迟，同时查看超时结果，判断是否还有请求等待后未能获准。

### ForetokenAdmissionTelemetryMissing

在准入副本表中定位指标不完整的 Pod，并核对运行版本。升级完成后仍未恢复时，检查监控配置。

### ForetokenNVIDIAGPUTemperatureHigh

按通知中的设备检查温度、散热和当前负载。

### ForetokenNVIDIAGPUPowerUsageHigh

比较设备功耗、当前负载、预期运行范围及配置的告警阈值。
