// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Scoring purely by KV-prefix locality.

use std::sync::Arc;

use foretoken_kv_indexer::KvPrefixIndexer;

use super::kv_prefix_best_match;
use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, ScorerDescriptor};

inventory::submit! {
    ScorerDescriptor {
        name: "prefix",
        factory: || Arc::new(PrefixScorer),
    }
}

/// Prefers longer confirmed-locality KV-prefix matches without considering current target load.
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
                let (matched_tokens, tier_preference, locality_preference) =
                    kv_prefix_best_match(request, candidate, kv);
                RouteScore {
                    matched_tokens,
                    tier_preference,
                    locality_preference,
                    load: 0,
                }
            })
            .collect()
    }
}
