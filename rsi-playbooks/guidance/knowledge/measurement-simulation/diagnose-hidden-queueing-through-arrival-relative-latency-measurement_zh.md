<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 诊断被遗漏的排队：按计划到达时间测量延迟

[English](diagnose-hidden-queueing-through-arrival-relative-latency-measurement.md) | 简体中文 · [测量与模拟](README_zh.md) · [推理知识](../README_zh.md)

## 平均长度相同，不代表工作相同

90 个短请求与 10 个长请求，不等价于 100 个平均长度请求。长 prefill 会干扰 decode，长输出长期占用 KV，长请求集中到达还会形成持续积压。输入长度、输出长度、到达时间、共享前缀与会话历史之间的关联，共同决定组批和缓存复用。

只有时间戳和 token 数的 trace 只能保留部分属性。Azure 2024 推理数据集没有 prompt 原文，按长度生成合成文本并不能恢复真实前缀共享、分词成本、工具调用与停止行为。内容数据集回答的是另一类问题。独立组合内容和到达流量可以构造有用负载，但应明确它不是原服务的完整重放。

## 闭环与开环回答不同问题

闭环客户端在请求完成后，可能等待思考时间 Z，再发出下一个请求。C 个持续活跃客户端、平均响应时间 R 的吞吐近似为 `C/(R+Z)`。服务越慢，发起负载就越低。这适合固定数量的交互用户，但可能隐藏外部独立到达流量下的过载。

开环由外部以速率 λ 安排到达。用固定容量 μ 作说明，当 λ 大于 μ 时，积压约以 `λ−μ` 增长。并发上限、连接池或过慢的压测端可能把队列移到服务之前，而不是消除队列。只报告实际发送到完成的延迟，就遗漏这部分等待。

设计划到达为 `tₐ`、实际发送为 `tₛ`、完成为 `t𝒻`，则到达口径延迟为 `t𝒻−tₐ = (tₛ−tₐ)+(t𝒻−tₛ)`。压测端若跟随服务变慢、又忘记原定到达时间，就会出现 coordinated omission，让吃力的服务看起来仍然健康。保留计划时间能暴露遗漏，但不代表压测端真的能维持目标速率。

Foretoken 调度器会在并发限制延迟准入时保留计划 offset，HTTP runner 记录 `send_delay`；trace 运行还有 `replay_delay` 及到达口径 TTFT／延迟。当前 trace 记录的 `open_loop=False`，因此“trace”本身不意味着无限制派发。普通延迟汇总仍使用请求时钟，要另看相对于到达的字段。AIPerf 同样区分请求延迟与从 credit 发放到完成、包含客户端等待的 effective latency。

## 排队会放大服务时间的小变化

M/M/1 的平均响应时间为 `1/(μ−λ)`，前提是泊松到达、独立指数服务时间、单服务者和稳定队列。连续组批、KV 限制和阶段干扰不符合这些假设，不能直接拿它预测引擎；它说明的是敏感性：μ=100、λ=90 请求／秒时为 100 ms，容量降到 95 时变为 200 ms。

即使平均负载低于容量，突发和服务时间波动也可能产生长等待。泊松负载不能替代长度与到达相关的 trace。只保留时间戳却打乱长度，会破坏相关性；平滑到达则改变了排队问题。

## 暴露遗漏队列的实验

对同一请求集合比较固定并发、压测端能承受的外部开环，以及保留计划时间的有上限重放。一起看计划、发送、完成与失败数，发送等待、到达口径延迟和服务端等待。请求时钟延迟平稳而发送等待上涨，说明负载积在上游；两者都上涨，则客户端限制和服务队列均有贡献。

再保留输入／输出长度对，比较原顺序和刻意打乱的对照。若差异集中在突发恢复或缓存命中，原因是相关性而非平均长度。合成前缀共享作为单独变量；比较调度时保持实际输出长度和停止行为，否则服务需求本身就变了。

Little 关系 `L=λW` 可检查同一稳定系统边界内的平均在途数量、到达率与停留时间。不要混用已发送请求的并发与包含发送前等待的延迟，也不要混用仅成功吞吐与全尝试延迟。准入窗口与排空时间分开说明，避免有限窗口只保留已完成请求而隐藏未完成工作。

## 参考

- [Azure 推理数据说明](https://github.com/Azure/AzurePublicDataset/blob/master/AzureLLMInferenceDataset2024.md)：2024 代码／对话 trace 的字段、隐私省略与采集时间。
- [AIPerf effective 与 active 指标](https://github.com/ai-dynamo/aiperf/blob/e1daadd10faa395100384358131d784d6858c5ae/docs/reference/effective-vs-active-metrics.md)：2026-10-12 revision 的 credit 排队、有效延迟与统计总体。
- [Foretoken 调度](../../../../benchmarks/src/benchmarks/runs/scheduling.py)、[HTTP 执行](../../../../benchmarks/src/benchmarks/runs/http.py)和[指标](../../../../benchmarks/docs/metrics_zh.md)：`e6ae3df6` 的计划到达、准入限制、排空及 trace 相对计时。
