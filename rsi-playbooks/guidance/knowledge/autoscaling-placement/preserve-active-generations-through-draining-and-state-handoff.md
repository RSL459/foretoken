<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Preserve active generations through draining and state handoff

English | [简体中文](preserve-active-generations-through-draining-and-state-handoff_zh.md)

## Problem and mechanism

Removing a decode worker can interrupt minutes of generation and discard warm KV. Scale-down must distinguish stopping new work, completing accepted work, moving active requests, and retiring reusable cache. A slower replica decrement is not itself a drain protocol, and a persistent prefix cache is not a resumable request checkpoint.

Natural drain follows a sequence: close admission, withdraw the route, confirm routing observers have installed the withdrawal, wait for accepted requests to finish, then release resources. Closing admission first protects against stale routers. A bounded deadline prevents permanent retirement stalls, but deadline expiry is incomplete drain—not successful zero-loss completion.

Live migration has additional requirements. Reserve a compatible destination, copy existing KV, transfer the generated-token position and engine-owned request state, catch up state written during copying, pause briefly at a consistent boundary, transfer ownership, and release the source after acknowledgement. Sampling RNG, speculative state, hybrid caches and in-flight collectives can matter. A new request with the same prompt is replay, not transparent migration.

An illustrative generation has 120 seconds remaining. Natural drain preserves it but holds a GPU for those 120 seconds. Moving 4 GiB over an effective 25 GB/s path has a 172 ms payload lower bound, before synchronization and dirty-state catch-up. Migration can release capacity sooner only if destination headroom and interruption SLO permit it. Otherwise, keeping the source is cheaper or safer for service continuity.

## Hardware, model state and cost

Use the actual checkpoint, KV dtype and TP/DP arrangement. BF16 GQA KV is not equivalent to MLA or recurrent state, and compatible weights do not imply compatible internal cache layouts. Moving across accelerators requires a supported connector and numerical/runtime semantics. Migration traffic competes with inference and may stall the surviving workers precisely during consolidation.

Shared prefix entries can survive worker removal if their storage owner persists, but active decode state also includes current request progress and lifecycle. Local cache loss reduces future hit rate even after all current requests complete. Count retained GPU-seconds, transferred bytes, repeated prefill and post-drain tail latency, not just time until the pod disappears.

## Current implementation and evidence

Foretoken's [Group drain owner](../../../../control-plane/controllers/modelgroup_drain.go) closes model-server admission, checks every surviving frontend's snapshot generation, observes running requests, and releases its finalizer on completion or a recorded timeout. Its [request workflow](../../../../data-plane/frontend/src/server/src/runtime/workflow.rs) retains cleanup across P/D and E/P/D. This path retires workers and cleans up canceled work; active-request migration requires the additional engine-state handoff above.

Dynamo's [graceful-shutdown utility](https://github.com/ai-dynamo/dynamo/blob/b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd/components/src/dynamo/common/utils/graceful_shutdown.py) unregisters endpoints, allows propagation grace, and invokes optional drain/cleanup callbacks with individual timeouts. The utility itself does not track or migrate active requests; behavior depends on the worker callback.

AIBrix's [drain controller helper](https://github.com/vllm-project/aibrix/blob/d0500b0399cf35ad0bf95d073faa83c23308f463/pkg/controller/drain/drain.go) annotates supplied pods and deletes on timeout, with cancellation support. In this helper, the timeout is the completion mechanism; it does not verify engine-request quiescence. Production Stack's [router code](https://github.com/vllm-project/production-stack/blob/4e076e8de3698a3729b575e3a5ade65ffbb929cf/src/vllm_router/routers/routing_logic.py) refreshes endpoints and routing resources, without a live-migration mechanism in that file.

The 2026 [TRE paper](https://arxiv.org/html/2609.29160v1) uses an A100 40GB hot-switch prototype with 7B/8B/14B models, unspecified dtype. It reports second-scale wake/sleep and recovers failed drains by reissuing work rather than migrating KV.

## Experiments and remaining questions

First simulate residual generation lifetimes and destination memory under a scale-down request. Compare natural drain, deadline termination and migration with measured copy rates. Include heavy-tailed outputs and correlated drains; average residual lifetime understates retained capacity.

Then retire a real worker during long streamed responses, with traffic continuing. Record admission closure, route acknowledgement, last accepted request, final completion and resource release. Check client continuity and backend cleanup under cancellation, timeout and stale frontend snapshots. Evaluate migration only on a backend that actually supports it, including exact output-state agreement and source/destination ownership. Remaining work includes tail-aware victim selection, migration-aware consolidation and shared-state cleanup after failure. Cache state is discussed in [KV-cache knowledge](../kv-cache/README.md).

[Back to autoscaling and placement](README.md)
