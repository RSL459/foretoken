<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 通过微批调度平衡流水线并行的延迟与吞吐

[English](balance-pipeline-latency-and-throughput-through-microbatching.md) | 简体中文

## 问题与现状

流水线并行 PP 按层切分，而不是切分每个权重矩阵。它可以跨节点容纳模型，让频繁 TP 通信留在节点内。但 collective 次数少，不保证单请求更快：请求仍需经过全部阶段，下一 token 还依赖上一 token 的采样反馈。

vLLM 已支持 PP、TP/PP 组合和不均匀层切分，官方部署指南建议在缺少高速 NVLink 的系统考虑 PP。DeepEP 主线也有实验性 RDMA-only `PPBuffer`。它们属于不同集成范围的已有设施；更快 send/recv 不会自动提供服务调度器，也不会消除气泡。

## 执行机制

第零阶段接收输入并执行所属层，把中间激活发送到下一阶段，依次推进到最终阶段产生 logits 和采样结果。同一自回归请求继续生成前，下一个 token 及所需调度状态要返回输入侧执行路径。

独立请求或合法 microbatch 可同时占据不同阶段。`P` 个等时阶段、`M` 个独立前向 microbatch、每阶段时间 `t`，理想仅前向流水线时间为 `(M+P-1)*t`，整体阶段利用率为 `M/(M+P-1)`。公式忽略传输、不均衡与服务调度，既不是训练 1F1B 公式，也不是 vLLM 当前执行顺序的性能承诺。

`P=4,M=1` 时，一个 microbatch 顺序经过四阶段；八个独立 microbatch 理想需要十一段阶段时间。这说明填充和排空气泡，不预测持续到达流量下的延迟。增加在途工作能改善吞吐，也可能增加单请求等待。

同一序列的 prefill chunk 有 cache 与 attention 依赖，decode token 依赖先前采样。不能随意当作独立 microbatch，否则会改变模型执行顺序。训练中利用 backward 重叠的调度，不能在没有另一种独立工作来源时直接套到推理。

阶段边界同时负责激活形状与缓存。每阶段保存自己 attention 层的 KV；中间传输可能包含 residual stream 或模型专有张量，不只是通用 hidden vector。移动层会同时改变权重、KV 容量和阶段耗时。

## 适用条件与取舍

层数相同不等于阶段时间相同。embedding、输出投影、不同历史长度的 attention 和 MoE 倾斜都可能制造最慢阶段。不均匀切分可改善平衡，但必须使用目标引擎支持的分区方式，而非随意移动模块。

低并发时 PP 往往首先是容量或拓扑选择；高并发独立请求才能填满阶段。即便 RDMA，小激活传输仍可能受延迟限制；图覆盖与启动偏斜也影响交接。阶段越多，失败和取消的协调范围越大。

引用版本的 DeepEP PP 接口要求 RDMA-only 组、连续 CUDA 张量、32 字节指针与大小对齐，以及预先配置最大张量字节数和在途槽位。实验性接口不意味着可以直接替换引擎现有 PP 通信器。后端通信应留在引擎职责内。

## 实验与服务验证

同一总 GPU 预算下，比较纯 TP、节点内 TP 加跨节点 PP，以及可支持的不均匀 PP 切分。覆盖并发一、足以填充阶段的独立请求、突发到达和混合长度。记录逐阶段计算、传输等待、排队和 KV 余量，找最慢阶段，不只看平均利用率。

吞吐改善但单请求 TPOT 变差，应区分流水线占用与串行遍历；通信变快却服务时间不变，检查阶段不均衡和依赖。模型加载启动与稳态服务分开计时。

验证输出与多轮缓存增长，再测客户端 TTFT、TPOT、成功数、输出长度，以及请求跨阶段时的取消。profiler 与正常测速分开。
## 参考

vLLM [6849ca69 的并行指南](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/serving/parallelism_scaling.md)和 DeepEP [93eb6eb2 README](https://github.com/deepseek-ai/DeepEP/tree/93eb6eb238127e96c6d7a4a625a6dad158348509) 的 PP 接口与条件。剩余工作是目标引擎阶段路径核对、平衡分区及负载相关测量。PP 所替代的通信见[TP 粒度](reduce-tp-synchronization-through-shape-aware-collective-selection_zh.md)。
