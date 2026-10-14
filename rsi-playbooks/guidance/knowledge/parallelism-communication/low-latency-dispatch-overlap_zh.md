<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 低延迟 MoE 通信与有效重叠

[English](low-latency-dispatch-overlap.md) | 简体中文

## 问题与现状

每 rank token 很少时，dispatch 与 combine 可能主导 decode。异步接口本身不会消除 dispatch 到专家 GEMM、combine 到下一层的依赖。有效重叠需要独立工作，或更细粒度的生产完成信息。

DeepEP 主线已是统一 `EPBuffer` 的 V2.5，移除了 V1 API 与 NVSHMEM 依赖。当前 README 明确指出 EP dispatch/combine 使用 SM，不支持零 SM 的 RDMA EP。vLLM 已实现双批重叠 DBO；DeepEP 独立 `antgroup-opt` 分支也有单批重叠 SBO。

## 执行机制

当前主线允许 dispatch 在通信 stream 异步执行，并延后收尾。先启动 dispatch，再做独立计算，到专家需要输入时才等待；等待返回展开输入、路由元数据与 handle。关闭 CPU 同步时，GEMM 必须使用 GPU 接收计数，容量中的无效行不是 token。计算并加权专家结果后启动 combine，继续独立工作，消费结果前等待。主线 combine 对传入结果求和，因此路由权重应在文档指定的计算边界应用。

DBO 把 batch 分为两个 microbatch，以获得独立工作。vLLM 让一个 microbatch 的 dispatch 与另一个的 attention 或专家计算交替，再让一个 combine 与另一个计算重叠。所有 DP rank 必须同意拆分；第二个 microbatch 为空时可能关闭拆分。完整 CUDA Graph 捕获这种顺序后，稳态 replay 不再需要捕获时的 CPU 线程协调。

SBO 改变工作粒度，而不是要求另一个 microbatch。PR #483 引入专家行块完成信号：combine-send 用 acquire 语义等待对应 GEMM 信号达到阈值，随即发送该块，所有相关块完成后发布专家完成状态。这需要 GEMM 生产者配合，普通整核完成事件无法提供提前就绪信息。把所有信号提前填满的测试，只验证消费者，不证明真实计算通信重叠。

## 适用条件与取舍

单个自回归请求每个 decode step 通常只产生一个新目标 token，除非推测或其他执行方式扩展输入。不能默认存在两个有用 microbatch。共享专家可能提供独立计算，但目标模型必须确实有共享专家；SBO 在小批量也可能没有足够 GEMM 时间偿还信号开销。

通信与 GEMM 争用 SM、HBM、共享内存和启动资源，整体时间不能简单写为 `max(comm,compute)`，因为重叠可能同时拉长两者。等待中的通信 block 不能占满生产者所需资源。应测并行执行下的完整层，不是孤立核函数的最短时间。

核对的 V2.5 NVIDIA 路径要求 Hopper 或更新设备、CUDA Toolkit 13.1+、PyTorch 2.10+ 和 NCCL 2.32.3+，节点内使用 NVLink，跨节点使用 RDMA。Dispatch 接受 BF16 或带 scale 的 FP8，combine 输入必须为 BF16。引擎 adapter 和传输表示应匹配这个接口，并计入专家计算前后的转换。V1 实验分支的 API 与依赖不同。

## 区分假设与服务验证

比较串行、没有独立工作的异步、有真实独立工作的异步、符合条件的 DBO，以及兼容分支的 SBO。固定模型、dtype 和拓扑，扫描有效 token、microbatch 平衡程度、专家倾斜和通信 SM 分配。记录 DBO 是否实际开启、图 replay、dispatch 就绪、GEMM 变慢、combine 尾部及最慢 rank 的层耗时。

重叠区间扩大而层时间上升，说明资源争用；并发一时 DBO 没开启，属于适用条件结论，不是实现失败。SBO 要覆盖块完成延迟和不齐，并在复用存储前检查输出。

完整模型核对后，以未加 profiler 的服务 TPOT、TTFT 和持续负载尾延迟判断，保持输出长度与质量，包含 prefill/decode 混合流量，不只测有利的稳态核函数。

## 依据与状态

核对日期：2026-10-14。DeepEP [主线 93eb6eb2](https://github.com/deepseek-ai/DeepEP/tree/93eb6eb238127e96c6d7a4a625a6dad158348509)、vLLM [6849ca69 的 DBO 设计](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/design/dbo.md)，以及 [PR #483](https://github.com/deepseek-ai/DeepEP/pull/483)。#483 于 2025-11-21 合入 `antgroup-opt`，merge `9f2fc4b3`，不能据此认为 V2 主线支持。核对时 [#453](https://github.com/deepseek-ai/DeepEP/pull/453) 仍 open、未合并。剩余研究是目标版本集成、合理资源划分和负载适用性测量。
