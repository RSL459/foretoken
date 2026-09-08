<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Router Maintenance

English | [中文](MAINTAINER_zh.md)

Router algorithms are compiled into the Frontend binary. They are not runtime plugins and are not a public extension surface.

## Pipeline contracts

Each request is processed as:

```text
compatible and healthy candidates
→ Filter indexes
→ Scorer scores parallel to retained candidates
→ Picker index
→ RouteDecision
```

- `RouteFilter` returns indexes of candidates to retain.
- `RouteScorer` returns one `RouteScore` for every retained candidate in the same order.
- `RoutePicker` returns an index into the scored candidates.

The Router owns candidate identity and validates duplicate or out-of-range indexes and score-count mismatches. Algorithms must not maintain a second route catalog or query model servers on the request path; they receive an immutable round-local observation snapshot.

## Adding an algorithm

Implement the appropriate interface under `src/algorithm/filter/`, `src/algorithm/scorer/`, or `src/algorithm/picker/`. Add one entry to the corresponding stage's `declare_router_algorithms!` list in `mod.rs`, providing the module name, type name, and user-facing configuration name. The macro generates the module declaration, public re-export, and compiled descriptor registration; no Controller enum or CRD change is required. Update maintained examples, the user-facing Router README, and contract tests only when observable behavior changes.

Request-local shared state belongs in `RouterPipeline::with_customized_context`. The Router creates one context per request and drops it when that request finishes.

## Multi-stage routing

Algorithms score the complete compatible and healthy candidate snapshot. Before picking, the Router narrows it to the current execution stage and its selected controller-defined pipeline scope. This preserves aggregate, P/D, and E/P/D execution ownership while allowing a scorer to account for related stage load.

## `token_load`

The scoring formula and defaults follow [llm-d](https://github.com/llm-d/llm-d-router/blob/7de00e5452818546815417aee2d6c68d2c2ff323/pkg/epp/framework/plugins/scheduling/scorer/tokenload/token_load.go).
Signed token addition precedes conversion to `f64`. Nonpositive load scores one; otherwise
score is `1 - min(load, threshold) / threshold`. The request contribution is uncached indexed
tokens plus the partial prompt tail. Estimated output tokens are disabled. Selection and
reservation share a lock; the routing session releases its contribution on the first response,
stage completion, or drop. RuntimeBuilder preserves the local state across generations.

`RouteScore.preference` preserves floating-point scores without quantization. Foretoken owns
input production, endpoint eligibility, and tie breaking. `scorerParameters` passes through
the CRD and controller environment to the selected scorer at frontend startup.
