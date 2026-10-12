# 自动扩缩容架构

[English](README.md) | [中文](README_zh.md)

本包将控制器拥有的观测转换为 `ModelPool` 容量。用户通过 `ModelService.spec.autoscaling` 配置自动扩缩容；配置和状态使用方式见[自动扩缩容指南](../../../../docs/autoscaling_zh.md)。

## 职责归属

`ModelService` 控制器负责调度、观测采集、扩缩目标发现、状态发布，以及将容量写入 `ModelPool`。算法保持无副作用：只评估一个完整观测并返回容量建议。

每个扩缩目标对应一个 Pool。E/P/D 服务各有一个 encoder、prefill 和 decode Pool，三个 Pool 分别评估容量；ModelService 控制器仍将它们准备完成的 revision 作为一个完整服务代统一提交。

## 评估流水线

```text
控制器轮询
→ ScalingSnapshot
→ TriggerDecision
→ ReplicaRecommendation
→ ReplicaAdjustment
→ ScalingDecision
→ ModelPool 容量和 ModelService 状态
```

控制器向流水线提供完整、近期的观测。`periodic` 接受这些观测，不拥有时间间隔或重新入队循环。即使缺少观测，Resolver 仍会应用最小和最大副本数硬限制；目标处于转换中时保持容量。

`step` 的稳定窗口使用当前控制器进程保存的近期建议。历史刻意保存在运行时本地，因此重启或 leader 切换不会恢复尚未结束的缩容延迟。

## 扩展边界

内置算法位于 `algorithm/`。Trigger、Decision 和 Adjustment 实现返回领域结果，不读取 Kubernetes 资源、不修改容量，也不调度工作。新增实现只有在它代表当前独立负责的建议策略时才有意义；控制器生命周期行为保留在 `core` 和 ModelService reconciler 中。

每个 Trigger、Decision 和 Adjustment 阶段都拥有自己的编译期 descriptor 列表。新增算法时，在所属阶段添加实现和一个 descriptor；顶层 registry 负责构造选中的 factory，不接受运行时注册。算法各自负责参数默认值和语义校验，`core.DecodeParameters` 只提供共享的字段、类型解析，不把实现结构体直接暴露为配置。

三个阶段都接收可省略的 JSON 参数对象。Adjustment 构造函数还接收控制器持有的建议历史。Trigger 实现提供轮询间隔，控制器负责调度并据此推导观测有效期。容量上下限与生命周期约束仍属于平台职责。

控制器每轮只构造一次流水线。省略触发或调整阶段时，由组装入口选择 periodic 或 step；具体参数的默认值只由实现负责。新增实现需要重新构建并部署控制器，不采用运行时动态插件。

## 验证

修改本包后运行控制面验证：

```bash
make -C control-plane verify
```

## Dynamo 反应式策略边界

复刻参考固定为 NVIDIA Dynamo 提交
[`bea55a595a83a84b76183d44516de05f9ea1b2d0`](https://github.com/ai-dynamo/dynamo/blob/bea55a595a83a84b76183d44516de05f9ea1b2d0/components/src/dynamo/planner/core/load_scaling.py)，
对应 `_prefill_easy_decision`、`_decode_easy_decision`、`_agg_easy_decision`
及其缩容后负载检查。本实现覆盖 easy 反应式策略；基于 profile 的 TTFT/ITL
预测、启动中容量估算和 Dynamo endpoint 管理不属于此决策边界。
Foretoken 通过已有控制器管理资源生命周期。

vLLM 参考固定为源码提交 `1be36283678a9a94fc8fdaad6c95c2896d6b4015`。
通用 `get_scheduler_load` utility 与调度采集钩子位于
`common/scheduler-load.patch`，仅加入固定源码和当前 Python 版本的补丁系列。
第一次 utility 查询启用采集，保留原生异步调度器。被分类为 decode 的 cached
请求计入已计算 token 数；抢占或等待远端 KV 的请求计入排队 decode token；
其余等待请求按完整 token 数计入排队 prefill。已完成请求从最后一轮 decode 样本中排除。

model-server 适配器通过公开 EngineCore utility API 查询全部 DP rank，
发布独立的 version-1 `/v1/internal/scheduler-load` 响应。既有 version-2
telemetry 不变。仅 `dynamo_load` 请求新增观测。控制器验证 rank 覆盖和容量，
将样本归属到选定 serving Group UID，并在 `EngineLoads` 中保留各 rank。
任一采集错误会丢弃整个观测，不以平均值或部分成功 cohort 作为扩缩容依据。

单组全注意力 cache 容量为 `num_blocks * block_size`。混合 cache、多 cache
组和上下文并行需要不同的容量协议，当前返回指标不可用。
已有请求由 Group 排空机制保护，不通过算法中的仅空闲可缩容条件保护。
