<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 路由与准入

[English](README.md) | 简体中文

判断到达请求能否使用共享服务容量、可以等待多久，以及应由哪个实例执行。

- [缓存亲和性与排队成本](cache-affinity-versus-queue_zh.md)：等待热 worker 的成本，何时超过在低负载实例重算？
- [预测负载路由与观测延迟](predictive-load-routing_zh.md)：预计工作量、尚不可见的 dispatch 和缺失延迟预测应如何影响选择？
- [按 deadline 准入与 goodput](deadline-aware-admission_zh.md)：何时拒绝不可达工作比继续转发更有效，怎样完整计量所有到达请求？
- [租户队列与过载 dispatch](tenant-queues-and-overload_zh.md)：突发期间 priority、公平性、共享容量和 session 进度如何相互影响？

这些决策属于请求层。[引擎调度](../engine-scheduling/README_zh.md)负责真实批次成员与 token 服务；集群编排负责容量和布局变化。

返回[推理知识库](../README_zh.md)。
