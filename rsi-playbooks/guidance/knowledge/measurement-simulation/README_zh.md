<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 测量与模拟

[English](README.md) | 简体中文

选择能区分不同解释的对照，保持负载、计时边界、统计总体和数值语义一致。

- [到达与排队](workload-arrival-queueing_zh.md)：区分固定并发、外部到达、重放延迟及被遗漏的等待。
- [有效吞吐与尾部归因](goodput-tail-attribution_zh.md)：衡量请求联合达标，解释真正构成尾部的请求。
- [Trace 关键路径](trace-critical-path_zh.md)：区分累计时长、忙碌墙钟时间、资源争用和因果依赖。
- [剖析驱动的模拟](profile-driven-simulation_zh.md)：区分运行时模型与调度模型失配，校准可用的配置排序。
- [数值与质量差异](numerical-quality-divergence_zh.md)：分别判断固定前缀分布、贪心不稳定性和任务答案质量。

实验命令与目录见[实验记录手册](../../../experiment-records_zh.md)，完整研究方法见[元知识](../../meta-knowledge/README_zh.md)。

[全部推理知识](../README_zh.md)
