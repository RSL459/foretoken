<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 推理知识

[English](README.md) | 简体中文

从实际开销或设计问题出发，查找理解和改进推理系统所需的机制、实现依据与研究线索。每篇说明方法如何工作、适合什么条件、上游已经实现什么，以及怎样通过实验判断剩余的设计选择。

## 模型计算

- [注意力与循环状态](attention-state/README_zh.md)：稠密注意力流水、MLA 布局、稀疏索引、通道门控循环计算与状态复用。
- [MoE 执行](moe-execution/README_zh.md)：专家计算划分、token 分配、副本均衡与量化布局。
- [推测解码](speculative-decoding/README_zh.md)：草稿生成、验证、接受成本、自适应深度与候选选择。
- [量化](quantization/README_zh.md)：块缩放格式、异常值、校准，以及数值误差与实际内核的配合。
- [多模态与生成模型](multimodal-generation/README_zh.md)：视觉编码、多模态批次、扩散加速与流式生成。
- [多模型与适配器](multi-model-adapters/README_zh.md)：LoRA 计算、adapter 驻留、租户调度与共享执行容量。

## 设备执行

- [算子设计](kernel-design/README_zh.md)：持久化任务分配、warp 分工流水、面向布局的融合与大词表选择。
- [编译与运行时](compiler-runtime/README_zh.md)：形状专门化、图分派、自定义算子边界与图内存生命周期。
- [并行与通信](parallelism-communication/README_zh.md)：张量、专家、上下文和流水线并行，以及通信粒度和计算重叠。
- [异构硬件](heterogeneous-hardware/README_zh.md)：设备特定布局、图与 stream 行为、collective 及 CPU／GPU 执行取舍。

## 服务与资源管理

- [引擎调度](engine-scheduling/README_zh.md)：token 预算、预填充与解码干扰、抢占、公平性和层组预填充。
- [KV 缓存](kv-cache/README_zh.md)：存储分层、部分复用、压缩、选择与传输兼容性。
- [请求路由与准入](routing-admission/README_zh.md)：缓存亲和与排队、工作量预测、截止时间和过载。
- [分离式服务](disaggregated-serving/README_zh.md)：P/D、Attention／FFN 分离，阶段配比、传输与异构放置。
- [扩缩容与放置](autoscaling-placement/README_zh.md)：容量估计、反馈延迟、冷启动、拓扑及容量退出。
- [模型加载与存储](model-loading-storage/README_zh.md)：加载流水、I/O 与主机内存、分布式权重及休眠恢复。

## 主机执行与实验证据

- [主机与流式链路](host-streaming/README_zh.md)：主机／设备调度、增量文本、背压、取消与 NUMA 影响。
- [测量与模拟](measurement-simulation/README_zh.md)：到达与排队、SLO 有效吞吐、trace 关键路径、模拟校准和数值差异。

一次解码变慢可能跨越多类。例如，先通过 attention 或 MoE 条目理解计算，再通过通信条目检查 rank 依赖，用主机和运行时条目解释启动间隙。目录划分机制职责，交叉链接串起完整执行路径。

## 怎样理解依据

实现状态以引用版本和核对日期为准；测量结果注明来源和实验条件，Foretoken 实测链接到实验记录。

条目区分已有能力与待研究问题，以及仅改变执行方式和需要新权重、训练或模型改动的方法。

## 增补与维护

每个技术职责使用一个分类目录，每个独立问题使用一个描述性文件名，提供英文正文和 `_zh.md` 中文版本。分类 README 按问题介绍用途。一篇可以比较多篇论文或多个实现，不因项目名称不同就另建类别或重复条目。

[知识条目模板](../../templates/guidance-template_zh.md)提供问题、机制、适用条件、实现状态和实验的组织方式。同一问题有新证据时，优先修正或扩充原条目，保留失败原因、可复用输入和代码，并更新分类索引。研究方法放在[元知识](../meta-knowledge/README_zh.md)，单轮命令和原始结果放在[实验记录](../../experiment-records_zh.md)。
