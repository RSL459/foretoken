<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 传输与网络瓶颈

[English](transfer-network-bottlenecks.md) | 简体中文

## 问题与机制

网卡快不代表 P/D 交接快。KV 移动还包括定位来源、注册或中转内存、构造 descriptor、传输 shard、必要时转换布局，以及在 D 读取前让完成状态可见。多个 producer 还可能汇聚到同一 consumer，或与专家流量争用链路。

普通全注意力 GQA 的逻辑缓存字节数近似为 `K = 2*S*L*H_KV*d*b`。S 为 token 数，L 为层数，H_KV 为 KV head 数，d 为 head dimension，b 为每元素字节数，系数二表示 K 和 V。此式未计 allocator padding、scale 元数据、复制和传输封装；MLA、滑动窗口及混合状态模型应使用真实表示。

算术例子：S=32768、L=32、H_KV=8、d=128、BF16 b=2，得到 4 GiB。即使有效路径理想地达到 50 GB/s，也需约 86 ms。每秒 10 个这样的请求约需 43 GB/s，几乎没有余量。FP8 KV 可使元素字节数约减半，但还要考虑 scale、转换和质量；FP8 权重本身不会改变这项计算。

可将传输记为 `T_X = Q_X + setup + pack + K/B_effective + unpack + completion`。有效带宽取决于消息大小与竞争流量，不是网卡线速。分块和逐层重叠可减少暴露在关键路径上的时间，但会延长 buffer 生命周期。KV shard 尚不可用就启动 D，只是把传输等待变成解码停顿。

## 硬件与生命周期成本

应明确 GPU/NIC 亲和性、NUMA、PCIe 和 rail 数。Device-to-device RDMA 与 pinned host memory 中转 TCP 不同；后者增加 GPU↔host 复制、主存带宽竞争和 buffer。节点内 NVLink 又是另一类路径。并发增加能提高利用率，也可能在某个点之后放大排队并干扰计算。

Producer 保留源 page，直到传输完成确认不再读取它；consumer 保留目标 page 供解码使用。失败或取消后，应等待传输停止再重用两端 buffer。不同 TP 布局可能要求重排或重复发送；拓扑兼容的放置可能比替换更快后端更有效。不能默认 connector 支持任意 TP、KV dtype 或模型状态组合。

## 公开证据与集成

核对日期为 2026-10-14。[NIXLBench README](https://github.com/ai-dynamo/nixl/blob/01656768741dc87922a2045feff72921e193d981/benchmark/nixlbench/README.md)在 `01656768`（2026-10-13）提供 pairwise、many-to-one、one-to-many 模式，DRAM/VRAM、后端选择和延迟分位数。它是传输测量工具，不证明服务层重叠已经有效。

2026 年 [AFD 设计空间论文](https://arxiv.org/html/2605.28302v1)用 AstraSim 显式建模拥塞和计算／通信重叠。450 与 25 GB/s 的放置比较属于 NVLink／InfiniBand 模型条件，不是可以直接移用的实测 KV 加速。[MegaScale-Infer](https://arxiv.org/html/2504.02263)测量 BF16 MoE M2N 通信，解释完成通知、CPU proxy、小消息和流量效应；逐层 activation 流量与一次 P/D KV 传输并非同一 payload。

Foretoken 的[E/P/D 部署文档](../../../../examples/encoder-prefill-decode/README_zh.md)明确默认 Mooncake RDMA、可选 host-staged TCP，而该示例 encoder 状态走共享存储。[执行工作流](../../../../data-plane/frontend/src/server/src/runtime/workflow.rs)保留跨阶段清理。

## 实验与剩余问题

先从模型真实 KV 布局生成消息，分别测 setup 和稳态，扫描大小、shard 数和 fan-in。加入并发计算，再加入竞争 EP 流量。记录 p50/p99、有效字节/s、主机复制、pinned memory 压力和注册复用；单对峰值不能解释 many-to-one 服务停顿。

真实 P/D 负载比较支持的节点内、跨节点 RDMA、TCP 路径，固定模型、权重／KV dtype、TP 和命中分布。把传输完成事件关联到客户端 TTFT，测 D 停顿和源 page 保留时间。加入取消与 peer 丢失，检查最终清理，不把失败请求更早结束算作加速。拥塞感知配对、大小感知传输准入、KV 与专家流量联合调度仍是研究问题；其他网络机制见[并行与通信](../parallelism-communication/README_zh.md)。

[返回分离式推理服务](README_zh.md)
