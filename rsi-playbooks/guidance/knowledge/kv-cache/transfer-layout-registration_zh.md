<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 传输布局、注册与 Connector 组合

[English](transfer-layout-registration.md) | 简体中文

KV 搬运可能先受描述符构造、布局转换或完成通知限制，而不是 NIC 带宽。两端字节量相同也不代表缓存兼容：层、块、头、scale 和位置必须按一致语义解释。

## 沿一次搬运追踪

先定位源和目标物理范围，注册内存，发布端点元数据，构造所需块的描述符；再提交批次、查询或等待完成，最后允许消费者读取。源和目标分配的寿命必须覆盖整个操作，请求完成与提交传输不是同一个生命周期边界。

Mooncake [Transfer Engine 接口](https://github.com/kvcache-ai/Mooncake/blob/342c8aeece6b4eefb76c6b8b31ccfac8dde07aa3/mooncake-transfer-engine/include/transfer_engine.h)包含单次/批量本地注册、segment 打开、batch 分配和提交，以及 task/batch 状态查询。复用注册区域可以省去重复准备，但需要明确寿命 owner；batch ID 是操作句柄，不代表提交后即可复用缓冲区。

可先建模为 `T = T_register + n T_descriptor + T_submit + D/B + T_completion + T_relayout`。64 层分别寻址的许多小范围，即使总载荷 D 不大，也可能需要很多描述符。合并连续范围或采用跨层物理布局可以减少 n；先 gather 到暂存张量则增加拷贝和内存。最优点取决于消息大小、局部性及 attention backend 是否接受该布局。

## 兼容性不止 TP 相同

[2026-10-14 快照](README_zh.md#来源快照)中的 vLLM [NIXL 兼容矩阵](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/features/nixl_connector_compatibility.md)要求架构、缓存 dtype、attention 几何/backend 和传输模式匹配，已支持部分不同 TP 与块大小组合。Mamba 要求相同 TP；异构块大小只适用于非混合模型，且生产者块更小。MLA 复制 KV，不能按普通分头方式理解。

文档中的 `LBHNC`、`LBNHC` 对头切分有不同约束，跨层块要求 `BLHNC`；布局置换还存在独立限制。量化传输要求 scale 表示兼容，支持静态或 packed scale 不等于支持运行时动态 scale。应结合[worker 源码](https://github.com/vllm-project/vllm/tree/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/distributed/kv_transfer/kv_connector/v1/nixl)阅读矩阵，不能沿用“所有端点 TP 必须相同”的旧结论。

## 组合不等于自动择优

vLLM [MultiConnector 实现](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/distributed/kv_transfer/kv_connector/v1/multi_connector.py)选择第一个报告命中 token 的 connector 加载，向全部 connector 保存，并聚合异步完成。它既不合并各方部分命中，也不动态选最快来源。任一 connector 查找仍为 pending，组合查找就仍为 pending，即使另一方已命中。顺序会改变命中由谁提供；加入存储 connector 即使从未赢得加载，也可能增加保存流量。

LMCache [MP retrieve](https://github.com/LMCache/LMCache/blob/4d69cdc43ac9bab9c0c1cd5cac380c480cb32224/docs/design/v1/multiprocess/modules/blend.md)处理按 token scatter 与按 stream 顺序释放读取锁；Dynamo [物理传输层](https://github.com/ai-dynamo/dynamo/tree/7708f041a965e35374af976ab8ad610b9537e3bc/lib/kvbm-physical/src/transfer)拥有 executor 和通知抽象。这些是已有接入边界，不是可随意互换的 connector 契约。

## 局部实验与服务验证

固定载荷字节，改变描述符数量、连续/离散范围、首次/复用注册和消息大小，记录 CPU 构造、注册、就绪、字节、暂存拷贝与设备等待。合并只改善小消息，说明固定开销主导；大消息耗时随字节增长，则更接近带宽瓶颈。

随后使用真实 KV 验证已支持的布局/TP/块大小组合，与本地完整 prefill 输出对照，加入量化 scale、最后不完整块、取消和延迟异步保存。颠倒 MultiConnector 顺序，记录实际加载来源，对比全部保存流量和完成延迟，而不只看读取速度。

剩余空间是减少暴露的描述符/打包开销，以及测清目标负载的组合行为。

[KV 缓存](README_zh.md)
