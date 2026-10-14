<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Balance Pipeline Latency and Throughput Through Microbatching

English | [简体中文](balance-pipeline-latency-and-throughput-through-microbatching_zh.md)

## Problem and current boundary

Pipeline parallelism (PP) partitions layers instead of splitting every weight matrix. It can fit a model across nodes and keep frequent tensor-parallel collectives within each node. But reducing collective frequency does not guarantee lower single-request latency: one request still traverses all stages, and autoregressive feedback adds a dependency before its next token.

vLLM already supports PP, combined TP/PP, and uneven layer splits. Its official deployment guide recommends considering PP on systems without fast NVLink connections. DeepEP main also exposes an experimental RDMA-only `PPBuffer`. These are implemented facilities with different integration scopes. A faster send/receive primitive alone does not provide a serving scheduler or remove pipeline bubbles.

## Execution mechanism

Stage zero receives request inputs and executes its assigned layers. It sends intermediate activations to stage one, which continues computation, and so on. The final stage produces logits and a sampled result. To continue the same autoregressive request, the next token and relevant scheduling state must return to the input-side execution path before the next forward.

Independent requests or legal microbatches can occupy different stages simultaneously. For `P` equally timed stages, `M` independent forward microbatches, and stage time `t`, an ideal forward-only pipeline takes `(M+P-1)*t`; aggregate stage utilization is `M/(M+P-1)`. This ignores transfers, unequal stage cost, and service scheduling. It is not a training 1F1B formula and not a claim about vLLM's actual schedule.

With `P=4,M=1`, the single microbatch traverses four stages serially. With eight independent microbatches, the ideal schedule uses eleven stage-time slots. These examples explain fill/drain cost; they do not predict latency under continuous arrivals. More in-flight work can improve throughput while increasing how long an individual request waits.

Prefill chunks from one sequence have cache and attention dependencies. Decode tokens from one sequence depend on prior sampling. Treating either as arbitrary independent microbatches can violate the model's execution order. A training pipeline schedule that overlaps backward work does not apply to inference without an entirely different source of independence.

Stage boundaries also own activation shapes and cache state. Each stage retains KV for its attention layers, and intermediates may include residual streams or model-specific tensors, not merely one generic hidden vector. Moving a layer changes weights, cache capacity, and stage timing together.

## Conditions and trade-offs

Equal layer counts are not equal stage times. Embeddings, output projection, attention at different history lengths, and MoE skew can create a bottleneck stage. Uneven splits can improve balance but must use the target engine's supported partitioning rather than arbitrary module relocation.

At low concurrency, PP is often primarily a capacity or topology choice. At high concurrency, independent work can fill the pipeline. Small activation transfers may be latency-bound even over RDMA, and graph coverage plus launch skew can influence stage handoffs. Pipeline depth increases failure and cancellation coordination requirements.

The cited DeepEP PP API requires an RDMA-only pipeline group, contiguous CUDA tensors, 32-byte pointer/size alignment, and preconfigured maximum tensor bytes and in-flight slots. Its experimental status does not establish drop-in replacement of the engine's existing PP communicator. Backend-specific communication belongs inside that engine boundary.

## Experiments and service validation

Compare pure TP, TP within nodes plus PP across nodes, and feasible uneven PP splits at an identical total GPU budget. Run concurrency one, enough independent requests to fill stages, and bursty arrivals with heterogeneous lengths. Measure each stage's compute, transfer wait, queueing, and cache headroom; identify the slowest stage rather than averaging utilization.

If throughput improves but single-request TPOT worsens, that is the expected distinction between pipeline occupancy and serial traversal. If a faster transport does not improve end-to-end time, check stage imbalance and scheduling dependencies. Separate startup model loading from steady-state serving.

Validate outputs and multi-turn cache growth, then check client TTFT/TPOT, success counts, output lengths, and cancellation while requests span stages. Profile separately from unprofiled speed comparisons.
## References

vLLM [parallelism guide at 6849ca69](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/serving/parallelism_scaling.md); DeepEP [main README at 93eb6eb2](https://github.com/deepseek-ai/DeepEP/tree/93eb6eb238127e96c6d7a4a625a6dad158348509), PP interface and constraints. Remaining work is target-engine stage tracing, balanced partition selection, and workload-aware measurements. See [TP granularity](reduce-tp-synchronization-through-shape-aware-collective-selection.md) for the communication PP replaces.
