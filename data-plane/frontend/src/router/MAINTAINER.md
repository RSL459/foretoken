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

Request-local shared state belongs in `RouterPipeline::with_customized_context`. The Router creates one context per request and drops it when that request finishes. A joint E/P/D implementation can evaluate the complete candidate snapshot during the initial round, retain its preferred stage identities in this context, and have its Picker return one planned candidate in each stage.

## Multi-stage routing

Algorithms score the complete compatible and healthy candidate snapshot. Before picking, the Router narrows it to the current execution stage and its selected controller-defined pipeline scope. This preserves aggregate, P/D, and E/P/D execution ownership while allowing a scorer to account for related stage load.

## Scorer contracts

Scorers use the following observations and formulas:

| Scorer | Input | Score |
| --- | --- | --- |
| `active_request` | Local active requests `count` and candidate maximum `maxCount` | `1` if `count <= idleThreshold`; otherwise `(maxCount - count) / maxCount * maxBusyScore` |

`active_request` takes `maxCount` over all candidates supplied to `score`. `idleThreshold` defaults to `0`;
negative values become zero. `maxBusyScore` defaults to `1` with range `[0, 1]`; missing, null, or out-of-range values use `1`.
Each selected stage remains counted until completion or session drop.

`active_request` uses frontend-local reservations per target and DP rank, without engine scheduler gauges
or other frontend replicas' requests. Selection and reservation share one lock; routing sessions own
cleanup, and RuntimeBuilder retains the state across serving-snapshot replacements.

An empty candidate slice produces an empty score vector. `RouteScore.preference` preserves the
numeric output, with the locality/load fields left at zero. Existing locality policies retain
their lexicographic ordering.

Set optional parameters in `FrontendService.spec.routerPipeline.scorerParameters`; the selected scorer reads them at frontend startup.
