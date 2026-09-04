// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Scoring by the vLLM scheduler's current running-request gauge.

use std::sync::Arc;

use foretoken_kv_indexer::KvPrefixIndexer;

use super::{least_loaded_scores, metric_score, pipeline_sum_penalties};
use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, ScorerDescriptor};

inventory::submit! {
    ScorerDescriptor {
        name: "running_request",
        factory: || Arc::new(RunningRequestScorer),
    }
}

/// Prefers the executable pipeline with the fewest requests currently running in vLLM.
///
/// Missing scheduler gauges make the complete round fall back to Model Server's least-loaded
/// signal instead of treating an unobserved scheduler as idle.
#[derive(Default)]
pub struct RunningRequestScorer;

impl RouteScorer for RunningRequestScorer {
    fn score(
        &self,
        _: &RouterRequest,
        candidates: &[RouteCandidate],
        _: &dyn KvPrefixIndexer,
        _: &mut (),
    ) -> Vec<RouteScore> {
        let Some(penalties) = pipeline_sum_penalties(candidates, |candidate| {
            i64::try_from(
                candidate
                    .route_target_stats
                    .as_ref()?
                    .scheduler_running_requests?,
            )
            .ok()
        }) else {
            return least_loaded_scores(candidates);
        };
        penalties.into_iter().map(metric_score).collect()
    }
}
