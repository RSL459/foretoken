<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Multi-model execution with elastic physical memory

English | [简体中文](shared-model-execution_zh.md) | [Multiple models and adapters](README.md)

## Sharing a device is not sharing a base model

Distinct full checkpoints usually need distinct weights and KV semantics. Multi-LoRA batches share one base GEMM; multi-model colocation generally does not. The problem is reclaiming idle reservations so another model can expand, while avoiding constant weight swaps during interleaved traffic. Prism's final OSDI 2026 paper combines space sharing and time sharing through GPU memory ballooning. The public kvcached driver provides reusable elastic-KV infrastructure.

Prism's final paper describes the broader scheduling and activation system; kvcached provides an independently versioned driver. The research prototype and current driver have different graph and prefix-cache configurations.

## One model expands while another becomes idle

An engine reserves a stable virtual address range for its KV tensors. Physical pages are mapped when actual token blocks need storage. When blocks are freed, empty pages can be returned to a buffer or released, allowing another engine to map its own physical memory without changing its logical tensor addresses. Different models keep separate KV contents and layout semantics; shared physical capacity does not imply shared token states.

Prism's balloon driver also coordinates model-weight and KV memory demand. Idle-model eviction frees weight residency, while low-load resident models can shrink unused KV reservations. Reusable engine pools preserve initialization and distributed contexts across model activations. For weight loading, the final paper partitions tensors across node GPUs, transfers in parallel, then aggregates via NVLink with bounded streaming buffers. That fast activation path is separate from the KV allocator.

A capacity relation is sum_j(W_j+K_j+A_j)+R≤C, where W is resident weights, K physical KV, A activations/workspace, R runtime reserve, and C device capacity. Virtual reservation is not another physical K term. If all models peak simultaneously, elasticity cannot make the sum disappear; admission and placement still determine which latency targets are achievable.

The paper uses demand-complementary placement and local slack-aware arbitration to protect memory headroom and avoid uncontrolled contention.

## Current availability, models, and precision

The final paper reports NVIDIA H100 evaluation across heterogeneous model sizes and architectures. Current kvcached's checked README documents version 0.1.6, tested vLLM through 0.30.0 and SGLang through 0.5.20, including hybrid attention and an AMD/ROCm path. That does not establish compatibility with every newer engine, layout, or accelerator. Its AMD path defaults to non-contiguous KV because the backend expects that layout.

Use each model's released checkpoint, tokenizer, and configuration independently; no new model training is required. Quantized weights, FP16/BF16 KV, hybrid attention state, and different TP layouts change physical block geometry. The current driver documents automatic page enlargement for blocks that do not fit the ordinary physical page, making page size an actual layout concern rather than an arbitrary tuning constant.

ServerlessLLM supplies a complementary loading foundation: loading-optimized checkpoints, pinned buffers, direct I/O, and token-replay migration in its original design. Replay and direct KV transfer have different costs and correctness conditions. Faster loading alone does not establish better steady-state multitenant execution.

## Experiments that separate memory and scheduling

Replay at least three traffic patterns: alternating model bursts, partially overlapping bursts, and simultaneous peaks. Compare dedicated engines, fixed colocated memory partitions, elastic KV alone, and elastic KV plus model activation. Keep models, precision, serving limits, and total device capacity matched.

Measure per-model TTFT/TPOT tails, SLO-qualified goodput, physical mapped bytes, virtual reserved bytes, weight/KV/workspace bytes, page operations, activation and migration time, HBM and PCIe/NVLink traffic, preemption, and failed requests. Include a long-context model and a hybrid-state model so the allocator's layout assumptions are visible. Confirm that preserved virtual addresses remain valid through graph replay and that prefix-cache behavior matches the selected engine version.

If elastic KV improves alternating demand but fails at simultaneous peaks, capacity—not allocator overhead—is the limit. If activation consumes bandwidth needed by a resident decoder, include that interference in cost per successful request. Remaining research concerns workload-aware memory arbitration and interference on supported current engines.

## Sources and checked state

Checked 2026-10-14.

- [Prism, OSDI 2026](https://www.usenix.org/conference/osdi26/presentation/yu-shan), [final PDF](https://www.usenix.org/system/files/osdi26-yu-shan.pdf): final methods and evaluation, including memory ballooning, engine reuse, and loading; published July 2026.
- [kvcached at `94d117c`](https://github.com/ovg-project/kvcached/tree/94d117c1e2d6e6c190223e1de35d38e1882c7acb): full README, commit dated 2026-10-13; existing plugin support and version/layout limits retained.
- [Prism research prototype](https://github.com/Multi-LLM/prism-research): execution examples and stated prototype scope; not substituted for the current driver or final paper.
- [ServerlessLLM original method, arXiv:2401.14351v1](https://arxiv.org/html/2401.14351v1) and [current repository](https://github.com/ServerlessLLM/ServerlessLLM): loading and migration mechanisms.
