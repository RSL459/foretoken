// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Scoring by LoRA adapter locality.
//! Prefers routing requests to nodes that already have the requested LoRA adapter loaded in GPU memory.

use foretoken_kv_indexer::KvPrefixIndexer;
use foretoken_model_protocol::ModelServerRole;

use super::{decode_loads_by_pipeline_scope, kv_prefix_best_match, load};
use std::sync::Arc;

use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, ScorerDescriptor};

inventory::submit! {
    ScorerDescriptor {
        name: "lora_aware",
        factory: || Arc::new(LoraAwareScorer),
    }
}

/// Prefers candidates that already have the requested LoRA adapter loaded.
///
/// A loaded-adapter hit raises `locality_preference`, which ranks after `matched_tokens` and
/// `tier_preference` in the lexicographic `RouteScore`: a much longer KV-prefix match on another
/// candidate still wins, but LoRA affinity beats locality among otherwise-equal candidates.
#[derive(Default)]
pub struct LoraAwareScorer;

impl RouteScorer for LoraAwareScorer {
    fn score(
        &self,
        request: &RouterRequest,
        candidates: &[RouteCandidate],
        kv: &dyn KvPrefixIndexer,
        _: &mut (),
    ) -> Vec<RouteScore> {
        let decode_loads = decode_loads_by_pipeline_scope(candidates);
        // The LoRA adapter requested by this request.
        let request_lora_id = request.lora_id();

        candidates
            .iter()
            .map(|candidate| {
                let (tokens, tier, mut locality) = kv_prefix_best_match(request, candidate, kv);

                // LoRA affinity match: check whether the candidate already has that adapter loaded
                // in GPU memory.
                if let Some(req_lora) = request_lora_id {
                    let has_lora_loaded = candidate
                        .route_target_stats
                        .as_ref()
                        .map(|stats| {
                            stats
                                .loaded_lora_adapters
                                .iter()
                                .any(|adapter| adapter.as_str() == req_lora)
                        })
                        .unwrap_or(false);

                    if has_lora_loaded {
                        // Grant a high locality preference to avoid unnecessary adapter swap in/out overhead.
                        locality = locality.saturating_add(20);
                    }
                }

                let downstream = if candidate.role == ModelServerRole::Prefill {
                    decode_loads
                        .get(&candidate.pipeline_scope_id)
                        .copied()
                        .unwrap_or(0)
                } else {
                    0
                };

                RouteScore {
                    matched_tokens: tokens,
                    tier_preference: tier,
                    locality_preference: locality,
                    load: load(candidate).saturating_add(downstream).saturating_neg(),
                }
            })
            .collect()
    }
}
