<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 非前缀复用与 CacheBlend

[English](non-prefix-cache-blending.md) | 简体中文

在文档前插入不同内容，再复用它的 KV，不是普通前缀缓存。即使文档 token 完全相同，因果上下文也变了。CacheBlend 复用多数条目并选择部分 token 重算；位置搬移与语义修正必须分别理解。

## 需要修复什么

假设 B 的缓存是在单独处理 B 时生成，新输入却是 `A | B | question`。B 的初始嵌入除位置外可以相同，但较高层隐藏状态理应受 A 影响。把旧 key 旋转到新位置，只修复位置约定，并未补上对 A 的依赖。

采用相应 RoPE 约定时，`k_p = R(p) k` 移动 `delta` 后有 `R(delta) k_p = R(p + delta) k`。value 通常不做这一旋转。不同缩放方式、只旋转部分维度及 MLA 都需要明确几何信息，不能把通用旋转应用到所有缓存通道。

[CacheBlend 原始方法，2024 年 5 月](https://arxiv.org/html/2405.16444v1)逐层读取缓存，为选中 token 重算 Q/K/V，替换对应条目，让这些 query 对完整因果 KV 做 attention，再将更新隐藏状态传给后续层。未选中条目仍保留旧上下文近似。选择范围既决定计算量，也决定能修复多少跨文档交互；低重算比例不是精确性的证明。

例如 A 的指令改变了 B 中一句话的解释方式。只重算最后的问题，可能改善问题到文档的 attention，却仍保留 B 的陈旧表示。重算一些 B 的 token 可以传播更多信息，但不保证与完整 prefill 相同。跨文档推理和冲突指令比从未变文档中复制事实更能检验问题。

## 当前已有实现

[2026-10-14 快照](README_zh.md#来源快照)中的 LMCache 已同时包含旧进程内 blending 与多进程 blend 路径。[进程内 blender](https://github.com/LMCache/LMCache/blob/4d69cdc43ac9bab9c0c1cd5cac380c480cb32224/lmcache/v1/compute/blend/blender.py)在配置的检查层，以 float32 计算 key 差值的平方 L2 距离，按比例取 top-k，恢复序列顺序，再更新选中的 K/V。不能把这一具体判据泛化成没有定义的“重要 token”。

[MP 模块设计](https://github.com/LMCache/LMCache/blob/4d69cdc43ac9bab9c0c1cd5cac380c480cb32224/docs/design/v1/multiprocess/modules/blend.md)覆盖指纹匹配、前缀和非前缀片段、稀疏预取、仅 key 的 re-RoPE，以及按 token 写入分页 KV。所有相关 rank/read-group 对象都须可用；源码入口为 `lookup.py`、`retrieve.py`、`rope.py`。匹配与安全读取并不替代引擎的选择性重算职责。

[当前旧模式指南](https://docs.lmcache.ai/kv_cache_optimizations/blending.html)已将进程内模式标为 deprecated，并推荐 MP。示例分别分词各块，再插入分隔符；直接拼字符串可能改变边界 token，不能把该示例当作通用当前接入方式。Mooncake 字节搬运、Dynamo 分层加载和 vLLM 普通前缀复用，本身都不修复非前缀因果依赖。

## 能区分原因的实验

分别缓存 A、B、C，再测试排列变化、新系统指令、重复块及最后块只分配一部分的情况。固定 token ID、位置和权重，对照完整 prefill、无重算读取、仅位置修正，以及不同重算比例和检查层。查看逐层 key 偏差与最终 next-token 分布，区分位置错误、上下文依赖误差和选择范围不足。

服务评测加入多跳文档问答、冲突证据、摘要和多语言边界；逐类记录质量，不能只看总平均。同步记录 TTFT、重算 token 数、读取字节及失败后完整重算次数，将读取、选择和模型执行分别剖析。

后续空间在于跨模型选择稳定性、重排后的依赖修复及质量与成本的折中。论文收益属于其模型、负载和硬件条件，本条目没有复现 Foretoken 收益。

[KV 缓存](README_zh.md)
