// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Scoring by measured KV-cache utilization.

use std::sync::Arc;

use foretoken_kv_indexer::KvPrefixIndexer;

use super::{least_loaded_scores, metric_score, ordered_nonnegative_f64, pipeline_max_penalties};
use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, ScorerDescriptor};

inventory::submit! {
    ScorerDescriptor {
        name: "kv_cache_utilization",
        factory: || Arc::new(KvCacheUtilizationScorer),
    }
}

/// Prefers the route or E/P/D pipeline with the lowest measured KV-cache pressure.
///
/// The raw `0.0..=1.0` gauge is ordered directly without heuristic thresholds. Encoder and Prefill
/// routes are ranked by the most-utilized required stage after choosing the least-utilized option
/// for each downstream role. Missing, non-finite, or out-of-range telemetry makes the complete
/// round fall back to the built-in least-loaded policy.
#[derive(Default)]
pub struct KvCacheUtilizationScorer;

impl KvCacheUtilizationScorer {
    /// Returns validated KV-cache utilization.
    fn utilization(candidate: &RouteCandidate) -> Option<f64> {
        let usage = candidate.route_target_stats.as_ref()?.kv_cache_usage?;
        if !(0.0..=1.0).contains(&usage) {
            return None;
        }
        Some(usage)
    }
}

impl RouteScorer for KvCacheUtilizationScorer {
    fn score(
        &self,
        _: &RouterRequest,
        candidates: &[RouteCandidate],
        _: &dyn KvPrefixIndexer,
        _: &mut (),
    ) -> Vec<RouteScore> {
        let Some(penalties) = pipeline_max_penalties(candidates, |candidate| {
            ordered_nonnegative_f64(Self::utilization(candidate)?)
        }) else {
            return least_loaded_scores(candidates);
        };
        penalties.into_iter().map(metric_score).collect()
    }
}
