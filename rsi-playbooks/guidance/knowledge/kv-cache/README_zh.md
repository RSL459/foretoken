<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# KV 缓存

[English](README.md) | 简体中文

缓存内容、驻留与搬运决定复用成本和容量；请求路由和预填充/解码部署由服务编排知识负责，attention 的数学与执行由注意力知识负责。

- 读取已有 KV 真的比重算更快吗？[通过分层卸载与异步预取隐藏 KV 加载延迟](hide-kv-loading-latency-through-tiered-prefetch_zh.md)分析暴露在关键路径上的搬运时间、暂存容量与复用寿命。
- 文档顺序或前文变化后，还能复用缓存吗？[通过选择性重算复用非前缀文档 KV](reuse-document-kv-with-selective-recompute_zh.md)解释位置修正、选择性重算及仍存在的语义误差。
- 哪种压缩减少运行时显存，哪种只减少存储或传输字节？[按压缩目标选择 KV 量化或存储编码](choose-kv-quantization-or-storage-codecs-for-compression_zh.md)区分 KIVI、校准 FP8 与 CacheGen。
- 能否少读 KV，却不永久删除信息？[通过查询感知的页选择减少 KV 读取](reduce-kv-reads-through-query-aware-page-selection_zh.md)区分 Quest 的页选择与不可逆缓存淘汰。
- 网络很快，为什么传输仍慢或不兼容？[减少 KV 传输开销：布局、内存注册与 Connector 组合](reduce-kv-transfer-overhead-layouts-registration-and-connectors_zh.md)梳理描述符、几何关系、完成通知与组合后的职责。

## 参考

- [LMCache `dev`](https://github.com/LMCache/LMCache/tree/4d69cdc43ac9bab9c0c1cd5cac380c480cb32224)：分层存储、预取与 blending。
- [Mooncake `main`](https://github.com/kvcache-ai/Mooncake/tree/342c8aeece6b4eefb76c6b8b31ccfac8dde07aa3)：注册内存搬运。
- [vLLM `main`](https://github.com/vllm-project/vllm/tree/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9)：量化 KV、传输兼容与 connector 组合。
- [Dynamo `main`](https://github.com/ai-dynamo/dynamo/tree/7708f041a965e35374af976ab8ad610b9537e3bc)：KVBM 加载、卸载与物理搬运。

[推理知识](../README_zh.md) · [模型加载与存储](../model-loading-storage/README_zh.md)
