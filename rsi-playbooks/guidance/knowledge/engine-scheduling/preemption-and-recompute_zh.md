<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# KV 压力、抢占与重算

[English](preemption-and-recompute.md) | 简体中文

请求刚被接纳时能够放进 KV cache，随着输出增长却可能耗尽容量。反复驱逐和重算会把有用推理变成恢复工作。调度需要保持运行集合可执行，同时避免为所有假想的未来输出保留过多内存、让 GPU 空闲。

## 当前失败路径

已核查的 vLLM V1 在生成调度结果时调用 `kv_cache_manager.allocate_slots`。分配失败后选择运行中的 victim：priority 策略取最大的 `(priority, arrival_time)`，其他策略取运行列表尾部。实际执行抢占前，还要确认块确实可释放。In-flight 执行和延后释放会影响结果，逻辑取消不等于所有块立即可用。

`_preempt_request` 释放 KV 和编码器状态，重置已计算 token 进度，清理推测 token，标记 PREEMPTED，并把请求放回等待队列。若 victim 已进入本轮调度，还需归还对应预算。恢复时要为保留的请求历史重建缺失状态；prefix caching 可能复用部分块，因此重置进度并不意味着历史 token 必然全部重算。

这些都是已有功能。vLLM 官方优化指南建议观察抢占次数，降低并发压力或增加 KV 空间，并明确 V1 默认采用重算，而不是默认 CPU swapping。

## 为什么初始可放入还不够

假设两个请求分别有 8K 输入，预计生成 1K 输出，起初可能都能放入。若实际各生成 8K，合计 KV footprint 接近翻倍，另需考虑块取整和共享。普通 dense attention 模型可粗略估算：

`KV_bytes ≈ resident_tokens × 2 × layers × KV_heads × head_dim × element_bytes`。

真正决策必须使用引擎实际的逐 rank 布局。Tensor parallelism、MLA、混合模型、共享前缀和 allocation group 都会改变这个估计；已计算前缀与未来输出的共享机会也不同。

SOLA 的 peak-memory prediction 在执行前检查新增请求对未来内存的影响，其简化调度算法明确排除了 swapping 和 preemption，优先形成可执行工作量。SCORPIO 结合输出长度预测和延迟准入，指出了同样的不确定性：即使当前集合可放入，过于乐观的长度预测仍会让未来集合超出容量。

只看当前 footprint 与为每个请求预留最大输出是两个极端：前者容易重复恢复，后者在多数输出很短时浪费内存。值得优化的是预测误差的成本，以及误差显现时如何调整选择，而不只是“有没有一个长度预测器”。

## 职责与设计空间

只有引擎知道块是否可回收，能按调度状态选择 victim，并正确恢复执行。Foretoken 请求层可根据观测减少向高压实例发送工作，也能限制入口并发；降低路由并发并不会立即释放已经运行的 KV。集群编排在更慢时间尺度提供副本或不同并行布局。

候选策略可在运行集合选择中考虑预计剩余输出、已完成计算、priority 与 deadline 余量。取舍很具体：驱逐大而旧的请求能回收很多内存，却可能毁掉昂贵进度；驱逐短请求可能同时伤害更多 deadline。现有证据不能证明某篇论文的预测器或 victim 规则普遍最优，也不能据此声称所有当前引擎都缺少它。

## 暴露 thrashing 的实验

保持 prompt 分布不变，只改变输出长尾：多数短响应、少数长响应，以及多个长输出同时出现的突发。固定输出上限、采样、KV 容量与 offered load，比较当前选择和 memory-aware 候选，再加入偏向短输出的预测误差。

记录原始到达数、同时满足 TTFT/TPOT 的完成数、每次完成对应的抢占数、重算 token 数、恢复占用的 GPU 工作、KV 占用和每个 victim 的恢复时间。除平均 TPOT 外还需记录 p99 token 间隔；长时间暂停后快速生成，可能被平均值掩盖。逐类别完成率可防止策略靠反复挤掉同一租户来提高总 goodput。

改变恢复机制前，先检查 token 预算和活跃序列上限。如果缩小运行集合能以接近的 goodput 消除抢占，这种直接控制比新增驱逐实现更值得保留。
## 来源

核查日期：2026-10-14。

- [vLLM scheduler，commit 6849ca69](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/v1/core/sched/scheduler.py)：分配、`_preempt_request`、victim 选择与延后释放约束。
- [vLLM 优化指南](https://docs.vllm.ai/en/latest/configuration/optimization/)：抢占信号与现有操作选项。
- [SOLA，MLSys 2025，§5.1](https://proceedings.mlsys.org/paper_files/paper/2025/file/bc82dbfbfa43232be85b8d9838f49c3e-Paper-Conference.pdf)：批次接纳时检查未来峰值内存。
- [SCORPIO，arXiv 2505.23022v2，2026-08-26](https://arxiv.org/html/2505.23022v2)：异构目标下依赖预测的准入。
