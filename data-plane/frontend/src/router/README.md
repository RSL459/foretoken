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
| Scorer | `two_tier` | Prefer lower active-request load when both imbalance thresholds are exceeded; otherwise prefer maximum Device-prefix overlap above `cache_threshold`. Requires the `max` picker. |
| Picker | `gamble_sampling` (default) | Sample from the full score ranking: higher ranks are more likely, ties have equal probability, and lower-ranked targets remain eligible. |
| Picker | `max` · `power_of_two_choices` | Choose the highest score · sample two distinct targets and choose the higher score (random on ties). |

When the KV index is unavailable, targets remain eligible without KV-prefix preference. See the [KV prefix index](../kv-indexer/README.md) for cache-locality behavior.

For `two_tier`, set `picker: {algorithm: max}` alongside `scorer: {algorithm: two_tier}`; other pickers fail configuration validation. Under `scorer.parameters`, `balance_abs_threshold` defaults to 32, `balance_rel_threshold` to 1.1, and `cache_threshold` to 0.5. Both the load spread and the maximum-to-minimum load ratio must strictly exceed their thresholds before load overrides cache affinity. Load counts this frontend's active reservations for each target and rank. Otherwise, a Device-prefix hit ratio strictly above the cache threshold selects the least-loaded candidate with maximum overlap; below or at the threshold, least load wins. Ties use candidate order.

The hit ratio counts complete cached blocks over the request's rounded-up block count. Missing cache observations contribute zero overlap. Cache comparison requires a common observed KV block size; differing sizes give all candidates equal scores. Host, disk, and external cache do not contribute.
