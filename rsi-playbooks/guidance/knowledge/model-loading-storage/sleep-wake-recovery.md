<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Cold, Warm and Sleep/Wake Recovery

English | [简体中文](sleep-wake-recovery_zh.md)

Recovery time depends on what survives: checkpoint files, host weight copies, a live memory owner, or request token history. “Warm” is not one state. A sleeping engine and a restarted process can have entirely different restoration paths even on the same GPU.

## Distinguish the surviving state

vLLM's [current sleep guide](https://docs.vllm.ai/en/latest/features/sleep_mode/) describes level 1 as backing weights into CPU memory while discarding KV. Wake restores those weights, but subsequent requests may need prefill again. Level 2 discards weights and KV while preserving required buffers in CPU memory. Waking allocations alone does not reload discarded weights; the documented sequence wakes weights, reloads them, then wakes KV. Partial wake is supported, but scheduling must wait for the necessary components.

An illustrative level-1 wake moves W weight bytes at effective H2D bandwidth B, giving a payload floor `W/B`. It additionally pays allocation/restoration and any request replay. Level 2 adds source loading and transformations. Keeping 40 GiB of host weight copies can reduce reload work but adds that memory pressure; a nominally faster wake that causes host reclaim or kills another process is not a complete improvement.

A live external memory owner creates a third case. vLLM's [weight-cache IPC loader](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/model_executor/model_loader/weight_cache/ipc_loader.py) can install daemon-owned CUDA IPC tensors in zero-copy mode, or clone them into engine-owned memory. Zero-copy requires the daemon to remain alive and is incompatible with sleep-mode weight offloading. Copy mode spends device memory and copy time but transfers ownership. Reuse requires matching model, parallelism, role and GPU identity; it is not a portable process checkpoint.

Dynamo's [GMS artifact implementation](https://github.com/ai-dynamo/dynamo/blob/7708f041a965e35374af976ab8ad610b9537e3bc/lib/gpu_memory_service/v1/snapshot/weight_artifact.py) saves raw allocation bytes and restores them into a fresh server. The local client and sidecar must resolve to the same physical GPU during mapping. Allocation granularity and external reconstruction metadata matter; the format itself is not a tensor-level cross-topology checkpoint, nor does that local device check alone prove artifacts cannot be restored elsewhere by a compatible consumer.

## Weights are not request recovery

[ServerlessLLM's original method](https://arxiv.org/html/2401.14351v1) reconstructs request KV by replaying input and generated tokens, with a second token update before handover. It avoids transferring full KV but spends prefill computation. Exact replay requires the same token history and model state, and preserving generated tokens is different from regenerating them with new sampling.

LMCache can retain reusable KV outside the engine, while Mooncake supplies transfer and weight-state metadata. A restarted worker still needs compatible keys, shapes and engine integration. External cache availability does not imply every in-flight request is resumable. Dynamo and ModelExpress provide additional loading paths, but replica recovery policy is a separate serving responsibility. These boundaries were checked against the [2026-10-14 snapshot](README.md#evidence-snapshot).

## Experiments and remaining questions

Locally compare cold process startup, warm filesystem startup, level-1 sleep/wake, level-2 wake with explicit reload, and supported daemon-backed reuse. Record surviving host/device bytes, transfer volume, restoration stages and next-token agreement. Also vary whether the memory-owning daemon survives. A fast zero-copy restart with a live daemon says nothing about full-node recovery.

For request restoration, hold token history and model revision fixed; compare full replay, externally restored KV and replay after a new weight revision. Inspect next-token distributions, not just whether an HTTP request succeeds. Weight changes invalidate assumptions about old KV semantics.

At service level, measure the first successful generation after restoration and the next several requests, including long-context and concurrent traffic. Record replay work and effects on co-located services. Remaining research concerns the cheapest sufficient surviving state and its lifecycle, not an unconditional promise of instant resume. No Foretoken recovery time or quality result has been measured.

[Model loading and storage](README.md)
