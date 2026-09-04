// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Scoring by scheduler waiting-queue depth.

use std::sync::Arc;

use foretoken_kv_indexer::KvPrefixIndexer;

use super::{least_loaded_scores, metric_score, pipeline_sum_penalties};
use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, ScorerDescriptor};

inventory::submit! {
    ScorerDescriptor {
        name: "queue_depth",
        factory: || Arc::new(QueueDepthScorer),
    }
}

/// Prefers the route with the fewest requests waiting in the engine scheduler.
///
/// Encoder and Prefill routes include the shallowest downstream queues in the same pipeline scope.
/// This request-count metric assumes comparable engines within one routed model. If any candidate
/// lacks the scheduler gauge, the complete round falls back to the built-in least-loaded policy.
#[derive(Default)]
pub struct QueueDepthScorer;

impl QueueDepthScorer {
    /// Returns requests waiting in the candidate's engine scheduler.
    fn queue_depth(candidate: &RouteCandidate) -> Option<i64> {
        i64::try_from(
            candidate
                .route_target_stats
                .as_ref()?
                .scheduler_waiting_requests?,
        )
        .ok()
    }
}

impl RouteScorer for QueueDepthScorer {
    fn score(
        &self,
        _: &RouterRequest,
        candidates: &[RouteCandidate],
        _: &dyn KvPrefixIndexer,
        _: &mut (),
    ) -> Vec<RouteScore> {
        let Some(penalties) = pipeline_sum_penalties(candidates, Self::queue_depth) else {
            return least_loaded_scores(candidates);
        };
        penalties.into_iter().map(metric_score).collect()
    }
}
