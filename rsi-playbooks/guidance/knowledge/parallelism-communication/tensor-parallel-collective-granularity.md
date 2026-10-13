<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Tensor-parallel collectives at the right granularity

English | [简体中文](tensor-parallel-collective-granularity_zh.md)

## Problem and current boundary

Tensor parallelism (TP) splits weights to fit or accelerate a model, but introduces repeated synchronization inside each layer. Small decode messages may be latency-bound; large prefill messages may be bandwidth-bound. Increasing TP can shrink local matrix multiplies while increasing the fraction spent on collectives.

vLLM already provides custom all-reduce, all-gather, and reduce-scatter selection alongside other communicator paths. The checked source includes MNNVL-specific all-gather/reduce-scatter and low-SM multimem reduce-scatter. It is no longer accurate to describe every custom collective as strictly single-node, but this does not make legacy IPC all-reduce a general RDMA implementation. The research question is matching message shape and topology to the existing selection path.

## Execution mechanism

A column-parallel projection computes disjoint output-feature slices. A subsequent row-parallel projection computes partial sums over input-feature slices. To produce replicated outputs, ranks sum those partials with all-reduce. Alternatively, when the consumer can retain a token shard, reduce-scatter produces only that shard, with a later all-gather where full rows are required. This changes tensor ownership between stages; replacing an operation without changing its consumer is incorrect.

For `T` tokens, hidden width `H`, and element size `s`, one replicated activation contains `B=T*H*s` bytes. An ideal ring all-reduce communicates approximately `2*(p-1)/p*B` bytes per rank for `p` ranks. This is a bandwidth model, not a latency prediction: launch, synchronization, topology, and protocol matter, especially when `T=1`.

In the checked `CustomAllreduce`, eligibility includes dtype, byte alignment, contiguity, group size, and peer connectivity. Legacy custom all-reduce's selector rejects more than eight ranks even though the enclosing object supports additional sizes for other operations. In eager mode it copies into registered buffers; captured paths can use registered graph addresses. A graph/eager comparison therefore changes communication preparation as well as CPU launch overhead.

The MNNVL reduce-scatter selector chooses between Lamport, multimem, or another communicator based on supported architecture, sizes, and initialized multicast storage. An ordinary multi-node InfiniBand cluster is not an MNNVL domain. Some paths deliberately avoid switching under batch-invariant mode because numerical behavior can depend on the algorithm.

## Conditions and trade-offs

Compare fixed model precision and reduction behavior. FP16/BF16 inputs, FP32 inputs, and quantized local GEMM outputs do not imply the same accumulation contract. More ranks can improve weight capacity yet increase launch and coordination costs. Different backend eligibility can create apparent performance cliffs at token or byte thresholds.

Keep frequent TP communication within a fast interconnect when possible; pipeline stages can cross a slower boundary, but that exchanges TP synchronization for stage dependencies and bubbles. Do not assume the largest TP degree is the best single-request configuration.

Collective bucketing can reduce launch count only for independently ready operations. Two reductions separated by a dependent nonlinear layer cannot simply be combined. Larger buckets also delay the first consumer and require buffer lifetimes that survive until completion.

## Experiments and service validation

Replay actual collective shapes from the model, including one-token decode, speculative verification, and chunked prefill. Sweep TP degree with the same total GPU budget where meaningful, record chosen kernels and network paths, and compare registered graph execution with eager execution separately. Use isolated collective measurements to locate thresholds, then measure full layers with surrounding GEMMs.

If a microbenchmark improves but layer time does not, inspect launch preparation, synchronization placement, and compute interference. If latency jumps at a shape boundary, verify backend selection before attributing it to model arithmetic. Include ranks starting unevenly rather than synchronizing away service launch skew.

Run full-model service comparisons for TP/PP alternatives using identical workloads and quality checks. Record concurrency-one TPOT, TTFT for long prompts, sustained throughput, client tails, and KV capacity.
## Sources and remaining work

Checked 2026-10-14: vLLM [custom collective source at 6849ca69](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/distributed/device_communicators/custom_all_reduce.py), read in full, and [parallelism deployment documentation](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/serving/parallelism_scaling.md). Existing selectors and MNNVL paths are implemented. Remaining work is measuring target shapes and topology, not first-time custom collective support. See [pipeline bubbles](pipeline-microbatch-bubbles.md) before moving TP communication across nodes.
