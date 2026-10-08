// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
// SPDX-FileCopyrightText: Copyright 2024 The Aibrix Team

//! Scoring daily mean request lengths with twice the weight on prompt tokens.

use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, RoutingProgress};
use foretoken_kv_indexer::KvPrefixIndexer;

/// Prefers smaller weighted request lengths using AIBrix's throughput cost.
#[derive(Default)]
pub struct ThroughputScorer;

impl RouteScorer for ThroughputScorer {
    /// Returns native token costs for Router; candidates missing either mean remain unscored.
    fn score(
        &self,
        _request: &RouterRequest,
        candidates: &[RouteCandidate],
        _kv_prefix_indexer: &dyn KvPrefixIndexer,
        _routing_progress: &RoutingProgress<'_>,
        _customized_context: &mut (),
    ) -> Vec<RouteScore> {
        candidates
            .iter()
            .map(|candidate| {
                let Some(stats) = &candidate.route_target_stats else {
                    return super::cost_score(None);
                };
                let (Some(prompt), Some(generation)) = (
                    stats.prompt_tokens_per_request,
                    stats.generation_tokens_per_request,
                ) else {
                    return super::cost_score(None);
                };
                // An idle daily range has an undefined 0/0 mean, not a zero-token request.
                // Do not let a NaN participate in the picker's total floating-point ordering.
                let cost = 2.0 * prompt + generation;
                if cost.is_finite() {
                    super::cost_score(Some(cost))
                } else {
                    super::cost_score(None)
                }
            })
            .collect()
    }
}
