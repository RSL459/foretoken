<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 流式生成：交付能播放的块，而不只是更早的 token

[English](streaming-audio-video.md) | 简体中文 | [多模态生成](README_zh.md)

## 客户端真正等待什么？

文本 token 流不自动等于语音或视频流。语音解码器可能需要未来编码，视频 VAE 可能等待完整 latent 块，网络也可能先送来暂时无法播放的字节。应优化的是首个可用媒体的延迟，以及持续播放时不中断的交付能力。

Qwen2.5-Omni 提供基本架构：Thinker 产生文本与隐藏状态条件，Talker 产生语音编码，再分块还原波形。当前 vLLM-Omni 文档描述异步 Qwen3-Omni Thinker→Talker→Code2Wav 流水，以及独立的扩散视频 WebSocket API。它们属于不同模型与协议，不能统称后就抹去具体边界。

## 一个块如何到达播放器

Thinker 处理输入，交付 Talker 启动所需信息。Talker 不等完整回答结束，就产生一个 codec 块。connector 携带请求关联及顺序元数据传输它；Code2Wav 解码时，Talker 可以继续生成下一块。跨阶段取消和输出排序由 orchestrator 负责。

Qwen2.5-Omni 报告中的波形路径使用 flow-matching DiT 和修改后的 BigVGAN。DiT 每块的感受野覆盖两个历史块、当前块及一个未来块，因此首个可播放块不仅等待计算，也等待 lookahead。这是该旧模型的具体设计，不能当作 Qwen3-Omni codec 的精确架构。

本次核对的 Omni 视频输出 API 先发 `video.chunk_metadata` JSON，紧接着发送含 fragmented MP4 字节的 binary frame。接收顺序属于协议。入口 `WS /v1/realtime/video` 用于生成视频输出，而不是输入实时对话视频。文档格式为 `m4s`，pipeline 必须具备 step execution 和分块输出能力；打开 streaming 参数不会让只能最终输出的模型自动变成增量模型。

假设每块包含 D 秒媒体，启动后每 A 秒到达一块，平均 A<D 是持续播放的必要条件，但尾部间隔仍可能耗尽缓冲区。因此启动延迟和长间隔概率必须与平均生成速度分开观察。

## 权重、状态和质量

文本、语音编码、波形或视频组件必须使用相互匹配的模型发布包。Qwen 报告提供发布入口，选择具体版本时还应检查实际文件与 Omni 模型支持。分块交付本身不用训练新权重；因果视频蒸馏是另一项模型变化，见[少步蒸馏](few-step-distillation_zh.md)。

transformer 支持 BF16/FP16，不代表 vocoder、VAE 也使用相同精度。CUDA attention、codec、VAE 依赖决定实际硬件覆盖。缩小块可降低首媒体延迟，也可能增加边界开销或破坏连续性。减少 lookahead、量化历史、截断上下文会改变质量，不只是网络优化。

请求状态应随消费进度保持有界。慢客户端或断连会让生成块堆积，即使 GPU 本身运行正常。架构文档说明同步与取消，但没有规定通用 credit-based 背压算法；这样的控制方法应作为待测设计，而不是现有保证。

## 实验与剩余空间

固定模型、精度和采样，在支持的块大小之间回放相同 prompt。比较最终输出与真正的增量解码，再加入可控客户端延迟与取消。要覆盖长语音、长视频，短演示看不出队列增长和漂移。

记录首 codec token、首解码波形或帧、客户端首可播放媒体、块间 P50/P95/P99 间隔、real-time factor、播放中断时长、排队字节、GPU 内存、取消清理时间，以及每秒合格媒体秒数。语音评分包含可懂度、说话人一致性、边界杂音；视频包含运动与主体连续性。

codec 提前但媒体仍然晚，应检查 decoder lookahead 与封装；平均实时因子改善但播放中断更多，说明突发交付破坏了播放。剩余候选在块级重叠、缓冲控制和质量工作点，不是把已实现流水重新列为未合并能力。

## 来源与核对状态

核对日期：2026-10-14。

- [Qwen2.5-Omni，arXiv:2503.20215v1](https://arxiv.org/html/2503.20215v1)：语音架构与块级 lookahead；报告里的视频是输入，不是生成输出。
- [Omni 架构](https://github.com/vllm-project/vllm-omni/blob/37f094a388ba1c79f83c129fda39797c1ebfc2a4/docs/design/architecture_overview.md)与[视频 API](https://github.com/vllm-project/vllm-omni/blob/37f094a388ba1c79f83c129fda39797c1ebfc2a4/docs/serving/streaming_video_output_api.md)：2026-10-13 的 `37f094a` 内容；这些是已有 upstream 路径，受模型限制，`v0.30.0` 发布早于该 main 版本。
