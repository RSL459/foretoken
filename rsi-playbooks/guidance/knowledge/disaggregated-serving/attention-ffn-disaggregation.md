<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Attention–FFN Disaggregation

English | [简体中文](attention-ffn-disaggregation_zh.md)

## Problem and execution

In sparse MoE decode, each expert receives only a small fraction of a batch, while every attention replica holds expert weights alongside request-local KV. Attention–FFN disaggregation (AFD) places attention and expert execution on different devices: multiple attention workers aggregate work into fewer, larger expert batches and free attention-side memory for KV.

For B tokens, top-k routing and E balanced experts give approximately `B*k/E` tokens per expert. With B=256, k=8, E=128, that is only 16 tokens. Aggregating four such attention batches gives 64 per expert, although skew can leave the busiest expert much more loaded. This arithmetic explains a possible weight-amortization benefit; it does not predict latency by itself.

A token still traverses attention→dispatch→FFN→combine at every MoE layer. Split the batch into microbatches so attention for one overlaps FFN and communication for another. The critical path depends on attention time T_A, expert time T_F, dispatch/combine time, and synchronization—not merely their sum divided by batch count. More microbatches can hide waits but reduce GEMM efficiency and increase padding.

FastAFD's coordinator builds aligned attention-group and expert-group plans. Inactive attention lanes receive dummy batches to preserve collective order; a common dispatch bucket keeps graph and communication shapes compatible. The attention scheduler allocates KV pages and splits prefill by token work, decode by request counts. The expert worker executes dispatch→expert→combine with CUDA events, or a persistent MegaMoE path. Completion retires pages and detokenizes only real requests. The persistent expert path is distinct from graph-captured nonpersistent execution.

## Hardware, models, and reported evidence

[FastAFD's technical report](https://haoailab.com/blogs/fastafd/) evaluates Qwen3-235B-A22B-FP8 and MiniMax-M2.5-FP8 on GB200 NVL72 with a shared NVLink/NVSwitch domain, 8K/16K contexts, two microbatches, and KV utilization near 0.85. It reports approximately 1.35–1.45× per-GPU decode throughput over tuned colocated vLLM, counting expert GPUs. Much of the gain is additional KV residency after removing expert weights. This is not an end-to-end arrival-driven Foretoken result or an inter-node RDMA result.

The [MegaScale-Infer paper](https://arxiv.org/html/2504.02263) derives ping-pong scheduling and evaluates BF16 MoE on Ampere and H20/L40S hardware. Its model requires approximately matched attention/expert times and enough microbatches to cover communication; those conditions explain why its three/four-microbatch choices differ from FastAFD's measured two.

The 2026 [design-space paper](https://arxiv.org/html/2605.28302v1) combines measured backend costs with AstraSim network modeling for FP8 MoE on B200. Its strict-SLO results and extreme attention/FFN ratios are modeled configurations, not the same evidence as FastAFD's physical NVL72 decode experiments. It finds aggregate serving can win throughput frontiers while AFD improves interactivity.

## Implementation and integration scope

Checked 2026-10-14. FastAFD is an independent `minisgl` runtime at `3c71619`, with inspected [coordinator](https://github.com/hao-ai-lab/FastAFD/blob/3c7161949310b6d59d6b4cf9bf997a4935c8113b/python/minisgl/afd_coordinator.py), [scheduler](https://github.com/hao-ai-lab/FastAFD/blob/3c7161949310b6d59d6b4cf9bf997a4935c8113b/python/minisgl/afd_scheduler.py), and [expert worker](https://github.com/hao-ai-lab/FastAFD/blob/3c7161949310b6d59d6b4cf9bf997a4935c8113b/python/minisgl/afd_expert_worker.py). Its scheduler asserts naive KV caching; prefix-cache and production autoscaling behavior cannot be inferred from its throughput presets.

The design-space paper references [vLLM PR #29772](https://github.com/vllm-project/vllm/pull/29772). GitHub reports CLOSED, with no merge time or merge commit, at this check. That describes this PR only, not all AFD work in current vLLM. Foretoken's existing [E/P/D workflow](../../../../data-plane/frontend/src/server/src/runtime/workflow.rs) is request-stage orchestration, not per-layer AFD.

## Experiments and remaining questions

Use FastAFD's `scripts/validate/` alignment comparisons before timing. Sweep attention:expert allocation, batch occupancy, context length, and microbatch count; disable overlap and substitute the unfused communication path separately. Measure expert token skew, graph padding, per-layer idle time, and throughput per total GPU.

For a real service, add mixed arrivals, prefill/decode interference, cancellations, and long-tail contexts. Compare equal GPU budgets and latency targets, not only maximum resident batches. Remaining questions include congestion outside NVL72, prefix-state integration, dynamic expert replication, and safe resizing of collective participants. See [autoscaling and placement](../autoscaling-placement/README.md) for slower capacity decisions.

[Back to disaggregated serving](README.md)
