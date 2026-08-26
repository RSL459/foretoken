// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Scoring by scheduler queue depth, KV-prefix locality, and load.

use foretoken_kv_indexer::KvPrefixIndexer;
use foretoken_model_protocol::ModelServerRole;

use super::{decode_loads_by_pipeline_scope, kv_prefix_best_match};
use std::sync::Arc;

use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, ScorerDescriptor};

inventory::submit! {
    ScorerDescriptor {
        name: "queue_depth",
        factory: || Arc::new(QueueDepthScorer::default()),
    }
}

/// Prefers candidates with the shallowest scheduler waiting queue, then lower downstream Decode load.
///
/// Queue depth is the number of requests waiting in the vLLM scheduler, the direct signal for the
/// queuing delay a newly admitted request would experience. It lands in the final `RouteScore::load`
/// tie-breaker, so KV-prefix match length, tier, and locality still rank first lexicographically.
#[derive(Default)]
pub struct QueueDepthScorer;

impl QueueDepthScorer {
    /// Requests currently waiting in the scheduler queue. Zero when the gauge is not reported.
    fn queue_depth(&self, candidate: &RouteCandidate) -> i64 {
        candidate
            .route_target_stats
            .as_ref()
            .and_then(|stats| stats.scheduler_waiting_requests)
            .and_then(|n| i64::try_from(n).ok())
            .unwrap_or(0)
    }
}

impl RouteScorer for QueueDepthScorer {
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

                let downstream = if candidate.role == ModelServerRole::Prefill {
                    decode_loads
                        .get(&candidate.pipeline_scope_id)
                        .copied()
                        .unwrap_or(0)
                } else {
                    0
                };

                let total_depth = self.queue_depth(candidate).saturating_add(downstream);

                RouteScore {
                    matched_tokens: tokens,
                    tier_preference: tier,
                    locality_preference: locality,
                    load: total_depth.saturating_neg(),
                }
            })
            .collect()
    }
}
