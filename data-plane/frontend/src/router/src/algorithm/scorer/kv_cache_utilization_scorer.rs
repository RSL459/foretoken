// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
// SPDX-FileCopyrightText: Copyright 2025 The Kubernetes Authors

//! llm-d KV-cache utilization scoring over the measured utilization gauge.

use foretoken_kv_indexer::KvPrefixIndexer;

use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, RoutingProgress};

/// Returns `1 - utilization` for each candidate without clamping or adding other signals.
/// An unobserved gauge has llm-d's initial endpoint value of zero utilization.
#[derive(Default)]
pub struct KvCacheUtilizationScorer;

impl RouteScorer for KvCacheUtilizationScorer {
    fn score(
        &self,
        _: &RouterRequest,
        candidates: &[RouteCandidate],
        _: &dyn KvPrefixIndexer,
        _: &RoutingProgress<'_>,
        _: &mut (),
    ) -> Vec<RouteScore> {
        candidates
            .iter()
            .map(|candidate| RouteScore {
                preference: 1.0
                    - candidate
                        .route_target_stats
                        .as_ref()
                        .and_then(|stats| stats.kv_cache_usage)
                        .unwrap_or(0.0),
                ..RouteScore::default()
            })
            .collect()
    }
}
