<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# NUMA 放置与多 rank 主机竞争

[English](numa-rank-host-pipelines.md) | 简体中文 · [主机与流式输出](README_zh.md) · [推理知识](../README_zh.md)

## 加速器增加，主机工作也会增加

多 rank 副本同时有 API 输入、scheduler 进程、设备 worker、通信推进、tokenizer 线程和输出处理。增加 tensor 或 data parallelism，可能减少每 rank 设备计算，却增加可运行的主机任务。整机 CPU 利用率不高，也可能让负责提交下一次 collective 的核心或容器配额不足。

vLLM 当前优化文档明确为 API、engine core 和 GPU worker 计算物理核心预算，更多 API server 或 data-parallel engine 还需要额外核心。这是部署指导，不是通用利用率阈值，更不是 Foretoken 实测资源默认值。超线程不能按独立物理核心的执行能力计算。

## 配额、亲和性和内存局部性是三种约束

Linux cgroup 的 `cpu.max` 表达每个周期可消耗的 CPU 运行时间。一个允许在 8 个 CPU 上运行、但每 100 ms 只获得 200 ms 运行预算的组，总配额约为 2 核。多个 worker 可提前用完预算，随后被 throttle 到下个周期。因此，周期性 GPU 空隙可以与低整机利用率并存。即使子组配额宽松，上级 cgroup 的限额也可能约束它。

CPU affinity 限定线程在哪里运行，但不预留核心，也不提高配额。反过来，提高配额不会消除一个过度拥挤 affinity set 的竞争。CPU pressure 描述可运行任务的等待，throttling counter 描述配额执行；二者都不能替代逐进程运行队列与调度证据。

NUMA policy 通常在页面缺页分配时决定内存放置。Buffer 分配后再绑定线程，不会自动搬迁既有页面。Worker 靠近 GPU，也可能持续读取另一 socket 分配的元数据，或从远端 pinned buffer 拷贝。执行位置、first-touch 分配和允许的内存节点需要一起考虑。Bind 适合局部化访问；interleave 可能帮助共享带宽型 workload，却增加部分消费者的访问距离。选择取决于谁实际读这些页面。

## 慢主机 rank 会表现成慢通信

设 rank r 进入 collective 的时间为 aᵣ，暂忽略拓扑细节，完成时间不会早于 max(aᵣ) 加上各方到达后仍需的传输工作。早到的 rank 可以在通信区间等待很久，网络带宽却正常。原因可能是 CPU 被换出、元数据构造、同步主机拷贝，也可能是此前设备计算不均。

例如，三个 rank 在 1 ms 到达，一个在 5 ms 到达，传输再花 1 ms。早到 rank 的 collective 区间约为 5 ms，晚到 rank 只有 1 ms。把传输缩短 0.2 ms，并没有消除主导的 4 ms 到达偏斜。实际通信算法和 GPU 执行会使分解更复杂，但这个例子说明为什么必须同时看进入时间和持续时间。

SGLang overlap 工具展示了另一个主机边界：只有某些 attention backend 或验证路径需要 CPU sequence-length mirror 时才更新它。设备侧接力可避免主机同步，backend 特定的元数据需求又可能把同步带回来。CUDA 与其他 backend 不能直接互换，跨硬件结论必须沿实际 adapter 和消费者路径核验。

## 如何分离放置与竞争的影响

固定 batch 形状和设备分配，读取 effective CPU set、配额层级、内存节点与逐 rank runnable 时间。先只改配额，再只改 affinity。周期性空隙仅在增加配额后消失，就不能归因于 NUMA 远端内存；相同配额下独立物理核心有效，则更像运行队列竞争或超线程共享。

局部性实验应比较同节点分配和执行，与刻意远端分配，固定 buffer 大小和传输方向。Warmup 后只改线程位置而不重建 buffer，不能隔离 first touch。Pinned buffer 流量还应与 tokenizer、共享模型元数据访问分开。

多 rank 分析按同一步骤或 collective 身份对齐，比较所有 rank 前面的主机工作、GPU 完成和 collective 进入时间。不能只按独立节点的时间戳对齐。如果主机放置消除了到达偏斜，而最后一方进入后的传输时间稳定，研究重点就是主机流水线。单用户延迟与饱和吞吐仍要分开：预留核心可能改善节奏，也可能减少同节点能承载的副本数。

## 来源与核验

核验日期为 2026-10-14。数值例子用于说明因果，不是硬件测量。

- [vLLM 优化文档](https://docs.vllm.ai/en/latest/configuration/optimization/)：物理核心预算与 busy-loop scheduler 竞争，核验当日读取。
- [Linux cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html)与[NUMA memory policy](https://docs.kernel.org/admin-guide/mm/numa_memory_policy.html)：配额、effective CPU set、pressure、分配与迁移语义，属于动态内核文档。
- [SGLang overlap 工具](https://github.com/sgl-project/sglang/blob/e9400c5a8f3a0d0312a37aecef694f5edfd69341/python/sglang/srt/managers/overlap_utils.py)：设备和 CPU 元数据边界，版本日期为 2026-10-13。
- [Nsight Systems 文档](https://docs.nvidia.com/nsight-systems/UserGuide/index.html)：核验当日读取进程范围、CPU/设备关联、时间归一化与跨节点时钟对齐章节。
- [Foretoken CPU 观测](../../../../benchmarks/docs/metrics_zh.md#cpu-与内存观测)：在 `e6ae3df6` 核实，属于 counter 估算与 trailing window 曲线，不是逐 rank 调度 trace。
