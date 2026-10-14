<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 按实际负载分桶捕获图，减少启动开销

[English](reduce-launch-overhead-with-workload-aware-graph-bucketing.md) | 简体中文

## 图覆盖率取决于负载

CUDA Graph 用较少的主机提交重放已记录的设备执行，但仍会完成记录中的工作，并要求形状、地址与操作行为相容。服务通常预先捕获一组批次配置，再把请求对应的执行分派到兼容的图。

vLLM v0.31.0 的 dispatcher 分别保存 FULL 和 PIECEWISE key，把 token 数补齐到捕获尺寸，并按需要包含请求几何和 LoRA 状态。运行时先尝试 FULL，再尝试 PIECEWISE，否则选择 NONE。推测解码的 uniform batch 可以每请求包含多个 query token，因此 token 总数并不足以判断图是否兼容。

图覆盖率和执行成本取决于真实批次分布、attention 后端、混合层及活跃 adapter。

## Padding 与捕获成本的取舍

若一个批次有 17 个 token 位置，下一个捕获尺寸是 32，那么即使补齐位置不产生用户输出，仍可能执行相当一部分计算。增加更小的桶可以减少浪费，却增加捕获时间和可能的内存消耗；eager 避开 padding，但主机启动更多。

可用实际观测分布下的 `补齐后执行成本 + 分派／启动成本` 理解稳态目标，另外记录启动与捕获内存。这里的分布是引擎实际执行步，不只是客户端并发数；混合预填充／解码、推测长度与 LoRA 组合都会改变它。

FULL 捕获完整的兼容执行，PIECEWISE 只捕获其中支持的片段。引用版本的 dispatcher 会放宽 PIECEWISE key 中请求数和 uniform 字段，但 FULL 保留后端元数据所需的几何。若未证明实际操作适用于新形状，就扩大 key 的匹配范围，可能重放错误执行。

## 不止是增加桶

先查清 eager 的原因：超过捕获上限、不支持的 attention 操作，还是不同 adapter 配置。增加 token 桶不能解决后端不支持 capture；反过来，使一个操作可捕获，可能不增加大量桶就提高覆盖率。

全图编译 pass 也可能与分段切分冲突，因此编译和图模式要共同考虑。混合模型受参与组件共同约束。应选择少量与负载相符的兼容配置，而不是无差别扩大捕获集合。

图内存还会减少 KV 可用空间。启动更快的方案，可能因更多抢占或更低并发容量抵消收益；这需要回到服务负载测量。

## 实验方式

采集真实 step 的 token 数、请求数、decode uniformity、adapter 情况、选中模式与补齐尺寸。在相同到达流量与输出条件下比较桶集合，分别看启动／捕获时间、稳态 step、graph 内存、KV 容量和端到端尾延迟。

修改后端时，对同样批次几何比较 eager 与 replay，覆盖适用的混合流量和推测解码。连续多步检查输出及状态，再判断服务收益是否来自图覆盖率提高。

## 参考

- [vLLM v0.31.0 CUDA Graph 设计](https://docs.vllm.ai/en/v0.31.0/design/cuda_graphs/)：模式与后端能力边界。
- [固定 dispatcher 实现](https://github.com/vllm-project/vllm/blob/db9527a46873454610df6dbedf79a36d6bf1a7f6/vllm/v1/cudagraph_dispatcher.py)：padding、LoRA case、注册 key 与回退顺序。
- [PyTorch v2.14 CUDA Graph Trees](https://github.com/pytorch/pytorch/blob/v2.14.0/docs/source/user_guide/torch_compiler/torch.compiler_cudagraph_trees.md)：按形状记录及内存生命周期约束。
