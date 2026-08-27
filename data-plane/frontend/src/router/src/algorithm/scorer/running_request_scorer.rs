// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Scoring by scheduler-running request count, KV-prefix locality, and load.

use foretoken_kv_indexer::KvPrefixIndexer;
use foretoken_model_protocol::ModelServerRole;

use super::{decode_loads_by_pipeline_scope, kv_prefix_best_match, load};
use std::sync::Arc;

use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, ScorerDescriptor};

inventory::submit! {
    ScorerDescriptor {
        name: "running_request",
        factory: || Arc::new(RunningRequestScorer::default()),
    }
}

/// Prefers candidates with the fewest scheduler-running requests, then lower downstream Decode load.
///
/// The running-request count is a finer admission signal than the total admitted request count:
/// it reflects work actively executing in the vLLM scheduler. It lands in the final
/// `RouteScore::load` tie-breaker, so KV-prefix match length, tier, and locality still rank first
/// lexicographically.
#[derive(Default)]
pub struct RunningRequestScorer;

impl RunningRequestScorer {
    /// Scheduler requests currently running, falling back to total running requests when the
    /// scheduler gauge is not reported.
    fn running_requests(&self, candidate: &RouteCandidate) -> i64 {
        candidate
            .route_target_stats
            .as_ref()
            .and_then(|stats| stats.scheduler_running_requests)
            .and_then(|n| i64::try_from(n).ok())
            .unwrap_or_else(|| load(candidate))
    }
}

impl RouteScorer for RunningRequestScorer {
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

                let total_running = self
                    .running_requests(candidate)
                    .saturating_add(downstream);

                RouteScore {
                    matched_tokens: tokens,
                    tier_preference: tier,
                    locality_preference: locality,
                    load: total_running.saturating_neg(),
                }
            })
            .collect()
    }
}
