// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Scoring by KV Cache utilization.
//! Prefers routing to nodes that have ample KV cache space available to avoid evictions.

use foretoken_kv_indexer::KvPrefixIndexer;
use foretoken_model_protocol::ModelServerRole;

use super::{decode_loads_by_pipeline_scope, kv_prefix_best_match, load};
use std::sync::Arc;

use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, ScorerDescriptor};

inventory::submit! {
    ScorerDescriptor {
        name: "kv_cache_utilization",
        factory: || Arc::new(KvCacheUtilizationScorer),
    }
}

/// Prefers candidates with lower KV cache utilization (more free blocks),
/// balancing between caching space availability and current load.
///
/// The utilization penalty lands in the final `RouteScore::load` tie-breaker: KV-prefix match
/// length, tier, and locality still rank first lexicographically.
#[derive(Default)]
pub struct KvCacheUtilizationScorer;

impl RouteScorer for KvCacheUtilizationScorer {
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

                let base_load = load(candidate).saturating_add(downstream);

                // KV-cache utilization penalty: excessive utilization causes repeated eviction
                // (thrashing) from capacity pressure, degrading throughput. Above 80% the penalty
                // rises steeply with utilization; below 80% only a light base penalty applies.
                let kv_utilization_penalty = candidate
                    .route_target_stats
                    .as_ref()
                    .and_then(|stats| stats.kv_cache_usage)
                    .map(|usage| {
                        let util_pct = (usage * 100.0) as i64;
                        if util_pct > 80 {
                            (util_pct - 80) * 10
                        } else {
                            util_pct / 10
                        }
                    })
                    .unwrap_or(0);

                let total_load_penalty = base_load.saturating_add(kv_utilization_penalty);

                RouteScore {
                    matched_tokens: tokens,
                    tier_preference: tier,
                    locality_preference: locality,
                    load: total_load_penalty.saturating_neg(),
                }
            })
            .collect()
    }
}
