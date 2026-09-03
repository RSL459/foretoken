// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Scoring purely by KV-prefix locality.

use foretoken_kv_indexer::KvPrefixIndexer;

use super::kv_prefix_best_match;
use std::sync::Arc;

use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, ScorerDescriptor};

inventory::submit! {
    ScorerDescriptor {
        name: "prefix",
        factory: || Arc::new(PrefixScorer),
    }
}

/// Prefers the longest confirmed-locality KV-prefix match, ignoring current load.
///
/// This isolates the cache-locality dimension: it ranks by matched tokens, then storage tier, then
/// physical locality, and leaves the load tie-breaker at zero. It is useful when cache reuse, not
/// load balancing, is the dominant objective.
#[derive(Default)]
pub struct PrefixScorer;

impl RouteScorer for PrefixScorer {
    fn score(
        &self,
        request: &RouterRequest,
        candidates: &[RouteCandidate],
        kv: &dyn KvPrefixIndexer,
        _: &mut (),
    ) -> Vec<RouteScore> {
        candidates
            .iter()
            .map(|candidate| {
                let (tokens, tier, locality) = kv_prefix_best_match(request, candidate, kv);
                RouteScore {
                    matched_tokens: tokens,
                    tier_preference: tier,
                    locality_preference: locality,
                    load: 0,
                }
            })
            .collect()
    }
}
