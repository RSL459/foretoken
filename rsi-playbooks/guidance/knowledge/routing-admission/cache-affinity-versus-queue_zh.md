<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 缓存亲和性与排队成本

[English](cache-affinity-versus-queue.md) | 简体中文

缓存前缀只有在被选 worker 真正执行请求后，才能体现省下的计算。把所有共享前缀请求送到最热副本，可能产生比节省 prefill 更长的等待。优化目标应是用户看到的首 token 延迟，而不是最高缓存命中率。

## 当前上游已有行为

四个已核查项目都已经组合或提供缓存与负载信号。Dynamo 当前 selector 计入 prefill backlog、decode 成本和活跃请求，同时扣除 overlap credit；当 worker 的 prefill 积压超过最低负载候选时，可以衰减设备缓存 credit。AIBrix 当前文档描述标准化后的缓存/负载混合，默认说明为 `5 × prefix + 4 × load_balance`，也有带负载资格判断的 cache-first 模式。Production Stack 的 load-aware 路由用命中 token 比例减去相对 in-flight 负载罚项。llm-d 提供可组合的 prefix、queue、load 和 latency scorer。

Foretoken 已有 `kv_least_loaded`、`prefix`、`token_load` 和 `two_tier`；其缓存权重表达偏好，不是测量得到的传输时间。因此研究增量不应是“增加 cache-aware routing”，而是校准机会成本，并验证队列变化时策略是否仍有效。

## 用毫秒看一次选择

一个 10K-token 输入，在 A 上有 9K 可复用前缀，在 B 上完全未命中。假设测得模型估计 A/B 剩余 prefill 为 30/220 ms，队列等待为 300/20 ms。忽略相同开销后，预计 TTFT 为 330/240 ms：虽然 B 没命中，仍更快。若 A 的等待降到 40 ms，就应优先 A。

可用以下分解帮助分析：

`estimated_TTFT = ingress_wait + worker_wait + cache_ready_time + uncached_prefill_time + response_overhead`。

这是分析模型，不是所有路由器共同使用的精确公式。缓存准备时间取决于状态所在位置及何时能被调度使用；索引宣称有前缀，不等于设备内存立即就绪。本文只讨论路由后果，不实现 offload。

Preble 估计近期计算负载、新请求 prefill 成本和缓存驱逐后果。DualMap 的 2026 年 2 月方法把请求限制到两个 hash 候选，先偏好复用；若预计 TTFT 超出 SLO，则转向低负载候选。它用自适应 prefix key 分散热点、保留冷前缀局部性，排队迁移仅去预先确定的 backup，且要求预计延迟收益为正。这是一种有限候选架构，不是全舰队最优搜索。

## 复用入口与适用条件

Dynamo 已读 selector 使用 block 成本，而非校准到毫秒；credit 衰减以新请求大小标准化额外 prefill backlog。Production Stack 的负载为 in-prefill 加 in-decoding 请求数，但两个长 prefill 可能比十个短 decode 更重。AIBrix 的归一化混合分数同样依赖候选分布。llm-d 已有预测 latency scorer，并明确实现预测与 fallback。

当前缀复用明显且需求不均衡时，这类方法值得比较。低负载通常利于亲和性，高负载则会放大热点惩罚。快速驱逐、突发、worker 速度不同和过期指标都可能反转排序。Session key 保持位置，却不能证明该 session 的 KV 仍驻留。

引擎负责缓存有效性、分配和逐轮调度；Foretoken 请求层负责候选资格、评分和 dispatch 计量；集群编排负责容量与布局。多个 frontend 向同一 worker 发送请求时，路由器本地观测不能冒充全局观测。

## 实验与剩余问题

构造一个逐渐变热的前缀家族、多个冷家族和周期性续问。固定输入/输出长度及总请求速率，只改变热家族集中程度。比较现有缓存/负载混合、load-only、affinity-only 和成本校准候选；再引入可控观测延迟与真实前缀驱逐。

记录 TTFT 分布、声明 TTFT/TPOT 目标下的 goodput、实际执行未缓存 token、逐 worker prefill backlog、选择不均衡、命中率和路由开销。解释一次 miss 是因为确实更快，还是因为观测错误。命中率升高但尾部 TTFT 变差，应判为负结果，不是部分成功。

剩余空间是面对不确定观测时，如何稳健校准排队成本与缓存准备成本。
## 来源

核查日期：2026-10-14；当前代码固定到以下 revision。

- [Preble，2407.00023v2，2024-10-03](https://arxiv.org/html/2407.00023v2)：按执行时间结合利用/探索与驱逐成本。
- [DualMap，2602.06502v1，2026-02-06](https://arxiv.org/html/2602.06502v1)：双候选与按 SLO 切换缓存/负载。
- [Dynamo selector，commit 7708f041](https://github.com/ai-dynamo/dynamo/blob/7708f041a965e35374af976ab8ad610b9537e3bc/lib/kv-router/src/scheduling/selector/reference.rs)：backlog 与 overlap-credit 衰减。
- [AIBrix prefix routing，commit d0500b03](https://github.com/vllm-project/aibrix/blob/d0500b0399cf35ad0bf95d073faa83c23308f463/docs/source/features/gateway-routing/prefix-cache-aware-routing.rst)。
- [Production Stack routing，commit 4e076e8d](https://github.com/vllm-project/production-stack/blob/4e076e8de3698a3729b575e3a5ade65ffbb929cf/src/vllm_router/routers/routing_logic.py)。
- [llm-d prefix scorer，commit 5253f555](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/epp/framework/plugins/scheduling/scorer/prefix/README.md)。
- [Foretoken 路由](../../../../data-plane/frontend/src/router/README_zh.md)。
