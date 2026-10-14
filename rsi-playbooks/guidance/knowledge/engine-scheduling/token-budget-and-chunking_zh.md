<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Token 预算与分块 Prefill

[English](token-budget-and-chunking.md) | 简体中文

Token 预算限制的是引擎一次迭代的工作量，不是服务能接收多少请求。真正需要优化的是：在满足已有流的 token 交付间隔时，一次迭代还能容纳多少 prefill。

## 当前已有机制

vLLM V1 已实现分块 prefill，先安排运行中的工作，再接纳等待请求。官方优化指南说明，它会在条件允许时默认开启。当前调度器还处理 speculative token、编码器预算、混合状态模型的块对齐和 KV 分配。

Sarathi-Serve 解释了这种执行方式为什么有效：访存受限的 decode 可以与计算密集的 prefill 共用一次迭代，小块输入则避免长 prompt 长时间占住设备。SOLA 则根据实际 SLO 压力选择每轮工作量与顺序，而不是固定预算。

## 看一次迭代

假设有 64 个运行请求，每个需要一个普通 decode token；此时到达一个 8,192-token prompt。简化地取每轮 512-token 预算，decode 占 64，剩余 448 可用于 prefill。若运行请求数量不变，该 prompt 至少需要 19 轮。把预算改为 2,048，每轮可处理 1,984 个输入 token，至少五轮完成，但每次混合执行可能更久地阻塞已有流。轮数由 token 计量得出，单轮耗时则需要测量。

实际约束应来自测量得到的延迟曲面：

`iteration_time(decode_population, context_lengths, prefill_tokens) <= delivery_budget`。

其中 delivery_budget 是预留主机调度与响应交付时间后，活跃流的下一 token 仍可等待的剩余时间；各时间量使用相同单位。

相同 token 数不代表相同时间。Attention 成本随已有上下文变化，MoE 专家激活影响权重流量，tensor parallelism 增加通信，推测解码还需要验证额外 token。当前 vLLM 区分调度 token 容量与输入预算，并为 draft slots 预留空间；不能把所有请求都当作只占一个位置。

Sarathi 按尾部 token 间隔目标测量预算，并考虑 GPU tile 大小的整数倍。更小的预算如果选中了低效矩阵形状，反而可能更慢。SOLA 则观察请求延迟、系统内存和拟合出的 prefill/decode 成本，动态调整请求数、token 数与执行顺序，再在引擎内用实际迭代延迟修正模型。延迟曲面需要按模型、权重／缓存 dtype、backend、拓扑和并行配置拟合；kernel 或执行设置变化后重新校准。

## 适用条件与取舍

当新到 prefill 引起 decode 卡顿，而设备仍有计算余量时，这个问题值得研究。大块有利于 prefill 效率和 TTFT，却可能扩大单次 decode 间隔；小块增加调度次数、collective、attention 读取，MoE 还可能重复读取专家权重。[按层分组 prefill](layered-prefill_zh.md)讨论了最后一种问题的不同执行切分。

纯 decode 没有可重新分配的 prefill。高并发 decode 本身也可能用尽延迟预算。前缀命中会改变实际 prefill 工作，因此应扫描未命中的后缀长度，而不是把完整输入长度作为唯一变量。多模态编码器和混合状态模型有额外限制，文本模型上的最优预算不能直接作为通用默认值。

## 职责与实验

引擎负责逐轮 token 选择、chunk 进度、KV 分配与 CUDA Graph 可执行性。Foretoken 请求层负责选实例并计量等待和活跃请求，不生成逐轮 token schedule。集群编排负责副本容量和并行资源布局；比较 token 预算时同时改变副本数，会混淆收益来源。

固定时间戳请求轨迹、输出上限、采样、模型、拓扑与 offered load。覆盖孤立长 prompt、长 prompt 突发和高缓存命中续问，比较多个预算与当前配置。记录 p50/p95/p99 TTFT、p99 token 间隔、TPOT、满足 SLO 的完成请求数/秒、抢占次数和设备内存；结合时间线区分长 kernel、CPU 调度和通信空隙。拒绝和超时必须与完成请求一起报告。

剩余设计空间是能随请求形状变化调整、又不会振荡或依赖过于乐观预测的预算策略。应与每个 workload 下最好的固定预算比较，而不是挑一个差的设置作为对照。

## 来源

核查日期：2026-10-14。代码链接固定到对应版本；官方指南使用其 latest 通道。

- [Sarathi-Serve，arXiv 2403.02310v1](https://arxiv.org/html/2403.02310v1)：混合批次、预算测量与 tile quantization。
- [SOLA，MLSys 2025，§§4–5](https://proceedings.mlsys.org/paper_files/paper/2025/file/bc82dbfbfa43232be85b8d9838f49c3e-Paper-Conference.pdf)：逐轮工作量控制和在线成本修正；论文使用 vLLM 0.4.2 集成。
- [vLLM 官方优化指南](https://docs.vllm.ai/en/latest/configuration/optimization/)：当前分块与抢占建议。
- [vLLM V1 scheduler，commit 6849ca69](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/v1/core/sched/scheduler.py)：`schedule`、token/input 预算与分配约束。
