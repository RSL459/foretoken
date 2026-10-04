<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Router

The Router chooses a healthy target that supports the requested model, input length, and capabilities. It also keeps the stages of separate prefill/decode or encoder/prefill/decode services compatible.

## Select a routing strategy

To route toward targets with fewer queued requests, add this to a `FrontendService`:

```yaml
spec:
  routerPipeline:
    scorer:
      algorithm: queue_depth
```

Omit `filter`, `scorer`, and `picker` to use the default routing strategy. By default, all compatible targets are considered (`allow_all`), ranked with `kv_least_loaded`, then selected with `gamble_sampling`. Each stage accepts an `algorithm`; scorer-specific options belong under `scorer.parameters`.

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

## Limit concurrent requests

To bound work accepted by each frontend replica, add an Admission stage:

```yaml
spec:
  routerPipeline:
    admission:
      parameters:
        maxConcurrentRequests: 64
```

This example allows 64 simultaneous generations and rejects excess requests with HTTP 503. Choose the limit from measurements of your workload; 64 is an example, not a default. Omit `admission` to leave this protection disabled. The stage's algorithm defaults to `concurrency`.

For short bursts, set `maxQueuedRequests: 128` and `queueTimeout: 2s` under the same `parameters` block. Queued requests receive capacity in FIFO order before preprocessing and target selection.

| Parameter | Purpose | Default |
| --- | --- | --- |
| `maxConcurrentRequests` | Maximum concurrent generations per frontend replica | Required |
| `maxQueuedRequests` | Maximum generations waiting for capacity | `0`, no queue |
| `queueTimeout` | Maximum time waiting for admission | Remaining request timeout |

A batched completion counts each output candidate separately: four prompts with `n: 2` need eight slots. A batch larger than the concurrency limit returns HTTP 400. Queue exhaustion and queue timeout return HTTP 503; the overall request timeout still applies. Text generation and tokenization share this protection; video requests and background video tasks do not.

Each frontend replica shares these limits across its models; they are not cluster-wide quotas. Health probes remain available when capacity is full. Admission does not change how targets are filtered, scored, or selected.
