// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
// SPDX-FileCopyrightText: Copyright 2025 The Kubernetes Authors

//! llm-d running-request scoring over the scheduler running gauge.

use foretoken_kv_indexer::KvPrefixIndexer;

use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, RoutingProgress};

/// Scores each candidate by `(max_running - running) / (max_running - min_running)`.
/// Equal counts receive one; only scheduler running requests contribute to the score.
#[derive(Default)]
pub struct RunningRequestScorer;

impl RouteScorer for RunningRequestScorer {
    fn score(
        &self,
        _: &RouterRequest,
        candidates: &[RouteCandidate],
        _: &dyn KvPrefixIndexer,
        _: &RoutingProgress<'_>,
        _: &mut (),
    ) -> Vec<RouteScore> {
        super::relative_request_scores(candidates, |stats| stats.scheduler_running_requests)
    }
}
