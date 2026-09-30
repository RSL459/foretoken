<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Router

The Router chooses a healthy target that supports the requested model, input length, and capabilities. It also keeps the stages of separate prefill/decode or encoder/prefill/decode services compatible.

To route toward targets with fewer queued requests, add this to a `FrontendService`:

```yaml
spec:
  routerPipeline:
    scorer:
      algorithm: queue_depth
```

Set `spec.routerPipeline` only when you want to change the routing strategy. By default, all compatible targets are considered (`allow_all`), ranked with `kv_least_loaded`, then selected with `gamble_sampling`. Each stage accepts an `algorithm`; scorer-specific options belong under `scorer.parameters`.

| Stage | Algorithm | Selection behavior |
| --- | --- | --- |
| Filter | `allow_all` (default) | Consider every compatible, healthy target. |
| Scorer | `kv_least_loaded` (default) | Prefer reusable KV prefixes, confirmed cache locality, then current and downstream Decode load. |
| Scorer | `least_loaded` · `uniform` | Prefer lower load · give every target an equal score. |
| Scorer | `queue_depth` · `running_request` · `kv_cache_utilization` | Prefer fewer queued requests · fewer running requests · lower measured KV-cache utilization. |
| Scorer | `active_request` | Prefer fewer requests active in this frontend; tune with `idleThreshold` and `maxBusyScore`. |
| Scorer | `token_load` | Prefer lower in-flight and incoming uncached prompt token load; tune with `queueThresholdTokens`. |
| Scorer | `prefix` | Prefer reusable prompt cache blocks; tune match-length preference with `matchLengthWeight` and `matchLengthScaleTokens`. |
| Scorer | `no_hit_lru` | Prefer endpoints not previously selected for cold requests, then least recently selected endpoints; retain up to `lruSize` entries. |
| Scorer | `load_aware` | Score an empty waiting queue at 0.5 and decrease linearly to zero at `threshold`. |
| Scorer | `session_affinity` | Prefer the target and rank bound to the request body's `session_id`; tune idle eviction with `sessionIdConfig.evictionTtlSeconds` and `sessionIdConfig.evictionSweepSeconds`. |
| Picker | `gamble_sampling` (default) | Sample from the full score ranking: higher ranks are more likely, ties have equal probability, and lower-ranked targets remain eligible. |
| Picker | `max` · `power_of_two_choices` | Choose the highest score · sample two distinct targets and choose the higher score (random on ties). |

When the KV index is unavailable, targets remain eligible without KV-prefix preference. See the [KV prefix index](../kv-indexer/README.md) for cache-locality behavior.

`session_affinity` supports only `strategy: session_id`, which is also its default. Send the same non-empty `session_id` in each Chat Completions, Completions, or Responses request body; surrounding whitespace is removed. An available binding scores 1 and other candidates score 0. A missing identifier, new session, or unavailable bound target gives every candidate 0. Use the `max` picker to honor an available binding; sampling another target does not change or refresh it. Bindings are committed after selection and migrate only when the previous target is no longer selectable.

Bindings belong to each frontend pipeline and routing stage, survive serving-snapshot updates, and are not shared across replicas. Under `scorer.parameters.sessionIdConfig`, the idle TTL defaults to 300 seconds and the sweep interval to 10 seconds; zero uses the default and negative values are rejected. Selecting the bound target refreshes its timer. A sweep removes bindings idle for strictly longer than the TTL; until then, they can still be used and refreshed. Replacing the pipeline or restarting the frontend clears its bindings.
