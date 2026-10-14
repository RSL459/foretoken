<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 避免租户饥饿：公平队列与有界派发

[English](avoid-tenant-starvation-fair-queues-and-bounded-dispatch.md) | 简体中文

共享队列可能被突发租户占满等待位置；全局 priority 排序即使面对小请求，也可能饿死低优先级流量。多租户过载控制需要明确共享目标、有界等待，并在请求不再消费容量时释放对应计量。

## 分开四种决策

Priority 表达哪个类别先执行；公平性表达可执行 flow 如何共享服务；容量上限约束活跃工作；队列过期表示继续等待是否仍有意义。四者互不蕴含：priority 整数不预留容量，跨所有队列选最早队首也不保证租户公平。

llm-d 当前已有 per-flow queue 接口、ordering、fairness 和 priority holdback。`globalstrict` 文档明确说明，它在 priority band 内跨 flow 选择最优队首，不提供租户公平。Program-aware 提供 least-attained-service（LAS）或 turn-priority；priority-holdback 在 saturation 上升时更早限制低优先级 dispatch，并支持不同 ceiling。

AIBrix 已有按预计 token 使用量的逐用户 VTC 路由，但 basic router 负责选 pod 和计入预计使用量，不执行容量拒绝，也未在该文件中按实际生成量纠正。Production Stack 解析 priority、选 endpoint 并向引擎传递，路由选择与引擎执行仍不同。Foretoken 已把基于角色的等待、公平 dispatch 与路由分开，候选改动应完善现有 owner，而非在 scorer 再建队列。

## 一次突发如何经过队列

A 排入 1,000 个请求，B 只有一个。全局 FIFO 可能让 B 等完整段突发；逐租户队列让 dispatcher 比较各队首，而不是把所有请求混在一起。LAS 可偏好加权服务量较少的 flow；按请求轮转只保证相同 dispatch 数，忽略执行成本差异。

llm-d program-aware LAS 对服务量施加衰减，文档机制中输出 token 权重为输入的两倍，因而近期消费比久远历史更重要。Turn-priority 则偏好更深的 session，并计入等待时间，可缩短交互程序下一轮依赖，但目标并非租户等份服务。其文档要求每个 fairness ID 对应一个 session，才能赋予 turn depth 合理含义。

VTC 原始 counter 防止闲置客户端回来时带着无限 credit；DLPM 的 locality-aware deficit 用 quantum 允许缓存友好的连续执行，同时限制独占。论文约束引擎层服务量；gateway 本地 dispatch counter 衡量的是另一个范围。[引擎公平性](../engine-scheduling/balance-token-service-weighted-counters-and-locality-deficits_zh.md)说明了两者区别。

## 身份与容量范围

Fairness identity 应来自部署的可信身份边界。调用者任意填写 ID，可以把一个租户拆成许多 flow；全部缺失身份归入 default flow，则会共用一条队列。llm-d 文档明确说明 default-flow 与 session depth 后果。

多个 frontend 也改变范围：两个独立队列可能都认为同一租户尚未得到足够服务。需要决定产品保证的是逐 frontend、逐 service、逐 tenant 还是逐 session 公平。共享容量时复用已有 admission/request-ledger owner，不把 Prometheus 当作准入事务系统。

请求层负责 queue、身份、reservation、过期和 dispatch；引擎负责批次成员及实际 token 服务；集群编排负责副本增减。客户端断开或遗弃的 in-flight 请求不应无限保留 dispatch 计量，llm-d program-aware 文档也明确指出这种状态滞留问题。物理 GPU 清理仍属于引擎生命周期。

## 实验与剩余选择

构造固定速率租户、突发租户、长输出租户和有依赖的多轮 session，在同一容量运行。比较现有公平 dispatch、全局严格排序、LAS；只有目标适合 workload 时，才加入 session-oriented 候选。身份与 priority 分配在比较中保持一致。

记录逐租户排队、拒绝/过期/取消、加权服务量、最差租户 TTFT/TPOT 达标率、整体 goodput 和突发恢复时间。多轮 workload 还应报告程序完成时间；单个请求变快不一定让程序变快。加入取消和丢失完成信号，检查 outstanding accounting，并明确 counter 范围。

剩余选择不是孤立地问“哪个队列算法最好”，而是过载时产品应保证什么，以及 dispatch 和引擎能否共同实现它、不丢失有用工作也不饿死某类请求。

## 参考

- [llm-d global-strict，commit 5253f555](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/epp/framework/plugins/flowcontrol/fairness/globalstrict/README.md)。
- [Program-aware fairness，同一 revision](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/epp/framework/plugins/flowcontrol/fairness/program-aware/README.md)。
- [Priority holdback，同一 revision](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/epp/framework/plugins/flowcontrol/usagelimits/priorityholdback/README.md)。
- [AIBrix VTC basic，commit d0500b03](https://github.com/vllm-project/aibrix/blob/d0500b0399cf35ad0bf95d073faa83c23308f463/pkg/plugins/gateway/algorithms/vtc/vtc_basic.go)及 [Production Stack routing，commit 4e076e8d](https://github.com/vllm-project/production-stack/blob/4e076e8de3698a3729b575e3a5ade65ffbb929cf/src/vllm_router/routers/routing_logic.py)。
- [VTC 方法](https://arxiv.org/html/2401.00588v2)与 [DLPM/D2LPM，2501.14312v1](https://arxiv.org/html/2501.14312v1)。
- [Foretoken admission owner](../../../../data-plane/frontend/src/admission/src/lib.rs)。
