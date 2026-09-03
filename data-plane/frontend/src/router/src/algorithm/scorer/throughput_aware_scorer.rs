// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Scoring by processing throughput (tokens per second).

use foretoken_kv_indexer::KvPrefixIndexer;
use foretoken_model_protocol::ModelServerRole;

use super::{decode_loads_by_pipeline_scope, kv_prefix_best_match};
use std::sync::Arc;

use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, ScorerDescriptor};

inventory::submit! {
    ScorerDescriptor {
        name: "throughput_aware",
        factory: || Arc::new(ThroughputAwareScorer),
    }
}

/// Divides the inverse-throughput penalty so higher tokens-per-second produces a smaller penalty
/// in the same magnitude as running-request counts (e.g. ~100 tps yields a penalty of ~10).
const INVERSE_THROUGHPUT_SCALE: f64 = 1_000.0;

/// Prefers candidates with higher observed throughput (prompt + generation tokens per second),
/// then lower downstream Decode load.
///
/// Mirrors AIBrix's `normInverseThroughput` decode-policy term: throughput reflects a node's
/// processing capacity over the observation window, so a faster node clears its queue sooner and
/// is preferred. The inverse-throughput penalty lands in the final `RouteScore::load` tie-breaker;
/// KV-prefix match length, tier, and locality still rank first lexicographically.
#[derive(Default)]
pub struct ThroughputAwareScorer;

impl ThroughputAwareScorer {
    /// Inverse-throughput penalty: larger when a node processed fewer tokens per second. A node
    /// with no throughput observation is treated as neutral (zero penalty), matching the
    /// "unknown = no penalty" convention of the other scorers.
    fn throughput_penalty(&self, candidate: &RouteCandidate) -> i64 {
        candidate
            .route_target_stats
            .as_ref()
            .and_then(|stats| {
                let prompt_tps = stats.prompt_tokens_per_second.unwrap_or(0.0);
                let generation_tps = stats.generation_tokens_per_second.unwrap_or(0.0);
                let total_tps = prompt_tps + generation_tps;
                (total_tps > 0.0).then_some((INVERSE_THROUGHPUT_SCALE / total_tps) as i64)
            })
            .unwrap_or(0)
    }
}

impl RouteScorer for ThroughputAwareScorer {
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

                let total_penalty = self
                    .throughput_penalty(candidate)
                    .saturating_add(downstream);

                RouteScore {
                    matched_tokens: tokens,
                    tier_preference: tier,
                    locality_preference: locality,
                    load: total_penalty.saturating_neg(),
                }
            })
            .collect()
    }
}
