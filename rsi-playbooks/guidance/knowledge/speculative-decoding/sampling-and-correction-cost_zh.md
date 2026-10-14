<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 保持目标采样分布并降低校正成本

[English](sampling-and-correction-cost.md) | 简体中文 | [推测解码](README_zh.md)

## 验证之后还有哪些公共成本

目标模型的推测前向并不是整轮流程。词表投影、采样过滤、残差分布、随机数、输出整理和 logprobs 都可能消耗明显时间与内存。这些成本同时存在于训练型 draft、并行块和复用候选中。研究目标应是保持真实目标采样语义、删除重复工作，或选择已有验证算法，以更多词表计算换取更长有效前缀。

设 p 是当前因果历史下希望保持的目标采样分布，q 是实际产生候选 x 的分布。普通逐 token 验证以 min(1,p(x)/q(x)) 接受 x；拒绝时从归一化的 max(p-q,0) 采样。候选全部成功时，bonus 从目标分布产生。这样保持的是分布，不保证与同 seed 的非推测运行逐字相同。

一个目标与任意现有 proposer 即可，无需额外训练验证模型。确定性候选的 q 是点质量，不是 argmax 之前的 softmax。惩罚、温度、top-k/top-p 或 grammar 若定义了目标行为，每个候选历史下的 p 都要体现这些处理；候选重排也会改变 q。正确性取决于有效分布，不能只看原始目标 logits。

## 具体单轮过程

设词表只有 A、B 两个符号，p=(0.6,0.4)，q=(0.8,0.2)。A 以 0.75 接受，B 总会接受；A 被拒绝时正残差完全落在 B。最终 P(A)=0.8*0.75=0.6，恰好等于 p。若把拒绝校正改成无条件从目标重采样，就会多生成 A。

先生成候选链及其真实提议概率，再对所有位置执行因果目标验证。每个位置依据自身假设前缀处理目标 logits；执行接受和校正，逐 token 算法在首次拒绝处停止，并整理接受前缀及校正/bonus。只提交这些输出。早期候选被拒绝后，后续已计算 logits 对应的是错误候选历史，不能直接输出为校正历史的续写。下轮前要恢复被污染的推测状态；详见[循环状态推测回放](../attention-state/recurrent-speculation-replay_zh.md)。

块验证采用另一种精确概率耦合，不只是把独立逐 token 检查并行化。SGLang 当前文档说明，它检查所有候选前缀，即使较早前缀检查失败，也可能保留更长前缀，并采用相应校正分布。跳过拒绝 token 来模仿这一行为是错误的：正确性来自整块算法。

## 已实现边界与成本

vLLM `6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9` 采样器区分贪心 argmax 与随机路径，按推测历史处理惩罚和采样限制，先计算各位置的恢复候选，再选出有效输出前缀。top-k/top-p 辅助代码指出词表排序成本。为避免同步，部分校正工作在知道首次拒绝前就执行；“最终没用上的计算”仍可能比主机决策更快。

设 batch 大小为 B、draft 长度为 K、词表大小为 V。FlashInfer 融合链接口接收 draft 概率 [B,K,V]、draft ID [B,K]、目标概率 [B,K+1,V]。假设 B=32、K=8、V=128000，两个 float32 稠密概率张量约占十进制 278.5 MB，尚未计入 logits 和缓冲。这是形状计算，不是实测内存。因此即使接受率不变，减少物化或融合遍历也可能有价值。

SGLang 提交 `e9400c5a8f3a0d0312a37aecef694f5edfd69341` 已记录 CUDA/ROCm 下随机 EAGLE/EAGLE3/NEXTN 的精确块验证，要求 topk=1 及完整目标词表 proposal，也覆盖受支持的随机 DFlash/DSpark 路径。贪心点质量 DFlash 不会由此得到更长前缀。块验证增加词表归约，值得单独测量。降低另一组接受阈值不是同一优化，不能沿用精确算法的分布保证。

## 实验与设计问题

分开比较三件事：同一逐 token 规则的融合实现、块验证与逐 token 验证、随机与确定性 proposal。混在一起会失去归因。固定权重、采样、graph、上下文和输出上限。先用小词表合成分布检查校正恒等式，再在真实模型中覆盖尖锐/平坦分布、过滤、惩罚、贪心随机混合批次、EOS 与取消。

记录投影、过滤/排序、概率转换、随机数、残差选择、输出整理及 logprob 时间。比较总迭代时间内提交的输出，而不是单次验证的接受候选数。FlashInfer 的独立 accepted 计数可包含首次拒绝之后的位置；emitted-draft 计数才是实际输出前缀，且不包含 bonus，两者不可替换。

正确性应检查实际服务 sampler 的 next-token/前缀经验分布及质量。性能使用未开启 profiler 的运行，报告 TTFT、输出间隔、完成时间、吞吐、峰值内存和 SLO 容量。节省采样时间却改变输出长度或过滤规则，已经不是同条件比较。

未解决问题包括：提前算残差是否比无同步的延迟计算更快；请求 logprobs 时如何避免重复全词表遍历；哪些随机采样负载足以摊薄块验证的归约成本。需要 kernel 与服务两层测量。

## 来源与实现边界

核对日期为 2026-10-14。

- [vLLM 固定采样器](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/v1/sample/rejection_sampler.py)：预处理、点质量提议、残差选择与输出整理。
- [FlashInfer 链 API](https://docs.flashinfer.ai/generated/flashinfer.sampling.chain_speculative_sampling.html)：形状、随机数 offset 和 accepted/emitted 区别；滚动文档需匹配安装的库版本。
- [SGLang 固定指南](https://github.com/sgl-project/sglang/blob/e9400c5a8f3a0d0312a37aecef694f5edfd69341/docs/docs/advanced_features/speculative_decoding.mdx)：受支持的块验证组合及词表归约成本。
- [Block Verification Accelerates Speculative Decoding](https://arxiv.org/abs/2403.10444) 定义原始算法，上面的固定引擎指南界定服务支持范围。
