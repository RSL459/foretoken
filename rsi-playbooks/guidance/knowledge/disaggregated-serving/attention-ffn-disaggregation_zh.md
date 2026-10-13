<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Attention–FFN 分离

[English](attention-ffn-disaggregation.md) | 简体中文

## 问题与执行过程

稀疏 MoE 解码时，每个专家只分到一个批中的少量 token，而每个 attention 副本又同时保存专家权重和请求 KV。Attention–FFN 分离（AFD）让两部分在不同设备上运行：多个 attention worker 汇聚成更大的专家批，同时把 attention 侧显存留给 KV。

若批大小为 B、每 token 选择 k 个专家、E 个专家分配均衡，平均每个专家得到 `B*k/E` 个 token。B=256、k=8、E=128 时仅有 16 个；汇聚四个这样的批可提高到 64 个。但实际路由偏斜会让最忙专家显著超载。这说明了权重读取摊销的机会，不能直接当作延迟预测。

每个 token 仍需在每个 MoE 层经历 attention→dispatch→FFN→combine。把大批拆成微批，使一个微批的 attention 与另一个的 FFN、通信重叠。关键路径取决于 attention 时间 T_A、专家时间 T_F、dispatch/combine 和同步，不是把总时间简单除以微批数。更多微批能隐藏等待，也可能降低 GEMM 效率并增加 padding。

FastAFD coordinator 生成对齐的 attention-group 与 expert-group 计划。空闲 attention lane 使用 dummy batch 保持集合通信顺序，共用 dispatch bucket 保持 graph／通信形状兼容。Attention scheduler 分配 KV page，prefill 按 token 工作量拆分，decode 按请求数拆分。Expert worker 用 CUDA event 编排 dispatch→expert→combine，或走持久化 MegaMoE 路径。完成后释放 page，只为真实请求生成输出。持久化专家路径与可 graph-capture 的非持久化路径不是同一机制。

## 硬件、模型与公开证据

[FastAFD 技术报告](https://haoailab.com/blogs/fastafd/)在 GB200 NVL72 的统一 NVLink/NVSwitch 域上测量 Qwen3-235B-A22B-FP8、MiniMax-M2.5-FP8，使用 8K／16K 上下文、两个微批和约 0.85 的 KV 利用率。报告相对调优后的 colocated vLLM，包含专家 GPU 后的每 GPU 解码吞吐提高约 1.35–1.45 倍。主要收益之一是移除专家权重后增加 KV 驻留容量。这不是 Foretoken 的到达驱动端到端结果，也不是跨节点 RDMA 结果。

[MegaScale-Infer 论文](https://arxiv.org/html/2504.02263)推导 ping-pong 调度，并在 Ampere 和 H20/L40S 上评估 BF16 MoE。其模型要求 attention／专家计算时间近似平衡，且微批足够覆盖通信；因此不能把其三／四微批条件与 FastAFD 实测的两个微批混为一谈。

2026 年[设计空间论文](https://arxiv.org/html/2605.28302v1)把实测后端成本与 AstraSim 网络模型结合，分析 B200 上的 FP8 MoE。严格 SLO 结果和极端 A:F 比例是模型估计，不是 FastAFD 的物理 NVL72 解码测量。论文也发现 aggregate 可能占优吞吐前沿，而 AFD 更有利于交互速度。

## 实现与集成范围

核对日期为 2026-10-14。FastAFD 在 `3c71619` 上是独立 `minisgl` runtime；已读[coordinator](https://github.com/hao-ai-lab/FastAFD/blob/3c7161949310b6d59d6b4cf9bf997a4935c8113b/python/minisgl/afd_coordinator.py)、[scheduler](https://github.com/hao-ai-lab/FastAFD/blob/3c7161949310b6d59d6b4cf9bf997a4935c8113b/python/minisgl/afd_scheduler.py)、[expert worker](https://github.com/hao-ai-lab/FastAFD/blob/3c7161949310b6d59d6b4cf9bf997a4935c8113b/python/minisgl/afd_expert_worker.py)。Scheduler 明确要求 naive KV cache，不能从吞吐脚本推断前缀缓存或生产扩缩容能力。

设计空间论文引用的 [vLLM PR #29772](https://github.com/vllm-project/vllm/pull/29772)，本次 GitHub 核对为 CLOSED，merge 时间与 commit 均为空。这只说明该 PR 的状态，不代表当前 vLLM 所有 AFD 工作都未合并。Foretoken 现有的[E/P/D 工作流](../../../../data-plane/frontend/src/server/src/runtime/workflow.rs)属于请求阶段编排，不是逐层 AFD。

## 实验与剩余问题

计时前先用 FastAFD `scripts/validate/` 做输出对齐。扫描 A:F 分配、批占用、上下文和微批数，分别关闭重叠、替换融合通信路径。记录专家 token 偏斜、graph padding、逐层空闲和包含所有 GPU 的吞吐。

真实服务再加入混合到达、prefill/decode 干扰、取消和长尾上下文。在相同 GPU 预算和延迟目标下比较，不只比较最大驻留批。NVL72 之外的网络拥塞、前缀状态集成、动态专家副本和集合参与者安全调整，仍是后续问题。较慢容量决策见[扩缩容与放置](../autoscaling-placement/README_zh.md)。

[返回分离式推理服务](README_zh.md)
