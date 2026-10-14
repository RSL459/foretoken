<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Low-latency MoE communication and useful overlap

English | [简体中文](low-latency-dispatch-overlap_zh.md)

## Problem and current boundary

MoE dispatch and combine can dominate decode when each rank has few tokens. Asynchronous APIs alone do not remove the dependency between dispatch and expert GEMM, or between combine and the next layer. Useful overlap requires independent work or finer producer-completion information.

DeepEP main is now V2.5 with a unified `EPBuffer`; it removed the V1 API and NVSHMEM dependency. Its current README explicitly says EP dispatch/combine use GPU SMs and zero-SM RDMA EP is not supported. vLLM already implements dual-batch overlap (DBO). Single-batch overlap (SBO) also exists in DeepEP's separate `antgroup-opt` branch.

## Execution mechanisms

Current main dispatch can run asynchronously on a communication stream and defer its epilogue. Launch dispatch, execute independent computation, then wait when expert inputs are required. The wait returns expanded inputs, routing metadata, and a handle. Expert GEMMs must respect GPU receive counts when CPU synchronization is disabled; unused capacity is not valid token data. After computing and weighting expert outputs, launch combine, execute other independent work, and wait before consuming the result. Main combine sums supplied outputs, so router weights must be applied at the documented compute boundary.

DBO obtains independent work by splitting the batch into two microbatches. vLLM's schedule alternates dispatch of one microbatch with attention or expert work from the other, then combines one while computing the other. All DP ranks must agree on the split; empty second microbatches can disable the mechanism. Full CUDA graph capture records the schedule so steady-state replay does not need the capture-time CPU thread coordination.

SBO changes granularity instead of requiring another microbatch. DeepEP PR #483 adds completion signals for blocks of expert rows. Combine-send waits with acquire semantics until the corresponding GEMM signal reaches its completion threshold, sends that block, and publishes expert completion after all relevant blocks finish. This requires a cooperating GEMM producer; a normal whole-kernel event cannot expose the same early readiness. A test that pre-fills every signal only checks the consumer, not real GEMM/communication overlap.

## Conditions and trade-offs

For one autoregressive request, one decode step supplies one new target token unless speculation or another execution mode expands it. Two useful microbatches cannot be assumed. Shared-expert computation may provide independent work, but the chosen model must actually have it. Small-batch SBO can also have too little GEMM duration to amortize signaling.

Communication and GEMM compete for SMs, HBM, shared memory, and launch resources. The relevant model is not simply `max(comm,compute)`: overlap can lengthen both components. Waiting communication blocks must not occupy all resources needed by the producer. Measure a complete layer under concurrent execution, not isolated component minima.

The checked V2.5 NVIDIA path requires Hopper or newer, CUDA Toolkit 13.1+, PyTorch 2.10+, and NCCL 2.32.3+, with NVLink within a node and RDMA across nodes. Dispatch accepts BF16 or FP8 data with scales; combine inputs must be BF16. Match the engine adapter and transport representation to this interface, including any conversion around expert computation. V1 experimental branches have different APIs and dependencies.

## Experiments and service validation

Compare serialized execution, async execution without independent work, async plus genuine independent work, DBO where eligible, and a compatible SBO branch. Sweep live tokens, microbatch balance, expert skew, and communication SM allocation at fixed model/dtype/topology. Record actual DBO activation, graph replay, dispatch readiness, GEMM slowdown, combine tail, and the slowest rank's layer duration.

If the overlap region grows while layer time rises, resource contention is the explanation. If DBO never activates at concurrency one, that is an eligibility result, not a failed implementation. For SBO, include late and uneven block completion and verify every output before reuse.

Validate full-model outputs, then compare unprofiled service TPOT/TTFT and sustained-load tails. Preserve output lengths and quality, and include mixed prefill/decode traffic rather than timing only a favorable steady-state kernel.

## Sources and status

Checked 2026-10-14: DeepEP [main 93eb6eb2](https://github.com/deepseek-ai/DeepEP/tree/93eb6eb238127e96c6d7a4a625a6dad158348509); vLLM [DBO design at 6849ca69](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/design/dbo.md); [PR #483](https://github.com/deepseek-ai/DeepEP/pull/483), merged into `antgroup-opt` rather than V2 main on 2025-11-21, merge `9f2fc4b3`. [PR #453](https://github.com/deepseek-ai/DeepEP/pull/453) was open, unmerged when checked. Remaining research is target-version integration, safe resource allocation, and measured workload eligibility.
