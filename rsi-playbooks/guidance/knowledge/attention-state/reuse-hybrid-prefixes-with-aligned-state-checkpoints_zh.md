<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 用对齐的状态检查点复用混合模型前缀

[English](reuse-hybrid-prefixes-with-aligned-state-checkpoints.md) | 简体中文

## 问题与当前上游

普通 transformer 可以复用前缀 KV page。hybrid 模型还需要处理完同一个前缀后得到的循环状态，以及可能存在的卷积状态。若两个请求更早就分叉，只保留上一请求最终状态是不够的。

vLLM 已支持对齐的 Mamba 检查点；v0.30.0 官方文档还提供有明确 speculative decoding 前提的细粒度前缀缓存选项。当前 cache manager 已处理 partial-tail checkpoint 和 copy-on-write。检查点位置及实际复用成本仍取决于负载。

## 恢复边界为什么重要

假设两个请求共享 token 0–89，之后分叉。注意力 KV 已覆盖到位置 90，循环检查点却只在处理完 64 和 128 个 token 后存在。128 的状态已经消费了不同后缀，不能充当位置 90 的状态；64 的状态有效，重算 token 64–89 即可到达目标边界。

检查点必须对应准确的已处理 token 数。恢复生成前，所有注意力组、循环层和短卷积缓冲区都要对齐到这个边界。full-attention KV 覆盖和循环检查点覆盖并不相同，可用命中应取交集，而不是任选其中最大的命中长度。

检查点位置在重计算、内存和复制之间取舍。间隔为 `C` 时，命中可能需要重放最多约 `C-1` 个 token。保存更多检查点减少重放，却增加状态快照；循环状态虽不随普通 decode 的 token 数增长，单份矩阵仍可能很大。如果缓存快照被用作当前请求的可写状态，copy-on-write 能避免一个续写修改另一个请求正在复用的快照。

分配器还有独立的空间几何。vLLM 将兼容层分组，使用等大小物理 page 的共享池。较大的循环状态可能迫使注意力 block 扩大，或使用 padding 来适配。逻辑 token 间隔与物理 page 字节数不是同一个量：扩大 block 可能改善打包，却降低前缀命中的粒度。

## 适用条件与取舍

Attention 与 Mamba/GDN 等混合模型的状态组成、层比例、dtype 和快照大小都依模型而定。较大的 FP32 状态会让频繁检查点昂贵，注意力缓存较小不意味着循环快照便宜。

v0.30.0 的细粒度选项要求 `mamba-cache-mode=align`、Mamba group 上启用 EAGLE/MTP，并显式设置小于 Mamba block 的 `prefix-match-unit`。该单位必须整除参与缓存的 block size，文档排除了 multi-module MTP。这些是特定版本的前提，不是建议为所有 hybrid 请求仅仅为了缓存而启用 speculative decoding。

重复系统 prompt、多轮续写和互不相关 prompt 的检查点价值不同。scheduler 的 chunk 边界也决定何时能导出状态。应用消息结束的位置并不自动意味着可用的状态快照已经存在。

## 实现入口与剩余设计空间

固定版本 vLLM 的 `MambaManager` 负责对齐查询、内部检查点、partial-tail 缓存及待执行 copy-on-write。状态 block 搬迁和 boundary offload 路径说明，缓存发布、可写状态与传输是不同生命周期阶段。应扩展既有 owner，而不是让 router 或 storage connector 自己定义另一套状态边界。

可测量的问题包括保留高复用位置的少量检查点、按已观察到的前缀分叉选择位置，以及避免放大 attention block 的打包方式。首先确认目标引擎版本是否已经提供所需模式。只传 attention page，却遗漏循环或卷积状态的 connector，不构成完整 hybrid 缓存传输；传输完成也必须先于检查点使用。

## 从局部到服务的实验

构造共享前缀刚好位于 attention/Mamba block 边界之前、之上、之后的成对请求，分别比较冷执行、对齐命中后重放和细粒度命中。固定后缀，比较开关缓存时的最终状态与输出分布，而不只查看 hit counter。

再改变 scheduler chunking、发布前取消、并发分叉续写、eviction 和 slot 复用。这些具体生命周期能暴露边界错配和共享状态修改。分别记录检查点字节、复制时间、重放 token 数、allocator padding 及真正可用的命中长度。

最后在相同总内存预算下运行多轮与静态前缀服务，混入无关流量制造 eviction，比较 TTFT 尾延迟、成功吞吐和 decode 干扰。命中率更高也可能更慢：状态复制和容量下降可能超过省掉的重计算。router affinity 只有面向完整可复用 hybrid 状态才有意义，不能只看到 attention KV 就假定能恢复。

## 参考

- [vLLM v0.30.0 automatic prefix caching](https://docs.vllm.ai/en/v0.30.0/features/automatic_prefix_caching/)：细粒度选项及明确前提。
- [vLLM hybrid cache 设计](https://docs.vllm.ai/en/latest/design/hybrid_kv_cache_manager.html)：共享 page、分组、前缀交集与文档中的实验性限制。
- [`MambaManager`，固定 `6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9`](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/v1/core/single_type_kv_cache_manager.py)：该版本的对齐/细粒度查询、检查点保留和 copy-on-write。
