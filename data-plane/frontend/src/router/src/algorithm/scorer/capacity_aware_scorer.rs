// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Scoring by concurrency headroom (remaining admission capacity).

use foretoken_kv_indexer::KvPrefixIndexer;
use foretoken_model_protocol::ModelServerRole;

use super::{decode_loads_by_pipeline_scope, kv_prefix_best_match, load};
use std::sync::Arc;

use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, ScorerDescriptor};

inventory::submit! {
    ScorerDescriptor {
        name: "capacity_aware",
        factory: || Arc::new(CapacityAwareScorer::default()),
    }
}

/// Prefers candidates with the most remaining concurrency headroom, then lower downstream Decode load.
///
/// Headroom is the gap between a node's configured concurrency limit and its current running
/// requests: it measures how many more requests the node can admit before saturating. Unlike
/// `least_loaded`, which compares raw request counts, this compares nodes relative to their own
/// limits, so a large node at 60% can beat a small node at 40%. When the concurrency limit is
/// unreported (0), it degrades to least-loaded semantics.
///
/// Headroom lands in the final `RouteScore::load` tie-breaker as a positive value (more headroom
/// ranks higher); KV-prefix match length, tier, and locality still rank first lexicographically.
#[derive(Default)]
pub struct CapacityAwareScorer;

impl CapacityAwareScorer {
    /// Remaining admission capacity: `max_concurrent_requests - running_requests`, saturating at
    /// zero. Falls back to negated running requests when the concurrency limit is not reported.
    fn remaining_capacity(&self, candidate: &RouteCandidate) -> i64 {
        let max_concurrent = candidate
            .route_target_stats
            .as_ref()
            .and_then(|stats| i64::try_from(stats.max_concurrent_requests).ok())
            .unwrap_or(0);
        if max_concurrent == 0 {
            // Unknown limit: prefer the least-loaded node.
            return load(candidate).saturating_neg();
        }
        max_concurrent.saturating_sub(load(candidate))
    }
}

impl RouteScorer for CapacityAwareScorer {
    fn score(
        &self,
        request: &RouterRequest,
        candidates: &[RouteCandidate],
        kv: &dyn KvPrefixIndexer,
        _: &mut (),
    ) -> Vec<RouteScore> {
        let decode_loads = decode_loads_by_pipeline_scope(candidates);

        candidates
            .iter()
            .map(|candidate| {
                let (tokens, tier, locality) = kv_prefix_best_match(request, candidate, kv);

                // Downstream Decode load reduces the effective headroom of a Prefill node.
                let downstream = if candidate.role == ModelServerRole::Prefill {
                    decode_loads
                        .get(&candidate.pipeline_scope_id)
                        .copied()
                        .unwrap_or(0)
                } else {
                    0
                };

                let headroom = self.remaining_capacity(candidate).saturating_sub(downstream);

                RouteScore {
                    matched_tokens: tokens,
                    tier_preference: tier,
                    locality_preference: locality,
                    load: headroom,
                }
            })
            .collect()
    }
}
