# Autoscaling Architecture

[English](README.md) | [中文](README_zh.md)

This package turns controller-owned observations into `ModelPool` capacity. Users configure autoscaling through `ModelService.spec.autoscaling`; configuration and status usage are documented in the [autoscaling guide](../../../../docs/autoscaling.md).

## Ownership

The `ModelService` controller owns scheduling, observation collection, target discovery, status publication, and writing capacity to `ModelPool`. Algorithms are side-effect-free: they only evaluate one complete observation and return a recommendation.

Every target scales one Pool. An E/P/D service has one encoder, one prefill, and one decode Pool; their capacities are evaluated independently, while the ModelService controller commits their prepared revisions as one complete serving cohort.

## Evaluation pipeline

```text
controller polling loop
→ ScalingSnapshot
→ TriggerDecision
→ ReplicaRecommendation
→ ReplicaAdjustment
→ ScalingDecision
→ ModelPool capacity and ModelService status
```

The controller supplies complete, fresh observations to the pipeline. `periodic` accepts those observations; it does not own an interval or requeue loop. The resolver applies hard min/max bounds even when observations are missing, and holds capacity while a target is transitioning.

`step` stabilization uses recent recommendations retained by the current controller process. The history is intentionally runtime-local, so a restart or leader change does not restore a pending scale-down delay.

## Extension boundary

Built-in algorithms live under `algorithm/`. Trigger, decision, and adjustment implementations return domain results and do not read Kubernetes resources, mutate capacity, or schedule work. Add a new implementation only when it represents a current, independently owned recommendation policy; controller lifecycle behavior remains in `core` and the ModelService reconciler.

Each trigger, decision, and adjustment stage owns a compiled descriptor list. Add an implementation and one descriptor in its stage; the top-level registry constructs the selected factory and does not accept runtime registrations. Algorithms own their parameter defaults and validation, while `core.DecodeParameters` provides shared field and type decoding without exposing implementation structs as configuration.

All stages receive an optional JSON parameters object. Adjustment factories also receive the controller-owned recommendation history. Trigger implementations expose their polling interval; the controller owns scheduling and derives observation freshness from that interval. Capacity bounds and lifecycle constraints remain platform responsibilities.

The controller constructs the pipeline once per reconciliation. Built-in defaults select periodic triggering and step adjustment when those stages are omitted; individual parameter defaults remain in the selected implementation. A new implementation requires rebuilding and deploying the controller, not runtime plugin loading.

## Validation

Use the control-plane verification target after changing this package:

```bash
make -C control-plane verify
```

## Dynamo reactive policy boundary

The replication reference is NVIDIA Dynamo commit
[`bea55a595a83a84b76183d44516de05f9ea1b2d0`](https://github.com/ai-dynamo/dynamo/blob/bea55a595a83a84b76183d44516de05f9ea1b2d0/components/src/dynamo/planner/core/load_scaling.py),
particularly `_prefill_easy_decision`, `_decode_easy_decision`, `_agg_easy_decision`,
and their consolidation check. This implements the easy reactive policies;
profile-driven TTFT/ITL prediction, pending-startup estimates, and Dynamo endpoint
management are outside this decision boundary. Foretoken owns those lifecycle
operations through its existing controllers.

The vLLM reference is the pinned source commit
`1be36283678a9a94fc8fdaad6c95c2896d6b4015`. The generic `get_scheduler_load`
utility and scheduler capture hook live in `common/scheduler-load.patch`, enabled
only by the pinned-source and current Python compatibility series. Capture is
activated by the first utility query and preserves the native async scheduler.
Cached requests classified as decode contribute their computed token count;
preempted and remote-KV waiting requests contribute queued decode tokens;
other waiting requests contribute their full token count to queued prefill.
Finished requests are excluded from the last scheduled decode sample.

The model-server adapter calls the public EngineCore utility API for every DP
rank and exposes a separate version-1 `/v1/internal/scheduler-load` response.
Existing version-2 telemetry stays unchanged. Only `dynamo_load` requests this
additional observation. The controller validates rank coverage and capacities,
attributes samples to the selected serving Group UID, and retains individual
ranks in `EngineLoads`. Errors discard the whole collection; an average or a
partial successful cohort never becomes a scaling signal.

Single-group full-attention cache capacity is `num_blocks * block_size`. Hybrid,
multiple cache groups, and context parallelism require a different capacity
contract and currently return unavailable. Accepted work is protected by Group
draining rather than an idle-only condition in the policy.
