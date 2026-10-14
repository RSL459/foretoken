<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Reduce adapter thrashing through residency-aware request dispatch

English | [简体中文](reduce-adapter-thrashing-through-residency-aware-request-dispatch_zh.md) | [Multiple models and adapters](README.md)

## Why one cache miss can affect other tenants

Dynamic adapter loading and LRU eviction already exist in serving engines. They do not guarantee graceful behavior when the active adapter set exceeds GPU slots. CLIMB, published at ICML 2026, studies a residency cliff: mandatory adapter fetches stall shared progress, and frequent misses amplify tail latency rather than causing a small linear slowdown. The interesting question is how residency and ingress jointly affect the whole queue, not whether hot loading can be implemented.

An adapter cache also competes with KV memory. Reserving more adapter slots may reduce misses but lower concurrent context capacity. Slot count alone is insufficient when ranks and target modules differ; actual allocated buffer bytes determine the memory tradeoff.

## One switch and one ingress decision

Current SGLang's memory pool first uses empty slots. When full, it selects an eviction victim excluding adapters needed by the current batch and pinned adapters. It copies compatible weights into the slot, updates UID-to-slot mappings, and clears missing module data to avoid retaining another adapter's update. Removed adapters clear their buffers; base-only replay must not read stale low-rank weights. Tensor-parallel ranks must agree on slot assignments.

CLIMB's public artifact labels `gate_rr` as its main policy. The policy tracks an active adapter set and in-flight work. It removes idle entries, fills available capacity with VIP adapters, uses remaining capacity for background adapters, and selects the oldest request among eligible active adapters. When the number of distinct VIP adapters with queued or in-flight work reaches the residency capacity, it pauses background dispatch. Separate round-robin indices advance adapter selection. The engine execution and confirmation of actual device residency are outside that policy file.

For example, with four slots and eight demanded adapters, admitting every queued request can continually force loads. Holding non-active background requests outside the engine reduces churn affecting urgent work, but does not erase their waiting. End-to-end latency must include the ingress queue.

For an adapted linear layer with input width h, output width o, rank r, and b bytes per weight element, raw adapter memory is b r(h+o), before sharding and padding. Rank 128 therefore uses sixteen times the raw A/B bytes of rank 8 for the same layer. A pool padded to maximum rank may reserve substantially more than the bytes of currently loaded tensors.

## Availability, precision, and constraints

CLIMB's artifact includes policy code, curated paper data, workload configurations, and a GPU rerun wrapper. The wrapper depends on a separately supplied full serving harness; this is not a self-contained production implementation. Its synthetic rank-128 adapters reproduce residency pressure, not trained task quality. Real experiments should obtain compatible trained LoRAs and their base checkpoint, target modules, scaling, and tokenizer information separately.

SGLang exposes pinned adapters, LRU/FIFO eviction, CPU loaded-adapter limits, and overlap loading. Overlap can reduce exposed copy time but constrain multi-adapter prefill batching. vLLM exposes runtime load/unload/replacement; TensorRT-LLM documents host/device caches.

Use actual FP16/BF16 buffer sizes and pinned-host memory accounting; base quantization does not halve every adapter buffer. PCIe transfer, host pinning, and accelerator support determine the switch cost. Prefetching an adapter that is never used can evict useful state or contend with current kernels. In-place replacement needs an explicit version/lifetime boundary so active requests do not mix old and new weights.

## Experiments and remaining space

Sweep demanded-adapter count across residency capacity while independently varying rank, burstiness, and popularity reversals. Compare ordinary engine eviction, pinning selected adapters, and residency-aware ingress with identical memory budgets. Keep the same adapter semantics; do not route a tenant to another adapter merely to improve cache hits.

Measure cold versus warm TTFT, engine-only versus end-to-end TTFT, GPU-slot occupancy, host/device bytes, cache misses, actual weight-copy duration, stalled iterations, KV capacity, queue age, and per-class SLO goodput. Include rare background traffic and report its longest wait and completion count. Cancel and replace adapters while requests are active to inspect lifetime behavior.

If engine tails improve but ingress tails worsen equally, waiting moved rather than disappeared. If more slots help until KV pressure dominates, the correct decision is a memory operating point. Remaining research concerns measured ingress/residency coordination, workload-aware prefetch, and rank-sensitive memory accounting on top of existing loaders.

## References

- [CLIMB, ICML 2026](https://proceedings.mlr.press/v306/zhang26dg.html): publication mechanism and artifact link. [Artifact](https://github.com/maxsignalll/CLIMB_artifact/tree/a96f7f3cb65b9bb86dec3d0a1f0c511705f05360) README and `policies/gate_rr.py` at `a96f7f3`, dated 2026-06-12; GPU reruns require an external serving harness; synthetic weights exercise residency pressure.
- [SGLang memory pool](https://github.com/sgl-project/sglang/blob/e9400c5a8f3a0d0312a37aecef694f5edfd69341/python/sglang/srt/lora/mem_pool.py): at `e9400c5`, dated 2026-10-13; [runtime documentation](https://docs.sglang.io/advanced_features/lora.html).
- [vLLM LoRA](https://docs.vllm.ai/en/latest/features/lora/) and [TensorRT-LLM LoRA](https://nvidia.github.io/TensorRT-LLM/advanced/lora.html): current loading/cache documentation; TensorRT-LLM main at `31c1a3f`, dated 2026-10-13.
