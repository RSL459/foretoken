<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# KV 量化与存储编码

[English](quantization-storage-codecs.md) | 简体中文

“压缩 KV”可能指低精度常驻张量，也可能指读取后先解码、再供 attention 使用的存储对象。前者可以减少运行时容量与读取量，后者主要减少存储和传输字节。混淆两者会误判容量与性能。

## 表示不同，成本也不同

[KIVI，2024 年 2 月](https://arxiv.org/html/2402.02750v1)采用不对称量化：key 沿 token 方向逐通道分组，value 沿通道方向逐 token 分组。前者针对持续出现的 key 通道离群值，后者针对随 token 变化的 value 范围。每组以 `x_hat = s q + z` 重建，其中 `z = min(x)`，`s = (max(x) - min(x))/(2^B - 1)`。整数、scale 和 offset 都占空间。

key 需要积累一定 token 才能组成组。KIVI 保留最近一段全精度残差窗口，把更老状态量化，再在 attention 中结合两部分；典型设置为组大小 32、残差长度 128。2-bit 有效载荷名义上只有 BF16 的八分之一，但元数据、残差、对齐和工作区会降低实际节省，短历史可能几乎不受益。key/value 分组差异和残差窗口都是方法的一部分，不等于“把 dtype 改成两比特”。

[CacheGen，2023 年 10 月](https://arxiv.org/html/2310.07240v1)则为缓存上下文生成 bitstream。每十个 token 为一块，以锚点和量化差值表示，采用随层变化的精度，再做算术编码。预存多个压缩等级，让控制器依据加载成本选择某种表示，或直接读文本重算。运行时先将 bitstream 解码回 KV 张量。熵编码相对量化符号无损，并不代表相对原始浮点缓存无损。

存储编码应比较 `T_load = T_fetch(D_compressed) + T_decode + T_install`，只有实测重叠才能从中扣除；常驻 attention 内存仍可能接近未压缩大小。运行时量化则比较 `T_attention = T_read + T_dequant + T_compute`，包含打包与 scale 读取。kernel 低效或 attention 不是服务瓶颈时，表示更小也可能更慢。

## 当前引擎与源码入口

[2026-10-14 快照](README_zh.md#来源快照)中的 vLLM [量化 KV 文档](https://docs.vllm.ai/en/latest/features/quantization/quantized_kvcache/)已说明 FP8、校准 scale、逐张量/逐头选择和跳过指定层。逐头支持依赖 attention backend。这些是已有机制，不等同 KIVI 的 2-bit 表示；默认单位 scale 与数据集校准 scale 也属于不同质量条件。

LMCache [CacheGen 指南](https://github.com/LMCache/LMCache/blob/4d69cdc43ac9bab9c0c1cd5cac380c480cb32224/docs/source/kv_cache_optimizations/compression/cachegen.rst)已有 `remote_serde: "cachegen"`，并提示离开 deprecated 的进程内模式。实验前应核对相应 MP 配置和 serializer 路径。Mooncake 搬运注册字节，Dynamo KVBM 搬运不同层中的缓存对象；仅存储更少传输字节，并不能证明模型使用低比特 attention。vLLM 的 [NIXL 兼容规则](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/features/nixl_connector_compatibility.md)还约束两端的 scale 表示。

## 质量与实验方法

局部实验采集目标模型真实 K/V，分别改变 key 轴、value 轴、组大小、残差窗口和校准方法，对比重建张量、attention 输出及最终 next-token 分布，区分离群值处理、校准失配和模型误差积累。随机高斯张量无法代替真实离群值结构。

存储编码实验固定解码 dtype，改变编码大小和带宽。若 TTFT 改善但常驻 KV 字节不变，收益来自传输压缩而非运行时显存压缩。运行时量化先比较相同请求数量，再比较相同内存预算；后者才能揭示单请求实验看不到的容量收益。

服务验证覆盖检索、多跳推理、长生成、代码与多语言，保留逐题质量、TTFT、TPOT、峰值内存和完成吞吐。剩余空间是模型校准与表示/kernel 互通，不是简单启用已有 FP8。本条目没有 Foretoken 质量或性能实测。

[KV 缓存](README_zh.md)
