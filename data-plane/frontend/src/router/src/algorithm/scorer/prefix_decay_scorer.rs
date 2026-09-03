// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Scoring by KV-prefix hit with busyness-decayed credit (Dynamo overlap-credit decay).

use foretoken_kv_indexer::KvPrefixIndexer;
use foretoken_model_protocol::ModelServerRole;

use super::{decode_loads_by_pipeline_scope, kv_prefix_best_match, load};
use std::sync::Arc;

use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, ScorerDescriptor};

inventory::submit! {
    ScorerDescriptor {
        name: "prefix_decay",
        factory: || Arc::new(PrefixDecayScorer),
    }
}

/// How strongly the cache credit decays with load. `1.0` fully cancels a saturated node's credit;
/// `0.0` disables decay (equivalent to a pure prefix scorer).
const CREDIT_DECAY_RATE: f64 = 0.5;

/// Prefers KV-prefix hits, but discounts a candidate's cache credit as its load rises.
///
/// Mirrors Dynamo's `--router-kv-overlap-score-credit-decay`: a cache-rich node that is already
/// saturated has its prefix advantage reduced, so a less-busy node with a shorter prefix can win.
/// The decayed prefix length still ranks first in the lexicographic `RouteScore`; load only breaks
/// ties among the remaining equally-ranked candidates.
#[derive(Default)]
pub struct PrefixDecayScorer;

impl PrefixDecayScorer {
    /// Multiplicative credit factor in `0.0..=1.0` based on the candidate's concurrency utilization.
    fn credit_factor(&self, candidate: &RouteCandidate) -> f64 {
        let running = load(candidate) as f64;
        let max_concurrent = candidate
            .route_target_stats
            .as_ref()
            .map(|stats| stats.max_concurrent_requests as f64)
            .unwrap_or(0.0);
        let utilization = if max_concurrent > 0.0 {
            running / max_concurrent
        } else {
            // Saturating toward 1.0 when the concurrency limit is unreported.
            running / (running + 1.0)
        };
        (1.0 - utilization * CREDIT_DECAY_RATE).clamp(0.0, 1.0)
    }
}

impl RouteScorer for PrefixDecayScorer {
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
                let (raw_tokens, tier, locality) = kv_prefix_best_match(request, candidate, kv);
                let decayed_tokens = (raw_tokens as f64 * self.credit_factor(candidate)) as i64;

                let downstream = if candidate.role == ModelServerRole::Prefill {
                    decode_loads
                        .get(&candidate.pipeline_scope_id)
                        .copied()
                        .unwrap_or(0)
                } else {
                    0
                };

                RouteScore {
                    matched_tokens: decayed_tokens,
                    tier_preference: tier,
                    locality_preference: locality,
                    load: load(candidate).saturating_add(downstream).saturating_neg(),
                }
            })
            .collect()
    }
}
