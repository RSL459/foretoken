<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 增量文本解码与流式缓冲

[English](incremental-text-streaming.md) | 简体中文 · [主机与流式输出](README_zh.md) · [推理知识](../README_zh.md)

## token 不等于可显示的文本分片

引擎可以稳定产生 token ID，用户却看到不规则的文本节奏。字节级 tokenizer 可能把一个 Unicode 字符拆到多个 token；decoder 规则可能依赖前文；特殊 token 间距和 stop string 也可能扣留已经算出的文本。推理内容与工具调用解析又增加一层边界。这些机制不同于设备停顿，不能直接把分片间隔当成解码速度。

例如，一个字符的 UTF-8 字节跨越多个 token ID。分别解码单个 token 可能产生替换字符，把这些字符串拼起来也恢复不了正确字符。增量 decoder 需要保留足够的 token 或字节上下文，只发出已稳定的后缀。因此，可见文本节奏与内容有关，不只由 token 数决定。

## 保留什么表示，决定重复多少工作

如果每次都解码整个生成前缀，长度依次为 1 到 n，且解码成本与长度线性相关，总工作量就是 1 + 2 + ... + n，即 O(n²)。即使原生 decoder 很快，反复构造完整累计字符串也可能产生同样的增长。增量实现希望成本主要跟随新增 token 和解决边界所需的少量上下文，但 tokenizer 规则、parser replay、stop 匹配和响应表示仍会改变实际复杂度。

核验的 vLLM detokenizer 已有原生 `DecodeStream` 和 helper 增量路径，维护输出位置并区分累计输出与 delta 输出。SGLang detokenizer manager 维护 surrogate/read offset、未发送文本及延迟分片，并按兼容解码设置进行分组 `batch_decode`。研究应进一步确认当前启用路径是否重复访问长历史、反复转换格式，或已经由序列化而非解码主导。

Stop string 本身要求一定缓冲。当最长 stop string 有 L 个字符且不应出现在输出中时，vLLM 在生成过程中保留至多 L − 1 个字符，否则已发送的后缀可能后来组成 stop marker。若每个 token 只贡献少量字符，可见文本就会延后多个设备步骤。结束时还必须发送剩余合法文本，并按 inclusion 规则裁剪匹配到的 stop 内容。

## 分组输出的摊销收益与等待成本

设每次输出操作有固定成本 a，以及每 token 成本 b。一次发送 k 个 token，可以把平均成本从 a + b 降为 a/k + b。若 token 以间隔 d 匀速产生，满组才发送，则平均额外等待约为 (k − 1)d/2。这个估计不覆盖 stop 处理、突发产出和定时 flush。

因此，分组可能适合大量短而快的流，却损害单用户交互延迟。只按 token 数触发的策略还可能扣住最后不足一组的输出，或延迟取消。活跃请求的内存也不只有 token 历史：保留字符串、parser 状态和排队输出都要分别计算。共享输出队列已经饱和时，多 decoder worker 无法解决问题；长流集中在一个 worker 时，增加 worker 也不等于均衡。

Fastokens 是 vLLM 已有的可选 backend。官方文档注明从 vLLM 0.23.0 起，可用于受支持的 BPE tokenizer 路径，并要求 fastokens 0.2.0 或更新版本；不是所有 tokenizer 模式都适用。比较 backend 成本时，应使用实际 tokenizer、输出长度和并发流数。

## 先区分文本正确性与传输性能

构造包含 ASCII、多语言字节边界、长输出、特殊 token、工具分隔符及跨发送边界 stop string 的内容矩阵。向对照路径输入相同的生成 token ID，先核对重建文本与结束 flush。提前停止造成输出变短，会看起来更快，却没有完成同样的工作。

之后分别改变输出长度与活跃流数，记录 token 可用、文本解码完成、入队和客户端解析事件时间。主机成本随输出长度超线性增长，提示前缀 replay 或复制；随活跃流数增长，则更像每事件固定成本或队列竞争。一起检查分片大小、字节量、原生 token 用量和逐请求最大间隔。引擎更快但分片更大，可能让观测 ITL 增大而 token 吞吐提高。Foretoken 当前按非空 `choices` 计时，role 和 finish 分片也计入，不是逐 token 计时；归因前必须查看实际 payload。

## 来源与核验

核验日期为 2026-10-14。

- [vLLM 增量 detokenizer](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/v1/engine/detokenizer.py)：原生/helper 路径、stop 缓冲与 delta 输出；版本日期为 2026-10-13。
- [SGLang detokenizer manager](https://github.com/sgl-project/sglang/blob/e9400c5a8f3a0d0312a37aecef694f5edfd69341/python/sglang/srt/managers/detokenizer_manager.py)：增量 offset、延迟文本、分组解码与结束清理；版本日期为 2026-10-13。
- [vLLM 优化文档](https://docs.vllm.ai/en/latest/configuration/optimization/)：fastokens 版本和 tokenizer 范围，核验当日读取，页面会随 upstream 更新。
- [Foretoken 分片计时](../../../../benchmarks/src/benchmarks/integrations/streaming.py)与[指标定义](../../../../benchmarks/docs/metrics_zh.md)：在 `e6ae3df6` 核实，ITL 描述接收到的分片间隔。
