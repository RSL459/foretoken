<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Warp 分工的加载、计算与写回流水

[English](warp-specialized-pipelines.md) | 简体中文

当一个内核无法同时有效利用数据搬运、矩阵计算和输出阶段时，可以研究 warp specialization：让不同 warp 承担不同职责。

## 分的是职责，而不只是数据

普通并行分解让不同 warp 处理同一计算的不同元素。Warp specialization 则让一组加载输入、一组发出矩阵指令，另一组转换并写回结果，通过共享内存和 barrier 交接。

Triton Gluon 与 CUTLASS 已有这些能力。它们可作为新负载流水设计的基础，不是应对所有模型统一开启的新优化。当前 Gluon 的逐元素示例针对 Hopper 及更新设备，使用 `tcgen05` 的矩阵示例针对 Blackwell；跨设备移植需重新选择指令与同步方式。

## 一轮流水怎样推进

以三个输入槽位为例。加载分区先等槽位零为空，声明预期字节数，发出异步加载。计算分区等槽位零就绪后消费数据，用完再标记为空；此时生产者可以继续准备槽位一和二。独立的 epilogue 等待累加器完成，把结果转换后放进共享内存，启动写回。

Barrier 的 phase 区分同一槽位的多次使用，上一轮的就绪不能错误满足下一轮等待。教程还在普通共享内存访问与 TMA 操作之间使用异步代理 fence；线程间 barrier 不能替代这类访存顺序约束。

若依赖和资源允许充分交叠，稳态每块时间的下界近似为 `max(加载, 计算, 写回)`。启动、排空和同步不在这个简化式内。很小的解码矩阵可能还没有形成稳态，固定成本就已主导总时长。

## 资源分配也是算法的一部分

加载与写回分区通常需要较少寄存器，但增加的 warp 和总寄存器占用仍会降低驻留度。双缓冲累加器可提升交叠，也会增加同时存活的状态。把 epilogue 拆成更小的输出片段，可以降低共享内存需求，却会增加部分操作次数。

因此，即使时间线上交叠更多，额外生产者 warp 仍可能让内核变慢。应比较关键路径与输出速度，而不是同时运行的操作数量。还应与 collective 共同执行，观察是否争用 SM、带宽或共享内存。

继续设计的空间包括职责分配、缓冲深度、累加器归属与输出粒度，均需适配真实层形状。[持久化调度](persistent-tile-scheduling_zh.md)讨论每个执行单元连续领取哪些输出块，本篇讨论单元内部怎样分工。

## 能区分原因的实验

保持算术和分块尺寸不变，分别改变缓冲深度、warp 分配或输出子块大小。输入覆盖小解码、中等批量和大预填充形状，观察寄存器、spill、共享内存、驻留度和完整内核时长。数值比较应包含尾块和未填满的缓冲区，错误 phase 或 mask 往往在这些条件下暴露。

再使用真实上游和下游张量接回模型，检查额外转换或重排是否抵消收益。最后用无剖析的服务运行比较延迟与吞吐，trace 用于解释流水，不代替速度测量。

## 来源与实现状态

核对日期：2026-10-14。相关机制已经存在于上游。

- [Gluon warp specialization 教程](https://triton-lang.org/main/getting-started/tutorials/gluon/warp-specialization.html)：barrier phase、代理 fence 和 epilogue 分片。
- [固定版本实现](https://github.com/triton-lang/triton/blob/4ee1a827440d453ca276ded4219190d5e7346b8b/python/tutorials/gluon/08-warp-specialization.py)。
- [CUTLASS GEMM 结构](https://github.com/NVIDIA/cutlass/blob/main/media/docs/cpp/efficient_gemm.md)：区分 Hopper cooperative、ping-pong 与 Blackwell 的不同分工。
