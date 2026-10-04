<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Implementing admission rules

English | [简体中文](admission-rules_zh.md)

An admission rule decides whether a request can enter preprocessing and execution. The framework supplies a normalized request, trusted service constraints, and access to current observations. Rules do not parse HTTP payloads, load tokenizers, or discover backend clients themselves.

## Implement a rule

Implement `RouteAdmission` under the Router's `algorithm/admission` directory. Its request-level entry point is:

```rust
async fn admit(
    &self,
    request: &AdmissionRequest,
    context: &AdmissionContext<'_>,
) -> Result<AdmissionPermit, AdmissionError>;
```

Return a permit only after accepting the complete request. An unrestricted rule returns `AdmissionPermit::default()` immediately. A stateful rule returns a permit owning its reservation; rejection uses `AdmissionError`. Waiting stays inside this future, and dropping it must remove the waiter and release its queue accounting.

Provide `from_parameters(Value) -> Result<Self, String>` and add the implementation to the stage's `declare_router_algorithms!` list. The shared descriptor registry selects and fully constructs the rule once. Required capacity must be validated before publishing runtime state, not filled with an arbitrary default. New public configuration fields also need an explicit control-plane API mapping and regenerated CRD schema.

`allow_all` is the default rule. `concurrency` demonstrates weighted FIFO acquisition, bounded intake, and reservation ownership.

## Read normalized request facts

`AdmissionRequest` contains lightweight facts, not the body, token IDs, a tokenizer, or a retained serving runtime.

| Input | Meaning and current source |
| --- | --- |
| `model`, `operation`, `api` | Logical model, requested frontend operation, and the API adapter that supplied it. Internal callers can omit `api`. |
| `request_id` | Frontend-generated identity where available. A completion batch shares its identity with its first child; CPU-only operations can omit it. |
| `inputs` | One summary per prompt or chat conversation, before candidate expansion. |
| `candidates_per_input`, `units()` | Actual generated candidates, including `best_of` candidates that will not all be returned. `units()` returns the complete weight or `None` on overflow. |
| `inputs[].text_bytes` | Supplied UTF-8 message text, including reasoning and existing tool-call argument strings. Excludes tool schemas, template expansion, and encoded media. Absent for token-ID-only input. |
| `inputs[].tokens` | `Exact`, `Estimated`, or `Unknown`. Supplied token IDs have an exact count; text and chat remain unknown before preprocessing. Byte count is not a token estimate. |
| `inputs[].messages`, `media` | Actual conversation and media-item counts, not the model's advertised capabilities. |
| `output.requested_max_tokens` | Client-requested per-candidate stopping limit. |
| `output.execution_max_tokens` | Limit already chosen during protocol lowering; unresolved model defaults remain absent. Echo-only completion can request zero while execution uses one token. |
| `output.expected_tokens` | Optional predicted per-candidate work, distinct from either limit. Currently absent because no estimator supplies it. |
| `requested_priority`, `stream` | Client scheduling preference and response mode. Neither grants a service tier. |
| `received_at` | Monotonic frontend processing origin, shared by every candidate. |

Tokenization and detokenization have no output-generation budget. Their processor's internal placeholder `max_tokens` is not exposed as requested work. Token counts refer to complete input cost when known; partial text counts must not be presented as exact multimodal cost.

The server's admission adapter normalizes all generation and tokenization APIs. Add new protocol mappings there rather than teaching each rule another request format.

## Use trusted policy and live observations

`context.deadline` is the original processing origin plus the configured request timeout. The runtime bounds the complete admission attempt by this deadline, including rules without intake reservations. Queue timeout may shorten the wait, but must not restart this budget.

`context.service` separates authenticated identity, configured service class and priority, and latency objectives from client preferences. Higher configured priority takes precedence when a rule uses priority; client priority is retained as a raw preference. TTFT and completion objectives start at `received_at`; TPOT is an average decode-time target after the first token. These optional values are currently absent: Foretoken does not yet provide a trusted identity handoff or a service-objective resolver. Do not substitute client headers, `service_tier`, cache salt, an invented anonymous tenant, or zero-valued SLOs. Those values belong to a future trusted resolver at the runtime boundary; rule interfaces need not change when it supplies them.

Read model and target observations through:

```rust
let state = context.state.model_state(
    &request.model,
    std::time::Duration::from_secs(30),
);
```

Each call reads the current serving generation and local telemetry cache without request-path network I/O. The result distinguishes an unpublished generation from an unknown, preparing, ready, or unavailable model. It includes the prepared model's context-length limit, target metadata and health, available statistics, and this frontend's per-rank routing reservations. Engine telemetry and frontend reservations remain separate.

The returned view contains values, not execution bindings. Query again after waiting rather than retaining a backend or tokenizer. `observed_at` records when the view was sampled; target statistics retain their own collection time and observation window. Missing telemetry remains absent. Observed capacity is not an atomic backend reservation.

## Transfer resource ownership

`AdmissionPermit` is opaque to HTTP and runtime callers. A rule wraps its own `AdmissionReservation`; dropping the reservation releases its remaining resources. `split_one()` transfers an already-reserved unit to a child without reacquiring capacity or incrementing accounting again. Keep the parent responsible for untransferred units.

The generation workflow retains each child permit through preprocessing and the full P/D or E/P/D execution. HTTP headers, the first token, and individual stage completion are not release points. Non-cancelable preprocessing keeps a reserved permit until the work actually finishes, even after the client disconnects.

For intake protection, implement the non-blocking `try_reserve_request()`. Its permit follows the response body, including slow-client backpressure. A resource-free intake permit preserves unrestricted HTTP behavior.

Set `requires_ready_runtime()` when a rule requires a prepared model before it waits. The runtime performs that check and owns readiness watching; the rule does not retain model state in its queue. `close()` wakes queued work during shutdown without revoking permits held by running requests.

## Relation to target selection

| Stage | Main input | Result |
| --- | --- | --- |
| Admission | Preprocessing-independent request facts and live context | An owned permit or typed rejection |
| Filter | Preprocessed request, candidates, KV access, routing progress | Candidate indexes |
| Scorer | Filtered candidates and observations | Scores and an optional selection update |
| Picker | Scored candidates and routing progress | One candidate index |

Admission shares the registration pattern, not the tokenized `RouterRequest` input. Keep target selection out of admission and HTTP status mapping in the existing protocol adapters.

The ownership model follows [Tokio owned permits](https://docs.rs/tokio/latest/tokio/sync/struct.OwnedSemaphorePermit.html) and [Tower concurrency readiness](https://github.com/tower-rs/tower/blob/tower-0.5.2/tower/src/limit/concurrency/service.rs). The distinction between unprocessed facts and token budgets is also explicit in [llm-d request handling](https://github.com/llm-d/llm-d-router/blob/v0.11.0/pkg/epp/framework/interface/requesthandling/types.go). These references inform the boundaries; they are not extra runtime dependencies.
