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

## Metric scorer contracts

The `running_request` scorer ports llm-d-router at `d8d22ea8f7d412f2a7e61ec415d11b24322a7938`:

| Foretoken scorer | llm-d source | Input | Score |
| --- | --- | --- | --- |
| `running_request` | [running-requests-size-scorer](https://github.com/llm-d/llm-d-router/blob/d8d22ea8f7d412f2a7e61ec415d11b24322a7938/pkg/epp/framework/plugins/scheduling/scorer/runningrequests/runningrequest.go) | `scheduler_running_requests` | `(max - running) / (max - min)` |

For identical input metrics and candidate sets, the numeric contributions match the stock
per-endpoint scorer. Counts normalize over all candidates supplied to `score`; equal counts receive `1`,
and an empty candidate slice produces an empty score vector. Count subtraction precedes
conversion to `f64`.
`RouteScore.preference` preserves the numeric output, with the locality/load fields left at
zero. Existing locality policies retain their lexicographic ordering.

The registry owns gauge history: publish gauges immediately, retain the last measured value on
omission, and leave rates and histograms unavailable until their counter window is covered.
The metric-scorer input mapping uses zero for never-observed gauges, matching llm-d's
[initial endpoint metrics](https://github.com/llm-d/llm-d-router/blob/d8d22ea8f7d412f2a7e61ec415d11b24322a7938/pkg/epp/framework/interface/datalayer/metrics.go).

Foretoken keeps its own telemetry transport, health checks, DP expansion, and E/P/D eligibility.
Its Model Server endpoint reports sums of scheduler counts and mean KV utilization across its
engines. Every rank of that endpoint receives the same metric score. The scorer ignores
`RoutingProgress`; Router still supplies it and owns the subsequent stage selection.
This ports scorer behavior, not llm-d's endpoint discovery, scraping, or complete scheduler.
