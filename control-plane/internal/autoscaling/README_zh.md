# 开发自动扩缩容算法

[English](README.md) | 简体中文

自动扩缩容算法根据负载建议一个 Pool 所需的完整模型副本数。配置已有算法请参阅[自动扩缩容指南](../../../docs/autoscaling_zh.md)。

## 新增副本数建议算法

可以从[队列算法](algorithm/decision/queue.go)开始：它根据等待请求数计算副本建议，并在队列已空、但请求仍活跃时保持容量。建议算法实现 `core.DecisionAlgorithm`：

```go
type DecisionAlgorithm interface {
    Name() string
    RecommendReplicas(core.ScalingSnapshot) (core.ReplicaRecommendation, error)
}
```

使用传入的观测计算副本数，并返回说明结果的原因和消息，供服务状态展示。每份观测对应一个 Pool；编码、预填充和解码 Pool 分别评估。副本数指完整 ModelGroup 的数量，不是单个 Pod 或引擎 rank 的数量。

将实现及其构造函数描述加入[建议算法注册表](algorithm/decision/registry.go)。构造函数接收用户选择的 `parameters` JSON 对象，在这里设置默认值，用 `core.DecodeParameters` 显式解析支持的字段，并校验算法参数。

重新构建并部署控制器后，通过 `ModelService.spec.autoscaling.decision.algorithm` 选择注册的名称。算法随控制器编译发布。

## 调整评估时机或扩缩步幅

大多数建议算法可以直接配合现有的 `periodic` 触发器和 `step` 调整算法。需要改变这些行为时，再扩展相应阶段：

- 触发器实现 `core.TriggerAlgorithm`，判断观测是否足以评估，并通过 `PollingInterval()` 提供控制器的调度间隔。参考 [periodic](algorithm/trigger/periodic.go)，将描述加入[触发器注册表](algorithm/trigger/registry.go)。
- 调整算法实现 `core.AdjustmentAlgorithm`，把建议转换为上下限内的容量，可按需加入稳定窗口或变化速率限制。参考 [step](algorithm/adjustment/step.go)，将描述加入[调整算法注册表](algorithm/adjustment/registry.go)。其构造函数还接收控制器持有的建议历史。

算法只根据输入计算结果。ModelService 控制器负责采集观测、安排评估、应用容量和发布状态，这些操作不放入算法。

## 验证扩缩结果

在[服务状态](../../../docs/autoscaling_zh.md#查看容量)中比较建议副本数、调整后的副本数和实际应用副本数。建议不一定立即应用：观测缺失、过期或不完整时，暂停按负载扩缩；自动扩缩也会在副本转换期间保持容量。即使观测不可用或副本正在转换，最小和最大副本数的硬限制仍然生效。

`step` 的历史仅保存在当前控制器进程中；控制器重启或 leader 切换后，稳定窗口从新的历史开始计算。

修改算法后运行控制面验证：

```bash
make -C control-plane verify
```

随后用模型工作负载观察容量变化，并确认请求成功。[多模型示例](../../../examples/multi-model-quickstart/README_zh.md)提供了可运行的自动扩缩容部署。
