<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 大词表选择与采样流水

[English](vocabulary-selection-sampling.md) | 简体中文

模型前向优化后，大词表过滤与采样仍占明显时间，尤其推测验证一次产生多行 logits 时，可从选择算法和阶段融合继续研究。

## 选择不一定需要完整排序

词表大小为 V 时，top-k 只需确定保留集合，不需要排好全部 V 项。随后 top-p 要找到累计概率边界，采样则从剩余分布抽取 token。阶段之间反复生成全词表张量，会带来额外启动和访存。

FlashInfer 当前的 CAKE 已提供融合替代：线程块 cluster 通过分布式共享内存协作执行 radix selection，输出最多 1,024 项的紧凑 `(概率, 索引)` slab；后续阶段排序 slab，按 top-k 的概率总量计算 top-p，归一化并采样。符合条件的小 k 可以把尾部工作融合到第一阶段，较大情形则通过 dependent launch 让第二阶段准备与第一阶段尾部交叠。

这是已实现的上游能力。继续研究应针对真实 batch／词表形状的分派、集成复制成本和其他选择算法的适用范围，而不是重新写一次完整排序。

## 保持请求所要求的分布

过滤顺序会改变结果。例如概率为 `[0.5, 0.3, 0.2]`，`k=2`、`p=0.6`。先 top-k 后保留总量为 0.8，第一项已超过 `0.6 × 0.8 = 0.48`，因此 top-p 只留第一项。若先对原分布做 top-p，则需要前两项才能超过 0.6。两种过程保留集合不同。

核对的 CAKE 实现明确采用 top-k-first，规定同概率时的索引顺序、定点累计概率和 Philox 随机流。分布等价并不自动意味着不同实现使用同一 seed 就生成逐 token 相同的结果，还取决于随机数分配方式。替换时需按接口语义和任务复现要求分别判断。

贪心解码则是另一种情况：argmax 不需要 top-p 或概率重新归一化。可以研究如何省去不必要的全词表操作，但仍要保留 logits processor 与请求要求的 logprob；LM head 输出或概率张量也可能有其他消费者。

## 硬件与输入范围

该路径要求连续的 float32 概率行，并利用 Hopper 及更新 NVIDIA 设备的能力。不支持的输入、禁用 top-k 或 k 超过 slab 范围时，会转入已有确定性采样实现。因此 API 调用成功，不代表专用内核实际执行；接口提供 routing 查询来区分。

总成本还包括 logits 转概率、惩罚项、约束和布局转换。接入时多做一次 float32 复制，可能抵消局部采样收益。推测解码还应按最终提交 token 的成本比较，而非只比较每行候选的采样耗时，见[推测解码](../speculative-decoding/README_zh.md)。

## 有区分力的实验

保留实际 batch、词表、过滤参数与概率形状，覆盖尖锐和平坦分布、边界相等值、贪心请求以及逐行不同配置。分别在 eager 和图重放下测完整过滤／采样路径，查看实际分派；分布语义和相同 seed 的 token 一致性分开比较。

最后把模型前向与后处理一同测量。某一阶段缩短后，启动或主机处理可能成为新的主导开销。无剖析运行用于比较速度，trace 用于解释关键路径变化。

## 来源与实现状态

核对日期：2026-10-14。

- [CAKE 采样文档](https://docs.flashinfer.ai/api/cake_sampling.html)：支持范围、route 查询和公开接口。
- [固定版本 FlashInfer 实现](https://github.com/flashinfer-ai/flashinfer/blob/d6dd9f336dcd9e4820b1583d20077804fe61147c/flashinfer/cake_sampling.py)：选择、相等值、特殊数值和 fallback 语义。
- [FlashInfer sampling API](https://docs.flashinfer.ai/api/sampling.html)：专用路径之外已有的其他实现。
