<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 异构 rank 与期限下的 adapter 调度

[English](tenant-aware-scheduling.md) | 简体中文 | [多模型与适配器](README_zh.md)

## 为什么总吞吐看不出问题？

rank 128 的租户可能比 rank 8 消耗更多 adapter 计算和驻留空间；低延迟与宽松延迟租户也不应只用一个平均 TTFT 判断。共享基础模型的请求已经可以组批，真正问题是 rank、热度、期限不同时，哪些请求适合共享批次和设备。

2025 年 11 月的 LoRAServe 研究 rank 感知的分布式放置与 routing；2026-10-04 提交的 HALO 研究多 SLO 调度及 base/LoRA 执行重叠。前者决定请求去哪儿，后者决定何时执行 prefill/decode，单篇论文都不是完整租户服务实现。

## 一次调度决策如何产生

LoRAServe 根据近期流量估计各 adapter 的 token 需求，结合在 SLO 下预先 profile 的 rank-specific 容量，计算各 rank 的服务预算，再装入服务器分配，以概率 routing，并调整分配减少迁移。某 adapter 的 routing fraction 总和为一。热度相同而 rank 不同，未必消耗相同容量；把相近 rank 聚在一起，可以减少异构批次的低效。

worker 上，HALO 按下一个期限计算请求 slack。prefill 受 TTFT 约束，decode 受逐 token TBT 约束。已经缓冲了一些生成 token 的请求可能暂时跳过 decode iteration，把容量让给更急的请求。其 output queue 将生成和客户端释放分开，因此 GPU 生成时间与客户端收到时间是两种测量。

HALO 还在 decode 用经调优的 SM 分配重叠 base 与 LoRA 计算。两条独立路径消费同一输入，再在适配层输出汇合。它以反馈搜索配置，而不是假设平分 SM 最优；论文也明确，这种并行不改善 prefill。研究时应与引擎现有 overlap 路径比较，不能声称所有引擎都缺这项能力。

## 条件、权重和代价

这些方法使用兼容基础模型和已训练 adapter，不提出新的训练目标。保留 checkpoint 身份、target module、rank、scale、tokenizer 与任务质量。合成 adapter 可以验证 rank 差异，不能证明租户任务效果。dense decoder 结果不能自动覆盖 MoE LoRA、多模态 tower、量化 kernel 或另一 TP 布局。

LoRAServe 使用 A100 与 InfiniBand/GPUDirect RDMA 获取远端 adapter，放置依赖 profile 工作点与近期流量。HALO 的 SM 分区也依赖 GPU/runtime 控制，应记录实际 dtype 与 kernel 路径。调度原则上保留模型计算，但并发 kernel 或归约顺序改变仍会影响数值复现。

组批集中化会以等待换利用率。按热度决策可能饿死低频 adapter；按期限可能改善紧急流量，却拖慢宽松流量。输出缓冲可平滑交付，也可能主动延后 token，所以不能只凭交付指标认定计算变快。

## 验证策略而不是总平均

回放 rank、热度、输入长度、输出长度、SLO 标签彼此独立的 trace，加入热度翻转、紧急突发、低频高 rank。固定 worker 容量比较是否按 rank routing；固定 routing 比较 FIFO 与 slack-aware 调度；最后在相同批次成员下比较顺序与 SM-overlap 执行。

按租户报告 P95/P99 TTFT、TBT、完成 token、失败、队列年龄、期限违约、生成与释放时间，以及 SLO 合格 goodput。记录 adapter 迁移、传输字节、切换成本、CPU/GPU 排队、SM 分区效率。保留总到达需求，不能丢弃难请求后冒充吞吐提升。

rank 放置只适合静态热度，应查预测滞后与迁移成本；客户端 TBT 改善而生成未变快，说明缓冲解释了结果；紧急吞吐靠饿死低频租户增加，说明需要明确公平性目标。剩余研究在联合考虑成本和期限、可测量租户结果，不是重新包装基本多 LoRA 服务。

## 来源与核对状态

核对日期：2026-10-14。

- [LoRAServe，arXiv:2511.22880v1](https://arxiv.org/html/2511.22880v1)：算法、远端传输和负载；该版本承诺接受后发布代码与 trace，但未提供作者仓库，不推断后续可用状态。
- [HALO，arXiv:2610.04956v1](https://arxiv.org/html/2610.04956v1)：2026-10-04 提交，slack 调度、SM 搜索和输出队列；此版本未找到作者代码链接。
- [SGLang LoRA 文档](https://docs.sglang.io/advanced_features/lora.html)：已有多 adapter 组批与 runtime 限制；main 版本为 2026-10-13 的 `e9400c5`。没有证据时，不为论文设计推断 upstream PR 状态。
