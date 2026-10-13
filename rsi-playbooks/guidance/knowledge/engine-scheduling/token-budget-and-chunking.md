<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Token Budgets and Chunked Prefill

English | [简体中文](token-budget-and-chunking_zh.md)

A token budget limits work in one engine iteration, not the number of requests a service can accept. The useful optimization question is how much prefill can accompany active decode without exceeding the required token-delivery interval.

## What already exists

vLLM V1 already implements chunked prefill and schedules running work before admitting waiting work. Its optimization documentation says chunked prefill is enabled whenever possible. The inspected scheduler also handles speculative tokens, encoder work, hybrid-state alignment, and KV allocation. Reimplementing basic chunking in a request router would duplicate the wrong owner.

Sarathi-Serve supplies the underlying execution argument: memory-bound decode can share an iteration with compute-heavy prefill, while bounded chunks prevent a long prompt from monopolizing the device. Its original paper is useful historical evidence, not evidence that chunking remains absent from modern vLLM. SOLA adds a distinct direction: choose the workload and ordering from observed SLO pressure rather than retain one fixed budget.

## Follow one iteration

Consider 64 active requests, each needing one ordinary decode token, and a newly arrived 8,192-token prompt. With a simplified 512-token iteration budget, 64 decode tokens leave 448 tokens for prefill. Completing that prompt takes at least 19 such iterations if the decode population remains constant. A 2,048-token budget leaves 1,984 tokens and takes at least five iterations, but each mixed iteration may stall existing streams longer. These are arithmetic examples, not measured iteration times.

The practical constraint is a profiled latency surface:

`iteration_time(decode_population, context_lengths, prefill_tokens) <= delivery_budget`.

Token count alone does not determine time. Attention work depends on existing context; MoE expert activation changes weight traffic; tensor parallelism adds communication; speculative decoding adds verification tokens. The inspected vLLM scheduler distinguishes scheduled-token capacity from its input budget and reserves draft slots. A change must preserve that accounting rather than assume every request consumes exactly one slot.

Sarathi profiles the budget against a tail time-between-tokens target and considers GPU tile-size multiples. A slightly smaller budget can be slower if it selects inefficient matrix shapes. SOLA instead monitors request latency, system memory, and fitted prefill/decode costs, then adjusts request count, token count, and execution order. Its cost model is corrected using measured iteration latency. This is a feedback loop inside the engine, not a reason to fetch Prometheus on every scheduling step.

## When tuning helps

Use this approach when arriving prefills explain decode stalls and the device still has useful compute headroom. Larger chunks can improve prefill efficiency and TTFT but increase individual decode gaps. Smaller chunks add repeated scheduling, collectives, attention reads, and, for MoE, expert-weight traffic. The [layer-group prefill note](layered-prefill.md) examines a different execution partition for that last problem.

Pure decode has no prefill work to redistribute. At high decode concurrency, decode itself may consume the latency budget. Prefix hits also change the amount of actual prefill: sweep uncached suffix length rather than treating all input tokens as equivalent. Multimodal encoders and hybrid-state models introduce additional limits, so a text-only optimal budget is not a universal default.

## Ownership and experiment

The engine owns token selection, chunk progress, KV allocation, and graph-compatible execution. Foretoken's request layer selects an instance and accounts for waiting and active requests; it should not invent per-iteration token schedules. Cluster orchestration owns replica capacity and parallelism placement. Changing replicas during a budget comparison makes attribution harder.

Run the same timestamped mixed trace with fixed output limits, sampling, model, topology, and offered load. Include isolated long prompts, bursts of long prompts, and cache-hot continuations. Compare several budgets with the current engine configuration. Record p50/p95/p99 TTFT, p99 inter-token gaps, TPOT, SLO-qualified completed requests per second, preemption count, and device memory. Inspect iteration timelines to distinguish longer kernels from CPU scheduling or communication gaps. Report rejects and timeouts alongside completions.

The remaining design space is an adaptive budget that responds to changing request shapes without oscillating or relying on optimistic latency estimates. Compare it against the best fixed budget for each workload, not an arbitrarily poor setting.
## Sources

Checked 2026-10-14. Code links identify inspected revisions; documentation follows its published latest channel.

- [Sarathi-Serve, arXiv 2403.02310v1](https://arxiv.org/html/2403.02310v1): stall-free hybrid batches, profiled token budget, and tile quantization.
- [SOLA, MLSys 2025, §§4–5](https://proceedings.mlsys.org/paper_files/paper/2025/file/bc82dbfbfa43232be85b8d9838f49c3e-Paper-Conference.pdf): iteration-level workload control and online cost correction; evaluated on a vLLM 0.4.2 integration.
- [vLLM optimization guide](https://docs.vllm.ai/en/latest/configuration/optimization/): current chunking and preemption guidance.
- [vLLM V1 scheduler, commit 6849ca69](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/v1/core/sched/scheduler.py): `schedule`, token/input budgets, and allocation constraints.
