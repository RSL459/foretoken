<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 循环 decode 与 speculative commit 的 replay 缓冲区

[English](recurrent-speculation-replay.md) | 简体中文

## 问题与当前上游

循环层为每个请求保留矩阵，而不是逐 token KV。普通 decode 每步读写完整矩阵，speculative verify 还可能保存各位置的中间状态，以便拒绝时恢复 accepted prefix。高 batch 下，即使状态大小已经与历史长度无关，这些字节仍可能主导执行。

2026-10-09 的 ReplaySSM 论文将状态表示为 checkpoint 加近期输入记录。SGLang 已在 6 月 26 日合并普通 decode PR #28451，7 月 20 日合并 speculative PR #28695，承接此前公开工作；独立的 compact-cache PR #27658 在核对时仍开放。剩余机会是具体负载下的表示与生命周期成本。

## 机制：不必每步物化整个状态

使用 value-first 布局，状态 `S` 形状为 `[V,K]`，`V` 和 `K` 分别是 value 与 key 维度。列向量 `v_t`、`d_t` 长度为 `V`，`k_t` 和包含输出缩放的 query `q_t` 长度为 `K`；标量 `alpha_t`、`beta_t` 分别控制遗忘和更新强度。GDN 更新可写成：

```text
d_t = beta_t * (v_t - alpha_t*S_previous*k_t)
S_t = alpha_t*S_previous + d_t*transpose(k_t)
o_t = S_t*q_t
```

从 checkpoint `S0` 后累计 `h` 条记录，状态为：

```text
S_h = (product_i alpha_i)*S0
    + sum_j (product_{i>j} alpha_i)*d_j*transpose(k_j)
```

输出只需要 `S_h*q`，并不需要把 `S_h` 全部写到显存。内核读取 `S0`，计算与 query 的乘积，再加缓冲中的低秩贡献；每累计 `L` 条已提交记录，flush 才将它们合并为新 checkpoint。这摊薄了完整状态写回，但每步仍会读取 checkpoint。

GDN 的 `d_t` 依赖前一状态，因此 verify chunk 中的修正需要三角变换联合求解，不能把 draft 记录当作独立加法。假设验证三个 draft，只提交前两个，下一状态就是 checkpoint 历史加这两条记录；第三条位于 committed cursor 之外，之后可覆盖，无需保存第三位置的完整快照。accepted length 是否包含 bonus token 必须有明确约定。

flush 顺序是正确性的一部分：被拒绝记录不能进入永久 checkpoint。前缀缓存发布也可能在窗口未满时强制物化。本次核对的 SGLang 用环形 cursor、request slot、raw input cache 和 accepted length 将论文适配到服务中，并非论文内核的逐字复制。

## 适用条件与取舍

这主要针对较大循环状态、足够 batch 下的带宽成本。batch-one decode 可能受 launch 或计算限制，replay 增加的工作反而超过省下的写回。若 hybrid 模型主要耗时在 MoE 或全注意力，GDN 内核明显加速也可能只有很小的端到端收益。

增大 `L` 降低 flush 频率，却增加缓冲读取和重建工作。Mamba-2 与 GDN 使用标量 decay；KDA 的通道 gate 需要另行推导 replay。状态布局、激活 dtype、checkpoint 精度和 dot-product 精度也会改变实际内核路径。

论文还把高精度 recurrence checkpoint 与较低精度的输出读取 checkpoint 分开。GDN 保留原始 `v_t` 输入，让 flush 从高精度 checkpoint 重新求解相互依赖的 `d_t`，而不是沿用低精度读取算出的修正。重建后的状态再分别转换为两份 checkpoint。因此低精度读出误差影响输出，却不反馈到下一份永久 recurrence checkpoint；输出变化需要在目标模型的任务上评估。

## 实现入口与剩余设计空间

从固定版本 SGLang 的 `gdn_replayssm_spec_decode.py` 追踪到 GDN backend 和 state pool 的 cursor owner。本次核对的 verify 路径面向线性链；树状验证是另一问题。仍开放的 compact-cache PR 也不是已经合并的 replay verify 本身。

可以测量按实际 batch 分布选择 flush 时机、buffer 布局或精度分离的价值。前缀 checkpoint 导出、slot 复用、取消、graph capture 和状态传输都要理解 buffered state。只复制 `S0` 而漏掉已提交记录，会丢失近期 token。完整传输可以先物化，或一致地转移 checkpoint 与已提交记录，应由既有引擎 owner 决定表示。

## 从局部到服务的实验

对相同 initial state 和 token 流比较直接 recurrence 与 replay，覆盖 flush 边界，以及短 verify 链每个位置的拒绝。同时检查输出和 commit 后状态。加入窗口未满时导出 checkpoint、立即复用 slot 的执行，确认下一次 flush 不会重新引入被拒绝记录。

性能上分别计时 non-flush、flush 和强制发布步骤。扫描 batch、replay 长度、draft 长度和 accepted-prefix 分布，记录状态读写字节与重建时间，避免平均内核时间隐藏 flush 尖峰。

再固定 draft 机制、sampling 与内存预算，运行实际 hybrid 模型，比较 TPOT 尾延迟、成功吞吐、acceptance 和质量。加入普通 decode，区分 replay 本身与 speculation 的贡献，报告 GDN 占整个模型时间的比例，将循环内核改动与完整模型结果联系起来。

## 依据与核对状态

核对日期为 2026-10-14。

- [ReplaySSM v1](https://arxiv.org/html/2610.13778v1) 与[提交记录](https://arxiv.org/abs/2610.13778)：v1 提交于 2026-10-09，介绍 recurrence、replay、speculation 与精度分离。
- [SGLang RFC #28511](https://github.com/sgl-project/sglang/issues/28511)：已关闭，描述集成范围和依模型而异的结果。
- [PR #28451](https://github.com/sgl-project/sglang/pull/28451)：合并 commit 为 `a10a24e9a7fdc0ddcc7dc3e90c0d4983707db028`；[PR #28695](https://github.com/sgl-project/sglang/pull/28695)：合并 commit 为 `c41c573ce9ed2053d38aa711582e19a67a5e9755`；[PR #27658](https://github.com/sgl-project/sglang/pull/27658)：仍开放，不作为已发布 compact-cache 能力依据。
- [实际 verify 内核，固定 `e9400c5a8f3a0d0312a37aecef694f5edfd69341`](https://github.com/sgl-project/sglang/blob/e9400c5a8f3a0d0312a37aecef694f5edfd69341/python/sglang/kernels/ops/attention/fla/gdn_replayssm_spec_decode.py)：环形 replay、folding、commit 约定与精度路径。
