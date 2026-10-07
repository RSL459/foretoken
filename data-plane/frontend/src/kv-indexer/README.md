<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# KV Prefix Index

English | [中文](README_zh.md)

The KV prefix index helps routing reuse prompt tokens already cached by a model replica. It reports local accelerator cache as `Device/Local`, filesystem offload as `Disk/Local`, and Mooncake shared memory or SSD cache as `External/Remote`. Prefix lookup supports text requests without LoRA that allow prefix-cache reads.

To use cache-aware routing without writing an algorithm, select a scorer in the [routing guide](../router/README.md).

## Use prefix matches in an algorithm

In a `RouteFilter` or `RouteScorer`, request prefix observations by implementing:

```rust
fn needs_kv_prefix(&self) -> bool {
    true
}
```

Query the reader supplied to `filter` or `score` for the candidate's exact target and data-parallel rank. Routing prepares external observations before calling the algorithm, so the lookup is synchronous:

```rust
use foretoken_kv_indexer::{KvPrefixIndexer, KvPrefixQueryResult};
use foretoken_router::{RouteCandidate, RouterRequest};

fn candidate_prefix(
    request: &RouterRequest,
    candidate: &RouteCandidate,
    indexer: &dyn KvPrefixIndexer,
) -> KvPrefixQueryResult {
    match request.kv_prefix_lookup(
        &candidate.route_target_id,
        candidate.data_parallel_rank,
    ) {
        Ok(lookup) => indexer.prefix_matches(lookup),
        Err(reason) => KvPrefixQueryResult::Unavailable(reason),
    }
}
```

Each match provides `placement` and `matched_tokens`. An empty `Matches` means no matching prefix was found; `Unavailable` means the result is unknown. Keep unavailable candidates eligible for ordinary routing.

## Inspect index health

Use the frontend's `/statusz` for index health and `/metrics` for monitoring. See [frontend operations](../../README.md#operations).
