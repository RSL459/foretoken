// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Scoring by multimodal cache affinity and KV-cache headroom.

use foretoken_kv_indexer::KvPrefixIndexer;
use foretoken_model_protocol::ModelServerRole;

use super::{decode_loads_by_pipeline_scope, kv_prefix_best_match, load};
use std::sync::Arc;

use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, ScorerDescriptor};

inventory::submit! {
    ScorerDescriptor {
        name: "mmcache_affinity",
        factory: || Arc::new(MmcacheAffinityScorer::default()),
    }
}

/// Prefers candidates with enough KV-cache headroom to absorb multimodal encoder outputs.
///
/// Multimodal requests (`mm_features`) do not reuse the prompt KV prefix: their encoder outputs must
/// be freshly written into the KV cache, so free cache space is the dominant signal. For such
/// requests this scorer applies a cache-pressure penalty stronger than the generic utilization
/// scorer, then falls back to the usual KV-prefix and load terms. Non-multimodal requests degrade to
/// the standard prefix + load ranking.
#[derive(Default)]
pub struct MmcacheAffinityScorer;

impl MmcacheAffinityScorer {
    /// Whether the request carries multimodal features that bypass prompt-prefix reuse.
    fn is_multimodal(&self, request: &RouterRequest) -> bool {
        request.generate_request.mm_features.is_some()
    }

    /// Cache-pressure penalty applied only to multimodal requests.
    ///
    /// Multimodal requests are more sensitive to cache exhaustion than text requests because they
    /// cannot fall back on prefix reuse, so the penalty escalates faster beyond 80% utilization.
    fn mm_cache_pressure_penalty(&self, candidate: &RouteCandidate, is_multimodal: bool) -> i64 {
        if !is_multimodal {
            return 0;
        }
        candidate
            .route_target_stats
            .as_ref()
            .and_then(|stats| stats.kv_cache_usage)
            .map(|usage| {
                let util_pct = (usage * 100.0) as i64;
                if util_pct > 80 {
                    (util_pct - 80) * 20
                } else {
                    util_pct / 5
                }
            })
            .unwrap_or(0)
    }
}

impl RouteScorer for MmcacheAffinityScorer {
    fn score(
        &self,
        request: &RouterRequest,
        candidates: &[RouteCandidate],
        kv: &dyn KvPrefixIndexer,
        _: &mut (),
    ) -> Vec<RouteScore> {
        let decode_loads = decode_loads_by_pipeline_scope(candidates);
        let is_multimodal = self.is_multimodal(request);

        candidates
            .iter()
            .map(|candidate| {
                // Multimodal requests cannot reuse the prompt prefix, so this is zeros for them.
                let (tokens, tier, locality) = kv_prefix_best_match(request, candidate, kv);

                let downstream = if candidate.role == ModelServerRole::Prefill {
                    decode_loads
                        .get(&candidate.pipeline_scope_id)
                        .copied()
                        .unwrap_or(0)
                } else {
                    0
                };

                let total_penalty = load(candidate)
                    .saturating_add(downstream)
                    .saturating_add(self.mm_cache_pressure_penalty(candidate, is_multimodal));

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
