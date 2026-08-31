// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Scoring by estimated latency (TTFT, TPOT, queue delay, and downstream Decode latency).

use foretoken_kv_indexer::KvPrefixIndexer;
use foretoken_model_protocol::ModelServerRole;

use super::{decode_loads_by_pipeline_scope, kv_prefix_best_match};
use std::sync::Arc;

use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, ScorerDescriptor};

inventory::submit! {
    ScorerDescriptor {
        name: "latency_aware",
        factory: || Arc::new(LatencyAwareScorer::default()),
    }
}

/// Prefers candidates with lower overall estimated latency (TTFT / queue duration)
/// and considers KV-prefix hit savings as well as downstream Decode latency for Prefill targets.
///
/// The latency estimate lands in the final `RouteScore::load` tie-breaker: KV-prefix match length,
/// tier, and locality still rank first lexicographically.
#[derive(Default)]
pub struct LatencyAwareScorer;

impl LatencyAwareScorer {
    /// Estimates candidate queue and processing latency in milliseconds.
    ///
    /// Processing latency is TTFT (time to first token) plus per-output-token latency (TPOT) scaled
    /// by the expected number of generated tokens, falling back to the reported end-to-end average
    /// when the finer-grained gauges are absent. Queue delay is added on top using the scheduler
    /// waiting-request count (or total running requests when the queue gauge is missing).
    fn estimate_candidate_latency(candidate: &RouteCandidate, request: &RouterRequest) -> i64 {
        candidate
            .route_target_stats
            .as_ref()
            .map(|stats| {
                let waiting = stats
                    .scheduler_waiting_requests
                    .and_then(|n| i64::try_from(n).ok())
                    .unwrap_or_else(|| i64::try_from(stats.running_requests).unwrap_or(0));
                let queue_delay = waiting.saturating_mul(10); // ~10ms base delay per queued request

                let ttft_ms = stats
                    .ttft
                    .as_ref()
                    .map(|latency| latency.average_ms as i64)
                    .unwrap_or(0);
                let tpot_ms = stats
                    .tpot
                    .as_ref()
                    .map(|latency| latency.average_ms as i64)
                    .unwrap_or(0);

                let processing_ms = if ttft_ms > 0 || tpot_ms > 0 {
                    ttft_ms.saturating_add(tpot_ms.saturating_mul(i64::from(request.max_new_tokens())))
                } else {
                    stats
                        .e2e_latency
                        .as_ref()
                        .map(|latency| latency.average_ms as i64)
                        .unwrap_or(0)
                };

                processing_ms.saturating_add(queue_delay)
            })
            .unwrap_or(0)
    }
}

impl RouteScorer for LatencyAwareScorer {
    fn score(
        &self,
        request: &RouterRequest,
        candidates: &[RouteCandidate],
        kv: &dyn KvPrefixIndexer,
        _: &mut (),
    ) -> Vec<RouteScore> {
        let decode_loads = decode_loads_by_pipeline_scope(candidates);

        candidates
            .iter()
            .map(|candidate| {
                // KV prefix hits lower prefill TTFT latency; matched_tokens ranks first in the
                // lexicographic RouteScore, so longer readable prefixes dominate this estimate.
                let (tokens, tier, locality) = kv_prefix_best_match(request, candidate, kv);

                let candidate_latency = Self::estimate_candidate_latency(candidate, request);

                // Downstream Decode load impact for Prefill nodes. This is a request count added
                // as a penalty magnitude, not a physical latency: both are heuristic penalties
                // combined before negation into the final `load` tie-breaker.
                let downstream_load = if candidate.role == ModelServerRole::Prefill {
                    decode_loads
                        .get(&candidate.pipeline_scope_id)
                        .copied()
                        .unwrap_or(0)
                } else {
                    0
                };

                let total_estimated_latency =
                    candidate_latency.saturating_add(downstream_load);

                // Negate latency score because Picker ranks higher scores as better candidate choices
                RouteScore {
                    matched_tokens: tokens,
                    tier_preference: tier,
                    locality_preference: locality,
                    load: total_estimated_latency.saturating_neg(),
                }
            })
            .collect()
    }
}
