<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 关键路径上的 collective

[English](collective-critical-path.md) | 简体中文

TP、EP 可能将瓶颈从 GEMM 转移到通信。孤立 all-reduce 最快的配置不一定最适合服务：collective 占用设备资源、要求 rank 顺序，也可能与本来希望重叠的计算争用资源。

## 消息大小决定适合的算法

粗略模型为 `T = α × steps + bytes/β`，其中 α 为每步延迟，β 为有效带宽。ring all-reduce 每 rank 流量约为 payload 的 `2(p−1)/p` 倍，但步骤数随 rank 数 p 增长。小 decode 消息可能由延迟主导，大 prefill 更看带宽和 channel 利用率。

BF16、hidden width 4096 的一个 token 为 8192 byte，1024 token 为 8 MiB。这只是示例 payload，不代表每层都调用一次该形状 collective。SP、融合投影和路由会改变大小及次数。为大消息增加 channel，可能在小消息下增加开销或占用过多执行资源。

完整关键路径还包含打包、dispatch、GEMM、combine 和等待最慢 rank。若计算通信确实并行且没有明显互相减速，可近似：

```text
T_stage ≈ max(T_compute, T_comm) + T_unoverlapped。
```

把通信发到另一 stream，并不能证明实现了这种 overlap。不均匀专家 token 可能让其他 rank 已完成通信，最慢 rank 仍在计算。

## 类似接口背后是不同实现

NCCL、RCCL、MCCL 接口相近，但设备 kernel、拓扑发现、传输和图语义不同。当前 RCCL 开发在合并仓库 `rocm-systems/projects/rccl`，历史仓库不代表所有当前修复。AMD vLLM 指南已说明 Quick Reduce、ROCm 的 all-gather/reduce-scatter 专家通信及拓扑约束；其中 channel 建议是特定负载指导，不是其他通信库的默认值。

已核对的 MetaX communicator 安装 backend-specific all-to-all manager，并让 MACA all-gather 走基础 process-group 路径。优化要保留实际 communicator 与张量搬运，不应随意换成看起来更快、顺序却不同的直接 wrapper。同一 rank 集合可能有多个 communicator，它们的计数空间不能混用。

量化 collective 又是独立选择。减少字节可能改善带宽瓶颈，但增加量化计算和数值误差。AMD 指南描述了 Quick Reduce 的低位模式；支持的归约形状与可接受的量化误差决定其适用范围。

## 剩余空间与测量

有价值的工作包括按实际消息分布选择受支持算法、减少布局 copy、找到可重叠部分，以及平衡计算通信资源。BF16/FP16 payload、低位归约、TP collective、EP dispatch/combine 要分开分析。

先用通信库现有 benchmark 测真实 rank 数和消息大小，再加入前后模型阶段，保留实际 stream 和 communicator。分别测通信、计算和 overlap，记录设备完成、rank 不均衡、打包流量及输出误差。孤立带宽改善却让 GEMM 变慢，是阶段层面的负收益。

比较低并发与目标混合流量，观察消息大小和 rank 不均衡如何变化。当最慢 rank 仍主导时，更快通信可能只改善容量，延迟保持不变。

## 来源

核对日期：2026-10-14；源码快照见下方链接。

- [当前 ROCm systems 源码](https://github.com/ROCm/rocm-systems/tree/f1b316f12c75430787032e99405834f59a026ae1/projects/rccl)。
- [AMD 通信与 Quick Reduce 指南](https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/optimization/vllm-v1-optimization.html)。
- [MetaX communicator 与 all-to-all 选择](https://github.com/MetaX-MACA/vLLM-metax/blob/cec91763dbe968fe4478fc066f57ecf5877c3965/vllm_metax/distributed/device_communicators/cuda_communicator.py)。
- [NCCL 图与 rank 参与契约](https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/usage/cudagraph.html)。

[异构执行](README_zh.md) · [并行与通信](../parallelism-communication/README_zh.md) · [知识索引](../README_zh.md)
