<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 编码微批与 embedding 生命周期

[English](encoder-pipeline-cache.md) | 简体中文 | [多模态生成](README_zh.md)

## 编码很快，首 token 为什么仍然很慢？

视觉 kernel 很快，多模态 TTFT 仍可能被预处理、等待组批、embedding 传输或下游预填充阻塞。vLLM 已经公开支持编码分离。真正值得研究的是如何重叠这些阶段，既不长期占住 embedding，又不为了凑满批次消耗过多首 token 预算。

2026 年 9 月提交的 EAServe 在分离架构中研究自适应编码微批：达到批次上限、出现由到达率推导的空闲间隔，或最老请求达到等待期限时发车。这里的矛盾很具体：多等一会儿能提高设备利用率，也会让请求更晚得到首 token。固定大批次不一定适合稀疏流量。

## 一次执行及其资源责任

四个图像请求不均匀到达。编码器收集已经完成预处理的张量，直到批次满或空闲间隔触发，再执行视觉模型。它为每个输出保留请求与输入图片位置，发布传输元数据。预填充 scheduler 等待所需 embedding，安排加载，确认完成后再执行图文预填充；此时编码器可以处理下一批。只有时间线显示计算与传输实际并行，才算重叠，不能仅凭异步 API 判断。

视觉 token 数为 V、语言侧 embedding 宽度为 d、每元素 b 字节时，传输负载约为 Vdb。取 V=4,096、d=3,584、b=2，约为 28 MiB，尚不含元数据与协议开销。命中 embedding 缓存可以省编码，但消费端不在本地时，传输仍可能存在。

当前 vLLM 编码缓存按请求及输入位置计引用。请求释放引用后，条目变成可回收，不一定立即删除；后续分配需要空间才驱逐。同一轮调度中被重新使用的条目不会再进入物理删除通知。这些区别避免“逻辑释放”变成“过早删掉设备数据”。取消请求也必须清除引用，并在重用缓冲区前完成或终止其拥有的传输。

## 模型与实现现状

采用已发布 VLM 权重及对应 processor；微批调度不需要训练新模型。vLLM 文档展示 Qwen2.5-VL、ExampleConnector 与 ECMooncakeConnector，后者通过 Mooncake TransferEngine 使用可用的 TCP 或 RDMA。音频路径还需要模型特有的 token 长度元数据，只覆盖独立音频，不涵盖带音轨视频；示例 proxy 也不是完整 realtime API。

EAServe 描述了 NIXL、libsmctrl、CUDA 与配置搜索，在 NVIDIA GPU 上评估，但论文未给出作者公开仓库。它的排队方法可以指导实验，不是已经可启用的 upstream 参数。FP16/BF16 传输在没有额外转换时保留既定表示；其他 backend、编码 graph 形状、编码权重变化仍应单独核对。

## 区分排队、计算与传输的实验

固定阶段放置、checkpoint、dtype、传输协议和 decoder 配置，以相同图片及到达时间回放立即发车、固定微批等待、自适应空闲间隔三条路径。分别改变单图片尺寸、每请求图片数、到达率，避免把新的资源分配效果算到组批算法上。

记录预处理完成时间、编码排队、编码执行、传输完成、decoder 等待、TTFT 尾延迟、设备利用率、传输字节、峰值活跃 embedding 内存和满足 SLO 的成功请求数。加入排队中、编码中、传输中的取消，观察内存能否回到预期稳态；取消请求不能算成功吞吐。

如果大批次降低了每图片计算时间，却恶化 TTFT，瓶颈在等待。如果自适应策略只改善稳定泊松流量、不改善突发，应检查到达率估计的响应速度，而不是宣称找到了通用最优批次。剩余问题是到达感知执行如何平衡 embedding 生命周期与交付成本。

## 来源与核对状态

核对日期：2026-10-14。

- [EAServe，arXiv:2609.31551v1](https://arxiv.org/html/2609.31551v1)：2026 年 9 月微批和传输机制，未找到作者公开代码入口。
- [vLLM 编码分离](https://docs.vllm.ai/en/latest/features/disagg_encoder/)：当前流程、connector、示例和音频限制。
- [编码缓存实现 `6849ca6`](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/v1/core/encoder_cache_manager.py)：embedding 生命周期与驱逐，commit 日期为 2026-10-13。
