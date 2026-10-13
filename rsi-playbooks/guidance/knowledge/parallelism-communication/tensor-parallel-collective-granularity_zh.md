<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 按实际粒度选择张量并行通信

[English](tensor-parallel-collective-granularity.md) | 简体中文

## 问题与现状

张量并行 TP 通过切分权重容纳或加速模型，却也在层内引入反复同步。小 decode 消息可能受延迟限制，大 prefill 消息可能受带宽限制。增加 TP 会缩小本地矩阵乘法，也可能增加通信占比。

vLLM 已有 custom all-reduce、all-gather、reduce-scatter 及其他通信路径。核对的源码包含 MNNVL all-gather/reduce-scatter 和低 SM multimem reduce-scatter。不能再笼统说所有 custom collective 只支持单节点，但这也不意味着旧 IPC all-reduce 成了通用 RDMA 实现。研究问题是怎样把实际消息形状和拓扑匹配到已有路径。

## 执行机制

列并行投影计算不同输出特征片段；后续行并行投影计算不同输入特征片段产生的部分和。若下一阶段需要完整复制输出，各 rank 通过 all-reduce 相加。若消费者可以保留 token 分片，则 reduce-scatter 只产生本 rank 片段，在之后需要完整行的位置再 all-gather。这改变了阶段间张量职责，不能只替换通信而不修改消费者。

`T` 个 token、hidden 宽度 `H`、元素字节数 `s`，一个完整激活大小为 `B=T*H*s`。`p` 个 rank 的理想 ring all-reduce，每 rank 流量约为 `2*(p-1)/p*B`。这是带宽模型，不是延迟预测；特别是 `T=1` 时，启动、同步、拓扑和协议更重要。

核对的 `CustomAllreduce` 检查 dtype、字节对齐、连续性、进程组大小和 peer 连通性。旧 custom all-reduce 的选择器拒绝超过八个 rank，虽然外围对象为了其他通信支持更多大小。eager 路径会复制到注册缓冲区，图执行可使用已注册地址，因此图与 eager 对比同时改变通信准备和 CPU 启动成本。

MNNVL reduce-scatter 按架构、大小和 multicast 存储选择 Lamport、multimem 或其他通信器。普通多节点 InfiniBand 集群不等于 MNNVL 域。部分路径在 batch-invariant 模式下刻意不随形状切换，因为不同算法可能产生不同数值行为。

## 适用条件与取舍

比较时固定模型精度与归约方式。FP16/BF16、FP32 输入以及量化 GEMM 输出，不意味着累加契约相同。更多 rank 能增加权重容量，却也增加启动与协调开销。后端适用条件不同，可能在 token 或字节阈值产生性能断点。

尽可能让频繁 TP 通信留在高速互联内；PP 可以跨较慢边界，但代价换成了流水线依赖与气泡。最大 TP 不一定适合单请求。

把 collective 合成大 bucket，只适用于独立就绪的操作。两个归约之间若有依赖的非线性层，不能直接合并。更大的 bucket 也会延迟首个消费者，并要求缓冲区持续有效到通信完成。

## 实验与服务验证

重放真实模型通信形状，覆盖单 token decode、推测验证和分块 prefill。在有意义的条件下固定总 GPU 预算扫描 TP，记录真正执行的核函数和网络路径，分别比较图注册与 eager。孤立通信测量用于定位阈值，完整层测量用于判断与周围 GEMM 的综合影响。

微基准改善而层时间不变时，检查启动准备、同步位置和计算干扰。形状边界上出现延迟跳变时，先确认后端选择，再归因模型计算。加入 rank 启动不齐，不要用同步把服务真实偏斜消除。

完整服务比较 TP/PP 配置时保持工作负载与质量检查一致，记录并发一 TPOT、长输入 TTFT、持续吞吐、客户端尾延迟及 KV 容量。
## 依据与剩余问题

核对日期：2026-10-14。vLLM [6849ca69 的 custom collective 实现](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/distributed/device_communicators/custom_all_reduce.py)及[并行部署文档](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/serving/parallelism_scaling.md)。剩余工作是目标形状和拓扑测量。跨节点调整前参见[流水线气泡](pipeline-microbatch-bubbles_zh.md)。
