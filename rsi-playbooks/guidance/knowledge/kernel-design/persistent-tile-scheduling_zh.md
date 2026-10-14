<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 持久化矩阵分块调度

[English](persistent-tile-scheduling.md) | 简体中文

高效的矩阵指令不能消除尾部不满一轮的分块、重复准备或缓存复用不足。持久化调度改变输出块的分配方式，并复用准备工作。

## 持久化改变了什么

普通分块 GEMM 为每个输出块启动一个线程块。输出块大小为 `BM × BN` 时，总数为 `ceil(M/BM) × ceil(N/BN)`。持久化内核只启动有限数量的线程块，让每个线程块连续处理多个输出块，复用加载流水与累加器管理。

假设共有 100 个等成本输出块，80 个执行单元同时工作。第一轮结束后，只有 20 个继续做第二块，其余 60 个已经空闲。持久化并不会自动消除这部分尾浪；它改变的是任务分配方式，以及准备、加载、计算和写回如何交叠。更利于缓存的遍历顺序，也可能造成更差的负载平衡。

Triton 当前的 Gluon 教程已实现普通顺序和分组顺序，CUTLASS 也已有 cooperative、ping-pong 等持久化内核。值得研究的是实际推理形状需要什么分块顺序和资源配置，而非重新引入持久化这个概念。

## 跟随一个输出块执行

生产者通过张量内存加速器 TMA，把输入异步加载到共享内存环形缓冲区，并用 barrier 记录预期传输字节数。消费者等数据就绪后执行矩阵计算，用完再释放槽位。沿 K 维累加完成后，epilogue 负责转换与输出；把写回安排到相邻输出块之间，可让上一块的存储与下一块的计算交叠。

Gluon 示例分别采用 Hopper 的 warp-group MMA 和 Blackwell 的 `tcgen05`。前者的累加器占用寄存器，后者使用 tensor memory。输入与输出缓冲区的存活区间决定共享内存能否复用，因此增加流水级数虽然可能隐藏延迟，也可能降低驻留度或迫使内核缩小分块。

## 适用条件与继续研究的方向

解码中的 M 往往很小。如果输出分块总数不足，仅改变遍历顺序无法填满 GPU。沿 K 分片能增加并行工作，但需要保存部分结果并归约。比较持久化、更小分块和 split-K 时，应把归约与输出转换一起计时。

大预填充矩阵更可能受稳态流水和局部性影响。小批专家计算则存在不等长任务，静态分配可能让少数执行单元承担过多工作，而动态分配又有额外调度开销。专家分组的具体问题见 [MoE 执行](../moe-execution/README_zh.md)。

持久化内核还会与通信争用 GPU 执行资源。独立 GEMM 占满所有 SM 时看似最快，但在需要通信重叠的模型中可能反而拉长一次迭代。

## 区分原因的实验

保留真实投影的 M/N/K、stride、dtype 和 epilogue。先固定分块大小，比较普通、持久化和分组调度，再调整分块。观察输出块数、尾浪、共享内存占用，以及包含归约和转换的总时间。分别测试权重已在缓存中的情况和工作集超过缓存的情况。

随后与模型中真实的并行通信共同运行，再接回完整层。如果独立收益消失，应检查资源争用与重叠变化，而不是继续无目标地扩大局部参数扫描。

## 来源与实现状态

核对日期：2026-10-14。以下机制已经存在于上游。

- [Triton Gluon 持久化教程](https://triton-lang.org/main/getting-started/tutorials/gluon/persistence.html)：生产者／消费者计数和缓冲区生命周期。
- [固定版本教程实现](https://github.com/triton-lang/triton/blob/4ee1a827440d453ca276ded4219190d5e7346b8b/python/tutorials/gluon/07-persistence.py)：包含 Hopper 与 Blackwell 路径。
- [CUTLASS 高效 GEMM](https://github.com/NVIDIA/cutlass/blob/main/media/docs/cpp/efficient_gemm.md)：持久化、epilogue 和 split-K；其中 Hopper 的具体分工不能直接套到 Blackwell。
