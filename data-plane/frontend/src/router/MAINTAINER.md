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

## Scorer contracts

The `token_load` scorer uses the following observations and formula:

| Scorer | Input | Score |
| --- | --- | --- |
| `token_load` | In-flight tokens plus incoming uncached prompt tokens, `load` | `1` if `load <= 0`; otherwise `1 - min(load, threshold) / threshold` |

Token load uses signed addition before conversion to `f64`. `threshold` is
`queueThresholdTokens` (default `4194304`); nonpositive configured values use the default.
The request contribution is uncached indexed tokens plus the partial prompt tail. Without
usable cache observations, the whole prompt counts as uncached. Output tokens are not estimated.
Counts are local to each frontend replica and target DP rank; engine scheduler gauges are not added.
Aggregate, Prefill, and Decode reserve the selected target's uncached prompt tokens before dispatch.
The first response releases tokens; stage completion or session drop releases any remaining
contribution, including failed dispatches.

Selection and reservation share one lock, so concurrent requests see already selected local
work. The routing session owns cleanup, and RuntimeBuilder retains this load state across
serving-snapshot replacements.

`RouteScore.preference` preserves floating-point scores without quantization. Foretoken owns
input production, endpoint eligibility, and tie breaking. `scorerParameters` passes through
the CRD and controller environment to the selected scorer at frontend startup.
