<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 稀疏注意力中成为瓶颈的索引器

[English](sparse-indexer-routing.md) | 简体中文

当 sparse MLA 已经很快，但历史 token 打分与 top-k 选择仍随上下文增长时，用本文研究选择过程本身。

## 问题与当前上游

DeepSeek Sparse Attention（DSA）找到相关历史并不是零成本：轻量 indexer 先扫描历史 key，昂贵的 MLA 再读取选中的 token。把消费方限制为固定 top-k 后，indexer 在 decode 中的线性成本、完整 prefill 中的平方级工作可能暴露出来。

DSA 已有上游实现。本次核对的 vLLM revision 已包含 query RoPE/量化融合、压缩 logits、多设备后端、分布式精确 top-k 合并，以及两级选择的 candidate-block mask。因此，“增加层次化稀疏注意力”不足以说明缺少什么。2026 年 5 月的 MISA 提供了更具体的问题：按 query 选择部分 indexer head，能否降低打分工作而不丢失重要 token？

## 机制：先选 head，再选 token

DSA 对 query 位置 `t` 和历史位置 `s` 的索引分数为：

```text
I(t,s) = sum_j w(t,j) * ReLU(q(t,j) · k(s))
selected(t) = topk_s I(t,s)
```

这不是最终 MLA 的 softmax。学习得到的 indexer 估计哪些历史 token 值得参与更昂贵的注意力计算。DeepSeek 报告先使用聚合注意力训练 indexer，再进行稀疏训练，每个 query 选 2,048 个 token。随意更换 selector 会改变训练后的模型行为。

MISA 沿 indexer 的 head 轴做路由。先把历史分块，对每块 index key 求均值；每个 head 用这些粗粒度 key 估计 affinity，选出当前 query 最有用的 `h` 个 head。随后仍扫描全部历史，但只用选中的 head 打分，最终 token top-k 交给原有 sparse MLA。设 indexer 有 `H` 个 head，历史长 `L`，池化块大小为 `B`，每 query 的打分工作近似从 `H*L` 变为 `H*ceil(L/B) + h*L`。它仍需读历史 index key，算术减少不等于内存流量减少。

MISA† 先通过路由 head 得到更大的候选集，再用所有 head 重排。论文示例选 8 个 head、池化块长 1,024、初选 8,192 个候选，最后保留 2,048 个 token。如果一个重要 token 没进初选，重排无法挽回；均值池化也可能掩盖罕见的高 affinity key。因此核对的论文没有给出精确恢复原 top-k 的保证。

## 适用条件与取舍

论文在已训练的 DSA 模型上评估，包括 DeepSeek-V3.2 与 GLM-5，不重新训练。这不是任意稠密注意力或 GQA 的通用替换。实际 head 数、index key 维度、量化 scale、因果边界和选中 token 数共同决定执行工作。

长上下文可消除的打分工作更多，但缓存插入时也需要维护池化统计。短上下文、小 batch 未必能摊薄额外路由与 launch。prefill 要处理每个 query 的因果池化边界，decode 面对持续增长的历史。FP8/FP4 索引打分、注意力缓存量化和 head 路由近似是不同误差来源。单台 H200 的结果不能推广到所有 GPU 或异构设备。

## 实现入口与剩余设计空间

作者仓库现在已提供一阶段与两阶段 vLLM patch，不能沿用论文中“之后发布代码”的旧状态。已核对的 README 指定 vLLM 0.17.0、Transformers 5.2.0 和 TileLang 0.1.7.post3，两种 patch 只安装一种。两阶段内核先池化 key、路由 head，再对候选使用全部 head 打分；另有按 query norm 路由的选项，选择规则不同。这是作者维护的自定义模型/算子集成，不代表所有上游 vLLM 发行版支持。

可以研究现有 candidate-block 路径是否能表达 head 路由，而不建立第二套缓存协议。head 路由与 token-block 路由的目标不同：前者降低全历史上的算术，后者尝试避免读取部分历史。组合可能进一步降低流量，也可能叠加召回误差。分布式精确 top-k 合并则保留给定评分的排序语义，不能与近似候选裁剪混为一谈。

## 从局部到服务的实验

从真实模型多层、不同 query 位置取得 indexer 张量，对照现有完整打分路径，比较分数误差、top-k 重叠、漏掉的高注意力质量 token 和路由延迟。加入“只有一个相关 key、同块其他 key 都无关”的输入，检验池化失真。既测算术，也测 key 读取字节；dot product 加速后，top-k 或缓存流量可能仍占主导。

完整模型评估应覆盖检索、多跳推理、长代码和真实文档问题，不只做单针测试。路由与重排使用相同最终 top-k，计入池化统计维护和两段选择。服务实验扫描上下文与并发，拆分 indexer、sparse MLA 和其他模型时间，质量与延迟一起报告。论文的内核加速与 token 集合重叠率都不能代替服务收益。

## 依据与核对状态

核对日期为 2026-10-14。

- [DeepSeek-V3.2 报告 v1](https://arxiv.org/html/2512.02556v1)：索引公式、训练方式、top-k 与 MLA 的关系。
- [MISA，2026-05-08，v1](https://arxiv.org/html/2605.07363v1)：池化 key 的 head 路由、重排、复杂度和经验保真度。
- [作者实现 README，固定 `dc9f3a3b7938bd26e165b0c99e3b6ea627d1ecfc`](https://github.com/MuLabPKU/TransArch/blob/dc9f3a3b7938bd26e165b0c99e3b6ea627d1ecfc/MISA_preprint/README.md)、[两阶段内核](https://github.com/MuLabPKU/TransArch/blob/dc9f3a3b7938bd26e165b0c99e3b6ea627d1ecfc/MISA_preprint/misa_vllm_patch_2stage/misa_vllm_patch/misa_ops.py)与[indexer wrapper](https://github.com/MuLabPKU/TransArch/blob/dc9f3a3b7938bd26e165b0c99e3b6ea627d1ecfc/MISA_preprint/misa_vllm_patch_2stage/misa_vllm_patch/indexers.py)：核对于 10 月 13 日 revision，确认发布范围及实际路由/重排。
- [vLLM indexer，固定 `6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9`](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/model_executor/layers/sparse_attn_indexer.py)：已实现的评分、量化、top-k 和 candidate-block 路径；不代表所有发行版。
