<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 多阶段资源平衡

[English](multistage-resource-balance.md) | 简体中文

## 问题与机制

当 encoder 或 prefill 产生输出的速度超过下游消费能力，增加 worker 反而可能让服务变慢。多阶段服务要平衡计算、状态传输、请求准入和中间状态驻留。这是流水线容量问题，不是 encoder 算子优化。

把请求路径写成 E→P→X→D，X 表示 KV 传输。初步稳定条件是 `λ < min(n_E μ_E, n_P μ_P, μ_X, n_D μ_D)`。各 μ 必须来自相同负载分布，并使用相同服务单位；图像编码工作不能直接与文本 token/s 比较。Decode 容量还要包含请求持续时间、上下文增长和延迟目标。

例如到达 8 请求/s，E、P、传输、D 的容量分别为 12、10、7、9 请求/s。把 P 翻倍仍不能突破 7，反而产生更多等待传输的 buffer。Little 定律给出平均驻留请求数约为 λW，W 为驻留时间；buffer 字节数则需要按请求大小加权。长请求即使数量少，也可能占据大部分空间。

执行顺序同样重要：准入后先让 E 完成并交付 descriptor，再让 P 完成传输交接，选择兼容的 D，并让中间状态存活到消费者完成或取消被确认。阶段完成屏障不等于对所有后续阶段做原子 reservation。提前预留 D 可以保护交接容量，却可能在 E/P 执行时浪费解码槽；延后选择更灵活，却会遇到下游竞争。

## 硬件、表示与成本

各边界都要使用真实模型和 dtype 测量。Encoder 输出是 embedding tensor 或 connector 定义的状态，不是 token KV。P/D 字节数取决于注意力结构、KV dtype 和并行布局。四 GPU 上的 Qwen2.5-VL-3B，与机架级互联上的 FP8 Qwen3-235B MoE，属于不同平衡问题。

分离会增加权重副本、内存 buffer、启动路径和故障域。若 D 驻留或网络已成为瓶颈，给 P 更快 GPU 可能无效。大图与长 prompt 相关突发时，仅看平均服务速率不够。各阶段应分摊端到端延迟预算，而不是分别追求最大孤立吞吐。

## 证据与当前集成

核对日期为 2026-10-14。Dynamo 的[encoder 分离文档](https://github.com/ai-dynamo/dynamo/blob/b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd/docs/fern/pages/use-cases/multimodal-serving/encoder-disaggregation.md)已有 E/PD、E/P/D 和 NIXL embedding 传输；不同后端范围不同，TensorRT-LLM 仅支持 E/P/D。这证明阶段分离已存在，不等于已有通用跨阶段 reservation 算法。

2026 年 [SARA 论文](https://arxiv.org/html/2609.26763v1)用 M/G/k 描述 P、M/G/1 描述传输、连续批处理 birth–death 近似描述 D，在分位数约束下把成本分配给算力、链路和 HBM。其 A100/SGLang 评估涉及 LLaMA 3.1 8B、Qwen2.5 32B、GPT-3 175B 配置，但总体评估 dtype 未明确说明。Poisson 到达、长度独立等假设限制了适用性。论文平均 goodput 收益属于来源报告，不是 Foretoken 结果。

Foretoken 的[维护中 E/P/D 示例](../../../../examples/encoder-prefill-decode/README_zh.md)使用 Qwen2.5-VL-3B、共享 encoder 存储和 Mooncake P→D 传输，Pool 可分别配置。[执行工作流](../../../../data-plane/frontend/src/server/src/runtime/workflow.rs)在 E/P 屏障之后保留清理职责，P 完成后选择 D。[扩缩容 owner](../../../../control-plane/internal/autoscaling/README_zh.md)独立评估容量，并提交完整服务 cohort。已有阶段执行不等于全局最优资源平衡，也不等于 triplet 原子 reservation。

## 实验与剩余问题

先用实测阶段时间和输出字节分布模拟串联流水线。固定 GPU 总预算，改变各阶段数量，再独立改变带宽。比较自由运行的 producer 与考虑下游容量的准入，记录排队字节、deadline 失败和 buffer 驻留，不只统计完成请求。

真实 E/P/D 服务保持图像内容和 tokenizer 不变，扫描图像数、文本长度、输出长度和突发。记录 accepted、各阶段完成、传输完成、最终输出时间；在各交接点取消请求，每次只缩放一个角色。P 更快而端到端 goodput 不变，说明瓶颈被移动，不是优化成功。联合容量承诺、大小感知背压、尾延迟预算分配仍值得研究。Encoder 细节见[多模态生成](../multimodal-generation/README_zh.md)。

[返回分离式推理服务](README_zh.md)
