<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Prevent pipeline backlogs through joint stage-capacity allocation

English | [简体中文](prevent-pipeline-backlogs-through-joint-stage-capacity-allocation_zh.md)

## Problem and mechanism

Adding encoder or prefill workers can make a service slower when their outputs arrive faster than downstream capacity can consume them. Multistage serving needs a balance across computation, state transfer, admission, and state retention. This is a pipeline-capacity problem, not an encoder-kernel optimization.

Represent the request path as E→P→X→D, where X is KV transfer. A first approximation is `λ < min(n_E μ_E, n_P μ_P, μ_X, n_D μ_D)`. Each μ uses the same workload distribution and service unit: image-heavy encoder work cannot be compared directly with raw text tokens/s. Decode capacity must include request lifetime, context growth, and its latency target.

For an illustrative pipeline accepting 8 requests/s, E can process 12, P 10, transfer 7, and D 9. Doubling P cannot raise sustainable throughput above 7 or clear the transfer queue while arrivals remain at 8 requests/s. Under sustained overload, the transfer queue grows until admission or backpressure limits accepted work. In a stable stage, Little's law gives mean resident requests λW, where λ is the admitted rate and W the mean residence time; buffer bytes require size-weighted accounting. Long requests can dominate bytes while remaining a minority by count.

The execution sequence matters. Admit a request, run E to a completed descriptor, run P to its transfer handoff, select a compatible D, and keep intermediate resources live until their consumers finish or cancellation is confirmed. A completion barrier is not an atomic reservation of all future stages. Reserving D too early protects handoff capacity but can strand decode slots while E/P work; selecting D late improves flexibility but exposes downstream contention.

## Hardware, representation, and cost

Measure each boundary with the actual model and dtype. Encoder output is an embedding tensor or connector-defined state, not token KV. P/D transfer size depends on attention architecture, KV dtype and parallel layout. Qwen2.5-VL-3B on four GPUs, for example, is a different balance problem from FP8 Qwen3-235B MoE on a rack-scale fabric.

Separating stages adds weight copies, memory buffers, startup paths, and failure domains. A faster GPU for P may be wasted if D residency or the network is limiting. Mean service rates are insufficient for correlated bursts of large images and long prompts. Stage-specific targets should divide an end-to-end latency budget; maximizing each stage's isolated throughput is not the objective.

## References

Dynamo's [encoder-disaggregation guide](https://github.com/ai-dynamo/dynamo/blob/b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd/docs/fern/pages/use-cases/multimodal-serving/encoder-disaggregation.md) describes E/PD and E/P/D, with NIXL embedding transport; backend support differs, including TensorRT-LLM's E/P/D-only scope.

The 2026 [SARA paper](https://arxiv.org/html/2609.26763v1) models P as M/G/k, transfer as M/G/1, and D with a continuous-batching birth–death approximation. It allocates cost across compute, link bandwidth and HBM against quantile constraints. Its evaluation combines modeling/simulation with A100/SGLang measurements and considers LLaMA 3.1 8B, Qwen2.5 32B, and GPT-3 175B configurations. The trace-replay hardware experiment uses LLaMA 3.1 8B; the cited paper does not clearly identify physical runs for every model or a common evaluation dtype. No public author code link is provided. Poisson arrivals and independent length assumptions constrain applicability.

Foretoken's [maintained E/P/D example](../../../../examples/encoder-prefill-decode/README.md) uses Qwen2.5-VL-3B, shared encoder storage and Mooncake P→D transport, with independently configurable Pools. Its [runtime workflow](../../../../data-plane/frontend/src/server/src/runtime/workflow.rs) retains cleanup through E/P barriers and selects D after P. The [autoscaling owner](../../../../control-plane/internal/autoscaling/README.md) evaluates capacities separately while committing a complete serving cohort.

## Experiments and remaining questions

First simulate a tandem pipeline using empirical stage-time and output-byte distributions. Vary stage counts while keeping total GPU budget fixed, then vary transfer bandwidth independently. Compare free-running producers with downstream-aware admission. Measure queued bytes, deadline failures and buffer residency—not only completed requests.

On a real E/P/D service, hold image contents and tokenization constant while sweeping image count, text length, output length and arrival bursts. Instrument accepted, stage-completed, transfer-completed and final-output times. Include cancellation during each handoff and scale one role at a time. Faster P with unchanged end-to-end goodput identifies a moved bottleneck rather than a successful optimization. Open questions are joint capacity promises, size-aware backpressure and tail-budget allocation. Encoder execution details are in [multimodal generation](../multimodal-generation/README.md).

[Back to disaggregated serving](README.md)
