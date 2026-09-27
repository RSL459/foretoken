// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
// SPDX-FileCopyrightText: Copyright 2025 The llm-d Authors.

//! Threshold-based waiting-queue scores, ported from llm-d's load-aware-scorer.

use foretoken_kv_indexer::KvPrefixIndexer;
use serde::Deserialize;

use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, RoutingProgress};

/// Gives an empty queue 0.5 and decreases linearly to zero at the configured threshold.
pub struct LoadAwareScorer {
    threshold: f64,
}

impl Default for LoadAwareScorer {
    fn default() -> Self {
        Self { threshold: 128.0 }
    }
}

impl RouteScorer for LoadAwareScorer {
    /// Reads llm-d's integer threshold; missing, null, and nonpositive values use the default.
    fn configure(&mut self, parameters: serde_json::Value) -> Result<(), String> {
        #[derive(Deserialize)]
        #[serde(rename_all = "camelCase")]
        struct Parameters {
            threshold: Option<i64>,
        }
        let parameters: Parameters =
            serde_json::from_value(parameters).map_err(|error| error.to_string())?;
        *self = Self::default();
        if let Some(threshold) = parameters.threshold.filter(|threshold| *threshold > 0) {
            self.threshold = threshold as f64;
        }
        Ok(())
    }

    /// Returns endpoint queue preferences without candidate-relative normalization or KV credit.
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
                let waiting = candidate
                    .route_target_stats
                    .as_ref()
                    .and_then(|stats| stats.scheduler_waiting_requests)
                    .unwrap_or(0) as f64;
                RouteScore {
                    preference: if waiting == 0.0 {
                        0.5
                    } else {
                        0.5 * (1.0 - waiting.min(self.threshold) / self.threshold)
                    },
                    ..RouteScore::default()
                }
            })
            .collect()
    }
}
