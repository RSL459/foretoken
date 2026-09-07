// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
// SPDX-FileCopyrightText: Copyright 2025 The Kubernetes Authors

//! llm-d queue-depth scoring over the scheduler waiting gauge.

use foretoken_kv_indexer::KvPrefixIndexer;

use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, RoutingProgress};

/// Scores each candidate by `(max_waiting - waiting) / (max_waiting - min_waiting)`.
/// Equal counts receive one; Router retains ownership of stage eligibility and picking.
#[derive(Default)]
pub struct QueueDepthScorer;

impl RouteScorer for QueueDepthScorer {
    fn score(
        &self,
        _: &RouterRequest,
        candidates: &[RouteCandidate],
        _: &dyn KvPrefixIndexer,
        _: &RoutingProgress<'_>,
        _: &mut (),
    ) -> Vec<RouteScore> {
        super::relative_request_scores(candidates, |stats| stats.scheduler_waiting_requests)
    }
}
