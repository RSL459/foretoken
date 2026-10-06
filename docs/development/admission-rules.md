<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Implementing admission rules

English | [简体中文](admission-rules_zh.md)

Admission rules control when requests enter preprocessing and execution. The frontend's admission crate owns rule construction, reservations, and telemetry; the router selects execution targets. For deployment settings, see [Configure admission rules](../../data-plane/frontend/README.md#configure-admission-rules).

## Implement and register a rule

Implement `AdmissionRule` with this entry point:

```rust
async fn admit(
    &self,
    request: &AdmissionRequest,
    context: &AdmissionContext<'_>,
) -> Result<AdmissionPermit, AdmissionError>;
```

Return an `AdmissionPermit` to accept the request or an `AdmissionError` to reject it. A rule can wait inside this future; the framework enforces the request deadline and cancels the wait when the caller disconnects.

Provide `from_parameters(Value) -> Result<Self, String>` and add the rule to the `declare_admission_algorithms!` list in [admission/src/algorithm/mod.rs](../../data-plane/frontend/src/admission/src/algorithm/mod.rs). External rules register an `AdmissionDescriptor` through `inventory` with a configured factory. Construction and parameter validation run once at startup. New public parameters also require a FrontendService API update and CRD regeneration.

Use [allow_all](../../data-plane/frontend/src/admission/src/algorithm/allow_all.rs) as the simplest implementation, or [concurrency](../../data-plane/frontend/src/admission/src/algorithm/concurrency.rs) for weighted waiting and resource reservations.

## Use the supplied inputs

- Request facts: `AdmissionRequest` provides the model, operation, candidate count, input and media summaries, output budgets, client preferences, and processing start time.
- Service context: `context.deadline` is the total request deadline; `context.service` contains resolved identity, service class, priority, and latency objectives. Identity and service-policy values are currently unpopulated.
- Runtime observations: query current model availability, target health, load, and capacity statistics through `context.state`:

```rust
let state = context.state.model_state(
    &request.model,
    std::time::Duration::from_secs(30),
);
```

Input token counts distinguish exact, estimated, and unknown values. Output limits and predicted output work are separate fields. Query runtime observations again after waiting to use current values.

Field definitions and units are documented in [AdmissionRequest](../../data-plane/frontend/src/admission/src/request.rs) and [AdmissionContext](../../data-plane/frontend/src/admission/src/context.rs).

## Return and release resources

For unrestricted admission, return `AdmissionPermit::default()`. For reserved resources, implement `AdmissionReservation` and wrap it with `AdmissionPermit::new(...)`.

`split_one()` transfers one reserved unit to a batch child; dropping a reservation releases its remaining resources. Intake permits follow the HTTP response body; work permits cover the complete request lifecycle, including output-stream completion. Keep waiting resources owned by the admission future so cancellation releases them.

While queueing, hold the guard returned by `context.queue.begin_wait()` until waiting ends. The framework records the wait with the final admission result.

Additional hooks support resource reporting, intake, and readiness:

| Hook | Purpose |
| --- | --- |
| `capacity()` | Report finite work, queue, and resident limits for the Admission dashboard. |
| `try_reserve_request()` | Reserve a resident HTTP-request slot before body extraction; its permit follows the response body. |
| `requires_ready_runtime()` | Require model preparation before generation admission. |
| `close()` | Wake waiting requests during shutdown. |

## Update existing configuration

Move `spec.routerPipeline.admission` to `spec.admission`, alongside `routerPipeline`, and remove the old field. Algorithm names, parameters, and the `allow_all` default are unchanged.
