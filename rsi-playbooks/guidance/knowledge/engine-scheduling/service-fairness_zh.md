<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 连续批处理中的服务公平性

[English](service-fairness.md) | 简体中文

请求数相等，不代表获得的服务相等。持续提交长输出的客户端可能消耗远多于短请求的推理工作。连续批处理还带来第二个问题：长请求一旦进入运行集合，仅靠公平准入无法撤回它每轮 decode 获得的服务。

## 先定义共享的是什么

Virtual Token Counter（VTC）按加权 token 服务量而非请求数计量。基本模型为 `service = wp × input_tokens + wq × output_tokens`。Decode 执行成本不同，因此输出 token 可使用更高权重。这些权重是策略与成本近似，不是通用的 GPU 毫秒换算。

有容量时，VTC 从 counter 最小的等待客户端接纳请求。处理输入时计入 input service，每生成一个 token 计入 output service。客户端新增自己的第一个等待请求时，counter 取保留值与已有等待客户端最小 counter 的较大值；等待队列为空时，参考最后离开该队列的客户端。这样既消除闲置期间产生的额外 credit，也保留已经计入的服务量。只有运行请求而没有等待请求的客户端，不属于这个比较集合。

例如权重为 1 和 2，A 的 1,000-token 输入、100-token 输出消耗 1,200 单位；B 的 100-token 输入、1,000-token 输出消耗 2,100 单位。按请求数看两者相等，VTC 则能区分。论文的服务差上界依赖输入和批次有界、服务器容量为正、无抢占等假设，并不是每个请求的硬延迟保证。

## 缓存局部性改变目标

VTC 的顺序可能打散前缀复用。2025 年 Locality-aware Fair Scheduling 提出 DLPM：优先最长前缀命中，但只有 deficit 为正的客户端能接纳。当所有有等待请求的客户端 deficit 均不为正时，为 deficit 不为正的活跃客户端补充服务额度（quantum），再扣除未缓存输入后缀和生成输出的成本。这样允许一段局部性较好的连续工作，却不允许无限占用服务。

计费口径直接影响公平性的含义。全量计入输入 token，会把只需很少新 prefill 的长缓存命中请求也当作昂贵工作；只计未缓存后缀更接近实际执行，但相同份额下缓存热客户端能获得更多逻辑 token。应先决定公平性衡量计算服务、交付 token，还是商业配额，不能默认某一种一定正确。

DLPM 的服务差上界依赖请求成本与 quantum；quantum 越大，局部性越好，但短时间差异也越大。分布式 D2LPM 增加 client-worker deficit 与 cache-aware 候选选择，每个 worker 仍维持本地公平。基本模型没有解决跨客户端共享和有依赖关系的程序轮次。

## 当前实现是不同契约

AIBrix 已有 `vtc-basic` 路由。该实现预估输入/输出 token，根据逐用户使用量和负载选 pod，并在路由时计入预计使用量。该文件没有实现论文中的逐迭代引擎调度，也没有按实际完成 token 纠正预估。它衡量的是 gateway 本地预计 dispatch 服务量。

llm-d 当前 program-aware fairness 提供按衰减加权服务量选择的 least-attained-service，以及 turn-priority；它们属于 dispatch 队列策略，官方文档明确说明 in-flight 状态和 session identity 假设。Foretoken 也已把基于角色的等待、公平 dispatch 与实例评分分开。

引擎负责实际批次服务与 token 计量，请求层负责可信身份、入口公平和 dispatch，集群编排负责容量。多路由副本必须明确计量范围；逐副本 counter 不能证明全局服务差上界，把 counter 复制到另一个 controller 也会产生竞争 owner。

## 实验与设计选择

构造持续有积压、输入/输出长度不同的客户端，再加入闲置后返回的客户端。分别使用共享前缀和不同前缀，固定到达负载与容量，比较按请求数准入、加权服务调度与 locality-aware 候选。

记录逐客户端服务量时间曲线、持续积压客户端最大服务差、p95/p99 等待时间、最差客户端 SLO 达标率、缓存复用、goodput 和调度开销，并明确缓存 token 是否计费。Gateway 使用预计输出时加入取消和预测误差；追踪实际生成 token，避免把公平 dispatch 当作公平执行。

剩余问题是部署究竟需要哪一种服务定义，以及 gateway 准入如何与引擎执行合作。新增公平性子系统前，先复用现有公平队列和生命周期计量。

## 来源

核查日期：2026-10-14。

- [VTC，arXiv 2401.00588v2](https://arxiv.org/html/2401.00588v2)：counter lifting、加权服务与证明假设。
- [Locality-aware Fair Scheduling，2501.14312v1，2025-01-24](https://arxiv.org/html/2501.14312v1)：DLPM/D2LPM 与局部性取舍。
- [AIBrix `vtc_basic.go`，commit d0500b03](https://github.com/vllm-project/aibrix/blob/d0500b0399cf35ad0bf95d073faa83c23308f463/pkg/plugins/gateway/algorithms/vtc/vtc_basic.go)：实际 gateway 计量与选 pod。
- [llm-d program-aware fairness，commit 5253f555](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/epp/framework/plugins/flowcontrol/fairness/program-aware/README.md)：现有 dispatch 策略与状态范围。
- [Foretoken 路由](../../../../data-plane/frontend/src/router/README_zh.md)：准入与选实例职责分离。
