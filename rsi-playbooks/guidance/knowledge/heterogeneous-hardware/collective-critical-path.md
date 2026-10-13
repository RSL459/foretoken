<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Collectives on the critical path

English | [简体中文](collective-critical-path_zh.md)

Tensor and expert parallelism can move the bottleneck from GEMM to communication. The fastest isolated all-reduce is not always the best serving choice: collectives consume device resources, impose rank ordering, and may compete with the very computation they are intended to overlap.

## Message size changes the useful algorithm

A rough communication model is `T = α × steps + bytes/β`, where α is per-step latency and β is effective bandwidth. A ring all-reduce moves roughly `2(p−1)/p` times the payload per rank, but its step count grows with rank count p. Small decode messages can be latency dominated; large prefill messages are more sensitive to bandwidth and channel utilization.

For a BF16 activation matrix with hidden width 4096, one token occupies 8192 bytes, while 1024 tokens occupy 8 MiB. These are illustrative payload sizes, not a claim that every layer uses a single collective of that shape. Sequence parallelism, fused projections, and expert routing can change both message size and count. Increasing channels to improve the large case can consume more execution resources or add overhead in the small case.

The end-to-end critical path also includes packing, dispatch, GEMM, combine, and waiting for the slowest rank. A useful overlap estimate is

```text
T_stage ≈ max(T_compute, T_comm) + T_unoverlapped.
```

It applies only when the work really runs concurrently without slowing either component excessively. Launching a collective on another stream does not prove overlap. Unequal expert token counts can leave the slowest rank computing after all other ranks have completed communication.

## Backend libraries are separate implementations

NCCL, RCCL, and MCCL provide analogous collective interfaces but use different device kernels, topology discovery, transport paths, and graph semantics. Current RCCL development lives in ROCm's consolidated `rocm-systems/projects/rccl`; historical repositories are not the source of every current fix. AMD's vLLM guide already documents Quick Reduce, ROCm all-gather/reduce-scatter expert communication, and topology-aware parallel placement. Its recommended channel settings are workload guidance, not portable defaults for another library.

The checked MetaX communicator already installs backend-specific all-to-all managers and routes MACA all-gather through the base process-group path. An optimization must preserve the actual communicator and tensor movement, rather than replace it with a faster-looking direct wrapper whose ordering differs. The same rank set can participate in more than one communicator; their operation counters are not interchangeable.

Quantized collectives are another distinct choice. Reduced transfer bytes can improve bandwidth-limited communication but add quantization work and numerical error. AMD's guide describes supported Quick Reduce low-bit modes. That is existing functionality, not a proposal to invent a new compressed collective. Eligibility and quality must be established for the target model and reduction.

## Remaining design space and measurement

Useful work includes choosing supported algorithms by actual message distribution, reducing unnecessary layout copies, finding uncovered overlap, and balancing compute versus communication resource use. It does not include transplanting vendor environment variables indiscriminately. BF16/FP16 payloads, quantized reductions, TP collectives, and EP dispatch/combine need separate analysis.

Start with the library's existing collective benchmark at the real rank count and message sizes. Add the preceding/following model stage using its real stream and communicator. Compare communication alone, computation alone, and their overlap; record device completion, rank imbalance, packing traffic, and output error. An isolated bandwidth gain that slows GEMM is a negative stage result.

At service level, compare TPOT and TTFT at both low concurrency and the intended traffic mix. Inspect successful token throughput, tail latency, output quality, and progress across all ranks. A faster collective can improve capacity but not latency when another rank remains the bottleneck.
## Sources

Checked 2026-10-14; source identities are in the [category index](README.md).

- [Current ROCm systems source](https://github.com/ROCm/rocm-systems/tree/f1b316f12c75430787032e99405834f59a026ae1/projects/rccl).
- [AMD communication and Quick Reduce guidance](https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/optimization/vllm-v1-optimization.html).
- [MetaX communicator and all-to-all selection](https://github.com/MetaX-MACA/vLLM-metax/blob/cec91763dbe968fe4478fc066f57ecf5877c3965/vllm_metax/distributed/device_communicators/cuda_communicator.py).
- [NCCL graph and rank-participation contracts](https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/usage/cudagraph.html).

[Heterogeneous execution](README.md) · [Parallelism/communication](../parallelism-communication/README.md) · [Knowledge index](../README.md)
