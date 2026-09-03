// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Scoring by Session affinity (stickiness), KV-prefix locality, and current load.

use foretoken_kv_indexer::KvPrefixIndexer;
use foretoken_model_protocol::ModelServerRole;

use super::{decode_loads_by_pipeline_scope, kv_prefix_best_match, load};
use std::sync::Arc;

use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, ScorerDescriptor};

inventory::submit! {
    ScorerDescriptor {
        name: "session_aware",
        factory: || Arc::new(SessionAwareScorer),
    }
}

/// Prefers candidates that hold existing Session affinity (session stickiness),
/// followed by longer confirmed KV-prefix matches, higher cache tier, and lower load.
///
/// The session target is resolved by the caller from `RouterRequest::session_id()` and carried as
/// `RouterRequest::session_target_id`. A hit raises `locality_preference`, which ranks after
/// `matched_tokens` and `tier_preference` in the lexicographic `RouteScore`: a much longer
/// KV-prefix match elsewhere still wins, but session stickiness beats locality among
/// otherwise-equal candidates.
#[derive(Default)]
pub struct SessionAwareScorer;

impl RouteScorer for SessionAwareScorer {
    fn score(
        &self,
        request: &RouterRequest,
        candidates: &[RouteCandidate],
        kv: &dyn KvPrefixIndexer,
        _: &mut (),
    ) -> Vec<RouteScore> {
        let decode_loads = decode_loads_by_pipeline_scope(candidates);

        // The session identity carried by the request, or the previously-affine target (if any).
        let session_target = request.session_target_id();

        candidates
            .iter()
            .map(|candidate| {
                // 1. Whether this candidate holds the session's affinity (session affinity match).
                let is_session_hit = session_target
                    .map(|target_id| target_id == candidate.route_target_id.as_str())
                    .unwrap_or(false);

                // 2. KV-cache prefix match facts.
                let (tokens, tier, locality) = kv_prefix_best_match(request, candidate, kv);

                // 3. Downstream Decode node load.
                let downstream = if candidate.role == ModelServerRole::Prefill {
                    decode_loads
                        .get(&candidate.pipeline_scope_id)
                        .copied()
                        .unwrap_or(0)
                } else {
                    0
                };

                // 4. On a session-sticky hit, raise locality_preference so requests in the same
                //    session prefer the previously-recorded node.
                let final_locality = if is_session_hit {
                    // Give a session hit the highest locality-preference bonus.
                    locality.saturating_add(10)
                } else {
                    locality
                };

                RouteScore {
                    matched_tokens: tokens,
                    tier_preference: tier,
                    locality_preference: final_locality,
                    load: load(candidate).saturating_add(downstream).saturating_neg(),
                }
            })
            .collect()
    }
}
