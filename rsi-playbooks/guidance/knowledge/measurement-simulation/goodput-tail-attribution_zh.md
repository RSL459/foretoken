<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 有效吞吐与尾延迟归因

[English](goodput-tail-attribution.md) | 简体中文 · [测量与模拟](README_zh.md) · [推理知识](../README_zh.md)

## 吞吐增加，有效服务可能反而减少

设配置一每秒完成 100 个请求，其中 60 个满足延迟要求；配置二完成 80 个，其中 76 个达标。第二种吞吐更低，请求有效吞吐却更高。若长输出主导 token 总数，按 token 计算又可能得到不同排序。目标需要明确哪些请求算有效，以及使用什么资源和时间分母。

请求 i 成功且满足全部条件时记 `gᵢ=1`，否则为零。对 N 次尝试跟踪到完成或失败，观察时长为 T，则请求有效吞吐为 `Σgᵢ/T`，token 有效吞吐为 `Σgᵢnᵢ/T`，其中 nᵢ 是输出长度；达标率为 `Σgᵢ/N`。T 从测量开始持续到排空完成，不含 warmup。固定稳态窗口则统计窗口内的完成量，并另报未完成工作。Token 有效吞吐需要达标请求的实际输出计数。失败保留在达标率分母中；比较时保持负载混合比例一致。

## 联合要求不是几个独立分位数

TTFT 达标但最大流式间隔超标的请求，不算联合达标。若 TTFT 和 ITL 各有 95% 达标，联合达标最低可能只有 90%；直接相乘隐含了未经测量的依赖关系。各自的总体分位数也无法指出哪些请求同时违反条件。

请求平均 TPOT 会隐藏卡顿。一次 500 ms 停顿加许多快速 chunk，可能平均 TPOT 合格，却最大间隔不合格。反过来，一个 chunk 含多个 token 时，接收间隔长也不一定是设备逐 token 生成慢。Foretoken 的请求 ITL SLO 使用最大接收 chunk 间隔，TTFT 衡量从请求开始到首个非空 `choices` chunk 的时间，首个事件可能是 role 或 finish。这些是操作定义，不是通用的分词级定义。

核对的 AIPerf 指标使用平均 decode interval 和对应的每用户吞吐倒数口径。工具间不能仅按名称比较；应对齐公式、token 来源、首事件规则、失败总体与观察窗口。

## 保留真正落在尾部的请求

顺序阶段可写为 `L=Q+P+D+O`，分别表示等待、prefill、decode 与输出交付，但 `p99(L)` 不等于各阶段 p99 相加。不同请求可能主导不同阶段，流水还可能交叠。应先选出端到端尾部请求，再检查它们的阶段与负载属性。

例如长输入主导 TTFT，长输出主导 E2EL。优化只改变哪些类别成功完成，也可能降低总体 p99。除总体外，应保留各类尝试数与达标率；取消慢请求同样可能改善仅成功延迟，却减少有效完成量。

分位数还受样本量影响。100 次观察的 p99 主要由最大的少数值和插值规则决定；一个请求产生更多 token，并不增加独立请求样本。同一过载突发中的连续请求有关联，逐请求 bootstrap 可能低估不确定性，按独立运行或时间块重采样更符合负载结构。

## 能区分原因的实验

保持请求集合与外部到达流量不变，扫描有效吞吐不再增长附近的负载，保留失败、超时和缺指标尝试。按请求检查联合达标，并区分首响应、最大流式间隔和完成延迟违约。token 吞吐上升但达标比例下降，可能只是批次更大或长输出更多，不一定改善了交互服务。

尾部归因时比较等长请求组，并对齐过载、缓存 miss、CPU 限流与 rank 延迟。相关性只提示机制；保持需求不变，改变怀疑的资源来验证。例如解除 CPU quota 后流式间隔改善而 prefill 不变，指向的就不是 prefill 内核。

最后保留时间分母。Foretoken 的一秒 token 曲线把整条请求的 token 计入完成窗口，尖峰不是设备瞬时生产速度。运行时长、准入时长与稳态观察窗口回答不同问题。不同窗口计数不等时，不能平均各窗口达标率来还原整轮比例。

## 来源与实现状态

核对日期：2026-10-14；开头请求速率是说明性例子。

- [Foretoken 指标](../../../../benchmarks/docs/metrics_zh.md)、[chunk 计时](../../../../benchmarks/src/benchmarks/integrations/streaming.py)和[HTTP runner](../../../../benchmarks/src/benchmarks/runs/http.py)：以 `e6ae3df6` 核对联合条件、失败、接收 chunk 与完成窗口。
- [AIPerf 指标](https://github.com/ai-dynamo/aiperf/blob/e1daadd10faa395100384358131d784d6858c5ae/docs/metrics-reference.md)与[有效指标](https://github.com/ai-dynamo/aiperf/blob/e1daadd10faa395100384358131d784d6858c5ae/docs/reference/effective-vs-active-metrics.md)：2026-10-12 revision 的统计总体和归一化差异。
- [Vidur，MLSys 2024](https://www.microsoft.com/en-us/research/wp-content/uploads/2024/05/vidur_mlsys24.pdf)，§§7.2–7.3：接近容量时的误差放大，以及其评估系统中随负载变化的 SLO／成本取舍。
