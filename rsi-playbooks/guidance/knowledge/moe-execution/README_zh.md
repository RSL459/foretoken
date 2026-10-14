<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# MoE 执行

[English](README.md) | 简体中文

按专家层的实际瓶颈选择条目。

- 输入收集、激活搬运比矩阵乘法更贵？[将输入收集融合到分组 GEMM，减少 MoE 中间张量写回](reduce-moe-materialization-through-gather-fused-grouped-gemm_zh.md)解释收集融合、异步输出写入，以及为何训练 token rounding 不是保持原路由的推理优化。
- 面向吞吐的核函数在低负载反而变慢？[按小批 MoE 工作量选择 megakernel 分工](match-small-batch-moe-to-megakernel-work-partitions_zh.md)区分有效 token 与容量，比较分离执行和持久 megakernel 角色分工。
- 持续热点或业务变化导致慢 rank？[按负载窗口复制与迁移专家，分摊持续热点](balance-expert-hotspots-with-windowed-replication-and-migration_zh.md)串起观测、复制、迁移和新映射生效。
- 布局合理，但当前 batch 仍失衡？[逐批分配专家副本，均衡当前计算负载](balance-batch-load-through-expert-replica-assignment_zh.md)解释 LPLB 的受约束重分配及规划成本的收支问题。
- 低精度减少字节数，却改变回答或后端适用性？[用量化布局权衡 MoE 流量与数值误差](balance-moe-traffic-and-error-through-quantized-layouts_zh.md)连接打包权重、scale 布局、激活转换与归约语义。

专家布局、dispatch、TP/CP/PP 与重叠见[并行与通信](../parallelism-communication/README_zh.md)。完整模型验证使用维护中的[部署配方](../../../../examples/recipes/README_zh.md)、[性能评测](../../../../benchmarks/docs/perf/README_zh.md)、[质量评测](../../../../benchmarks/docs/eval/README_zh.md)和[性能剖析](../../../../benchmarks/docs/profile/README_zh.md)。正常服务测速与诊断捕获分开执行。

返回[推理知识库](../README_zh.md)。
