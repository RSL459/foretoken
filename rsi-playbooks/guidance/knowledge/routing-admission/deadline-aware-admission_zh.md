<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 按 Deadline 准入与 Goodput

[English](deadline-aware-admission.md) | 简体中文

选出“相对最不差”的 worker，不等于请求还来得及达标。过载时转发所有请求，会把 GPU 时间花在已无法按时完成的工作上，并拖慢本来可达标的请求。准入判断执行、等待还是拒绝；路由判断可执行工作去哪里。

## 现有控制不能互相替代

llm-d 已有 request admission 与 flow-control 队列。已读 `admission.go` 的 legacy 路径在 saturation 达到上限时拒绝可丢弃的负 priority 请求；flow-control 路径等待 dispatch、拒绝、TTL 过期、取消或关闭。这个文件没有预测 deadline 可达性检查。

llm-d 另外在 latency scoring 中实现预测 TTFT/TPOT headroom。所有预测都不利时，scorer 仍可能选择 idle 或 deficit 最小的候选，低分不等于拒绝。Production Stack 已按 priority 路由并把解析出的 priority 传给引擎，但该路径不构成预测 deadline 准入控制。Foretoken 已有基于角色的等待、并发计量、queue timeout 和 request deadline 结果。研究增量是按可达性联动，不是增加普通队列或超时。

## 从入口跟踪一次期限

请求在零时刻到达，TTFT 目标为 300 ms。准备输入和入口等待消耗 100 ms；最好候选的 worker 等待预计 120 ms，prefill 预计 100 ms。剩余只有 200 ms，下游却需要 220 ms。如果重新给 worker 一个完整 300-ms timeout，就掩盖了已经消耗的时间。

可用以下示例检查：

`remaining_slack = arrival_deadline - now - estimated_downstream_latency`。

负值意味着按当前估计无法达标，仍需考虑预测误差与允许的替代执行方式。TTFT 目标只计首 token 所需工作；端到端完成期限还需计入生成。Request deadline、queue TTL、TTFT 与 TPOT 是不同契约，不能混成一个平均“延迟”。

SCORPIO 的 2026 年修订结合 TTFT 预测拒绝、等待请求按 deadline 排序，以及 TPOT 准入检查。后者根据异构 token 频率需求构造 virtual batch size，并检查新增运行集合的预测 TPOT 是否满足其中最严格目标；decode credit 机制再提供差异化频率。准入与真实批次执行共享假设，只复制拒绝公式到 router，会缺少后半段机制。

## Goodput 应奖励什么

固定观察窗口内，可定义 `goodput = 同时满足全部声明 SLO 的完成请求数 / 时间`。还应报告所有 offered arrivals 的达标率，拒绝与超时默认计为未达标，除非 benchmark 明确另有契约。SCORPIO 在 adherence 中将拒绝计为 SLO 未满足。

例如 1,000 个到达请求：A 完成 900，其中 500 达标；B 拒绝 300、完成 700，其中 650 达标。B 的有效完成更多，但不能把 B 的已接纳达标率 93% 与 A 的全到达达标率 50% 比较。两个分母及全部结果都应展示。准入的价值是拒绝不可达工作后保住更多有效完成，而不是把失败从报告里删除。

## 职责、取舍与实现方向

请求层负责原始到达时间、可信服务目标、入口队列和响应结果；引擎负责执行可达性与批次成员；集群编排负责较慢的容量响应。Foretoken 应保持 owner 边界并传递剩余预算，不能每阶段重置时间起点，也不能让 scorer 修改全局准入容量。

预测错误会造成误拒或过载。激进拒绝可能不利于长 prompt、严格 SLO 类别，或预测器不熟悉的租户。等待能缓解短突发，却可能伤害本就紧迫的 deadline。Dispatch 后取消需要释放请求计量，但引擎资源释放仍可能异步完成，应由引擎处理。

## 实验与剩余问题

使用 open-loop 到达轨迹，使速率越过容量后再恢复。混合严格/宽松 TTFT 类别与不同输出长度，保持引擎调度不变，比较现有有界等待、deadline 排序和 prediction-aware admission；然后单独测试引擎执行频率联动。

记录全到达 SLO 达标率、有效完成/秒、误拒估计、逐类别结果、排队时间、在哪一层过期、p99 token 间隔和突发后恢复。加入低估与高估实验，并保留逐请求原始结果，防止策略通过丢掉迟到结果改善摘要。

真正未解的问题是：相对已有 queue/concurrency 控制，校准过的下游可达性模型能否增加有效完成。
## 来源

核查日期：2026-10-14。

- [SCORPIO，2505.23022v2，2026-08-26](https://arxiv.org/html/2505.23022v2)：TTFT/TPOT 联合准入与拒绝计量。
- [llm-d admission，commit 5253f555](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/epp/requestcontrol/admission.go)。
- [llm-d latency scorer，同一 revision](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/epp/framework/plugins/scheduling/scorer/latency/plugin.go)：排序与拒绝的区别。
- [Production Stack routing，commit 4e076e8d](https://github.com/vllm-project/production-stack/blob/4e076e8de3698a3729b575e3a5ade65ffbb929cf/src/vllm_router/routers/routing_logic.py)：现有 priority 传递。
- [Foretoken admission](../../../../data-plane/frontend/src/admission/src/lib.rs)与[到达时间捕获](../../../../data-plane/frontend/src/server/src/admission.rs)：现有结果与时间边界。
