<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 查询感知选择与淘汰

[English](query-aware-selection.md) | 简体中文

少读 KV 不等于少存 KV。选择器可以保留全部信息，每次 query 读取不同页；淘汰方法则从活跃缓存中永久移除条目。这个区别决定后一问能否找回前一问没有使用的信息。

## Quest 如何按页选择

[Quest，2024 年 6 月](https://arxiv.org/html/2406.10774v1)保留完整缓存，为每页每个 key 维度保存最小值和最大值。给定 query `q`，页 p 的分数上界为：

`U_p(q) = sum_i max(q_i min_p(k_i), q_i max_p(k_i))`。

页内任意 key 与 q 的点积都不会超过这个逐维上界。但各维极值可能来自不同 token，因此上界可以很松；按上界排序不等于精确找 top token，也不证明被省略概率质量很小。

执行过程是读取页元数据、计算分数、按预算取 top-k，再只读取这些页的 K/V 做实际 attention。`q_i` 为正时关注 key 最大值，为负时关注最小值。因此，上一问不重要、下一问在负方向上变得重要的页，仍可能被重新选中。

页大小 S、上下文 N、选中 K 页时，相对完整 K/V 扫描的元数据和 KV 流量可近似为 `1/S + KS/N`，假设元素宽度相同，暂不计选择与工作区流量。S=16、N=32768、K=128 时约为 12.5%，不能据此预测服务快 8 倍，页打分、top-k、启动与非 attention 层仍存在。论文设置保留前两层稠密执行，因为这些层的有效稀疏性较弱。

基于历史 attention 的淘汰，则可能因为一个条目近期无人关注而删掉它。下一问若恰好需要它，除非从独立后备存储重新加载，否则已不可用。保留 sink token 或最近窗口，只保护特定类别，并不保证任意后续检索。不能将这些方法统一称为等价压缩。

## 条件与当前实现边界

Quest 原方法评测长上下文 decoder 和专用页选择 kernel。质量取决于模型、层、预算和任务；多事实聚合可能比单 passkey 需要更多页。因为仍保留全部 KV，它本身不减少 HBM 容量。把未选中页放到其他存储层，会额外产生加载与执行调度问题。

[2026-10-14 上游快照](README_zh.md#来源快照)确认的是已有基础设施，而非各引擎普遍实现了 Quest。vLLM 的 [NIXL 兼容说明](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/features/nixl_connector_compatibility.md)描述分页几何，LMCache [MP blend](https://github.com/LMCache/LMCache/blob/4d69cdc43ac9bab9c0c1cd5cac380c480cb32224/docs/design/v1/multiprocess/modules/blend.md)提供稀疏片段读取，Dynamo [KVBM onboarding](https://github.com/ai-dynamo/dynamo/blob/7708f041a965e35374af976ab8ad610b9537e3bc/lib/kvbm-engine/docs/onboarding.md)及 Mooncake [Transfer Engine](https://github.com/kvcache-ai/Mooncake/blob/342c8aeece6b4eefb76c6b8b31ccfac8dde07aa3/mooncake-transfer-engine/include/transfer_engine.h)搬运已有数据。这些能力不代表查询相关页打分。提出实现前，还须检查目标 backend 是否已有等价选择器。

## 区分选择与删除的实验

采集真实长生成中的 query 和完整 KV，以相同 token 预算比较完整 attention、Quest 式上界、基于完整 attention 的精确页排序与历史淘汰。精确排序是诊断参考，并非无成本可部署算法。查看页召回、遗漏 attention 质量、输出偏差、元数据字节、选择耗时和 KV 读取耗时。

设计连续两问，分别询问早期不同段落。保留缓存的选择器可在第二问重新选择此前未用的页；淘汰则必须重新加载。再加入分散多事实聚合、干扰项密集页和位置扫描，区分可恢复性、页上界过松及预算不足。

服务侧跨上下文长度和并发比较质量与完成吞吐，把峰值内存和访问流量分开记录。选择 kernel 由注意力职责负责，缓存研究关注元数据驻留、后备存储读取及质量感知预算。剩余问题包括量化后的元数据、页大小权衡与动态预算，不表示已有 Foretoken 实现或收益。

[KV 缓存](README_zh.md)
