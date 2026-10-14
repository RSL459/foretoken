<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 路由与准入

[English](README.md) | 简体中文

判断到达请求能否使用共享服务容量、可以等待多久，以及应由哪个实例执行。

- [权衡前缀复用与排队成本，降低首 Token 延迟](reduce-ttft-balancing-cache-reuse-and-queueing_zh.md)：等待热 worker 的成本，何时超过在低负载实例重算？
- [通过延迟预测路由与派发预留减少排队](reduce-queueing-through-predictive-routing-and-dispatch-reservations_zh.md)：预计工作量、尚不可见的 dispatch 和缺失延迟预测应如何影响选择？
- [通过预测期限可达性准入提高 SLO 有效吞吐](improve-goodput-through-predicted-deadline-feasibility-admission_zh.md)：何时拒绝不可达工作比继续转发更有效，怎样完整计量所有到达请求？
- [避免租户饥饿：公平队列与有界派发](avoid-tenant-starvation-fair-queues-and-bounded-dispatch_zh.md)：突发期间 priority、公平性、共享容量和 session 进度如何相互影响？

这些决策属于请求层。[引擎调度](../engine-scheduling/README_zh.md)负责真实批次成员与 token 服务；集群编排负责容量和布局变化。

返回[推理知识库](../README_zh.md)。
