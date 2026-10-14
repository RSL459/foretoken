<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 视觉 token：精确复用编码结果与近似复用 KV

[English](visual-token-cache.md) | 简体中文 | [多模态生成](README_zh.md)

## 重复请求到底能省掉哪部分计算？

围绕同一张图片反复提问，包含两类不同机会。图像编码器产生的 embedding 不依赖问题；处理方式与编码器权重相同，可以精确复用。语言模型的 KV 则可能依赖前文、位置和其他图片。换了问题还复用视觉 KV，通常不属于精确的前缀缓存。2025 年 12 月的 VLCache 研究后一种机会，不能与当前引擎已经具备的编码缓存混为一谈。

先算清视觉 token 数。Qwen2.5-VL 使用 14 像素空间 patch，并将相邻四个特征合并后交给语言模型。调整后的图像高宽为 H、W 时，语言侧视觉 token 数大约是 HW/784，不含模型特有的边界标记。448×448 对应 256 个；高宽同时翻倍后是 1,024 个，而不是 512 个。视频还会在时间维分组。这些数量由训练后的模型与 processor 共同决定。

## 一次请求如何执行

两次请求针对同一文档扫描件提出不同问题。先按 checkpoint 的 processor 解码、调整尺寸，再通过引擎已有的身份机制查编码缓存。未命中时执行 ViT 和 projector，保存 embedding，然后与文本 embedding 一起送入语言模型。正常预填充会生成带上下文的 KV。

VLCache 进一步保存施加旋转位置编码前的视觉 KV。相同图片再次命中时，读取 embedding 与视觉 KV，按新位置处理；每层重算一部分排在前面的视觉 token，其余复用。论文用小型校准集选择各层重算比例，并约束该比例随层深不增加。这不是在不同图片之间做相似度匹配。论文采用精确像素身份和 Tair KVCache Store。

可以用 E(image) 与 KV_l(image, preceding_text, positions) 区分两者：前者可保持不变，后者可能改变。精确复用 E 省编码器计算；近似复用 KV 还能省语言模型的视觉预填充。把两类命中率合在一起，就看不出收益来自哪里，也看不出哪项近似改变了答案。

## 模型、权重与质量边界

使用同一发布版本的权重和 processor。Qwen 报告提供公开 Qwen2.5-VL checkpoint 入口；VLCache 在 Qwen2.5-VL、Qwen3-VL 上评估，无需重训模型。校准得到的是复用比例，不是新语言模型。论文没有给出作者代码仓库，因此“论文中集成到 SGLang”不能写成 upstream 已公开提供该能力。

BF16、FP16 不会让跨上下文 KV 复用变成精确计算。对缓存 embedding 再量化是另一项近似，应单独验证。NVIDIA 上的结果也不能外推到其他加速器、attention backend 或 processor 版本。OCR 分辨率、图片顺序、提示位置、编码塔 LoRA 都会改变复用条件；平均得分接近，不代表细小文字或局部定位不受影响。

## 能区分原因的实验

固定 checkpoint、processor、dtype 和生成参数，比较完整重算、仅精确编码缓存、真正相同前缀的精确 KV 缓存、跨上下文选择性 KV 复用。构造图片相同但问题、图片顺序、前置指令不同的请求，并混入冷图片。任务包含小字 OCR、计数、定位和与图片事实冲突的文本前提。

记录 processor 时间、编码 GPU 时间、语言模型预填充时间、传输字节、缓存占用、逐图片命中率，以及服务 P50/P95/P99 TTFT、输出长度和满足延迟目标的成功请求数。分任务评分并检查改变的答案。编码耗时消失但预填充不变，说明精确缓存生效；额外收益必须另找原因。跨上下文失败而相同前缀成功，应先检查上下文依赖，而不是继续优化查缓存。

值得继续研究的是如何在变化的问题与负载下选择重算范围，同时守住质量。

## 来源与核对状态

核对日期：2026-10-14。

- [VLCache，arXiv:2512.12977v1](https://arxiv.org/html/2512.12977v1)：2025 年 12 月论文的方法与实验，未找到作者代码链接。
- [Qwen2.5-VL 报告，arXiv:2502.13923v1](https://arxiv.org/html/2502.13923v1)：processor、空间合并、训练和权重发布入口。
- [vLLM 编码缓存实现](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/v1/core/encoder_cache_manager.py)：2026-10-13 的 `6849ca6`；精确 embedding 缓存已经实现。
