// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Scoring by a weighted composite of load, latency, KV-cache usage, and throughput.

use foretoken_kv_indexer::KvPrefixIndexer;
use foretoken_model_protocol::ModelServerRole;

use super::{decode_loads_by_pipeline_scope, kv_prefix_best_match, load};
use std::sync::Arc;

use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, ScorerDescriptor};

inventory::submit! {
    ScorerDescriptor {
        name: "weighted_sum",
        factory: || Arc::new(WeightedSumScorer::default()),
    }
}

/// Fixed sub-score weights (larger weight = more influence on the final penalty). The Router's
/// descriptor registry has no per-scorer configuration, so these are compile-time constants; a
/// configurable variant would extend `ScorerDescriptor` with a parameterized factory.
const LOAD_WEIGHT: f64 = 40.0;
const LATENCY_WEIGHT: f64 = 30.0;
const CACHE_USAGE_WEIGHT: f64 = 20.0;
const THROUGHPUT_WEIGHT: f64 = 10.0;

/// Reference value used to normalize latency into a `0.0..=1.0` sub-penalty.
const LATENCY_REFERENCE_MS: f64 = 1_000.0;
/// Reference throughput (tokens per second) used to normalize inverse throughput into `0.0..=1.0`.
const THROUGHPUT_REFERENCE_TPS: f64 = 100.0;

/// Prefers candidates by a weighted combination of load, latency, KV-cache usage, and throughput,
/// after KV-prefix locality.
///
/// Mirrors AIBrix's `multiStrategyRouter`: each secondary signal is normalized to a comparable
/// scale and combined with fixed weights into the final `RouteScore::load` tie-breaker. KV-prefix
/// match length, tier, and locality still rank first lexicographically.
#[derive(Default)]
pub struct WeightedSumScorer;

impl WeightedSumScorer {
    /// Normalized load sub-penalty in `0.0..=1.0` (concurrency utilization).
    fn load_utilization(&self, candidate: &RouteCandidate) -> f64 {
        let running = load(candidate) as f64;
        let max_concurrent = candidate
            .route_target_stats
            .as_ref()
            .map(|stats| stats.max_concurrent_requests as f64)
            .unwrap_or(0.0);
        if max_concurrent > 0.0 {
            (running / max_concurrent).clamp(0.0, 1.0)
        } else {
            // Saturating toward 1.0 when the concurrency limit is unreported.
            (running / (running + 1.0)).clamp(0.0, 1.0)
        }
    }

    /// Normalized latency sub-penalty in `0.0..=1.0`. Processing latency is TTFT plus TPOT scaled
    /// by expected generated tokens, falling back to the end-to-end average when the finer-grained
    /// gauges are absent.
    fn latency_utilization(&self, candidate: &RouteCandidate, request: &RouterRequest) -> f64 {
        let latency_ms = candidate
            .route_target_stats
            .as_ref()
            .map(|stats| {
                let ttft_ms = stats
                    .ttft
                    .as_ref()
                    .map(|latency| latency.average_ms)
                    .unwrap_or(0.0);
                let tpot_ms = stats
                    .tpot
                    .as_ref()
                    .map(|latency| latency.average_ms)
                    .unwrap_or(0.0);
                if ttft_ms > 0.0 || tpot_ms > 0.0 {
                    ttft_ms + tpot_ms * f64::from(request.max_new_tokens())
                } else {
                    stats
                        .e2e_latency
                        .as_ref()
                        .map(|latency| latency.average_ms)
                        .unwrap_or(0.0)
                }
            })
            .unwrap_or(0.0);
        (latency_ms / LATENCY_REFERENCE_MS).clamp(0.0, 1.0)
    }

    /// Normalized KV-cache-usage sub-penalty in `0.0..=1.0`. `kv_cache_usage` is already in that
    /// range; the clamp is defensive against an out-of-range upstream value.
    fn cache_usage_utilization(&self, candidate: &RouteCandidate) -> f64 {
        candidate
            .route_target_stats
            .as_ref()
            .and_then(|stats| stats.kv_cache_usage)
            .map(|usage| usage.clamp(0.0, 1.0))
            .unwrap_or(0.0)
    }

    /// Normalized inverse-throughput sub-penalty in `0.0..=1.0` (lower is better). A node with no
    /// throughput observation is treated as neutral (zero penalty).
    fn inverse_throughput(&self, candidate: &RouteCandidate) -> f64 {
        candidate
            .route_target_stats
            .as_ref()
            .map(|stats| {
                let prompt_tps = stats.prompt_tokens_per_second.unwrap_or(0.0);
                let generation_tps = stats.generation_tokens_per_second.unwrap_or(0.0);
                let total_tps = prompt_tps + generation_tps;
                if total_tps > 0.0 {
                    (THROUGHPUT_REFERENCE_TPS / total_tps).clamp(0.0, 1.0)
                } else {
                    0.0
                }
            })
            .unwrap_or(0.0)
    }

    /// Weighted composite penalty; larger is worse.
    fn composite_penalty(&self, candidate: &RouteCandidate, request: &RouterRequest) -> i64 {
        let penalty = LOAD_WEIGHT * self.load_utilization(candidate)
            + LATENCY_WEIGHT * self.latency_utilization(candidate, request)
            + CACHE_USAGE_WEIGHT * self.cache_usage_utilization(candidate)
            + THROUGHPUT_WEIGHT * self.inverse_throughput(candidate);
        penalty as i64
    }
}

impl RouteScorer for WeightedSumScorer {
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
                let (tokens, tier, locality) = kv_prefix_best_match(request, candidate, kv);

                let downstream = if candidate.role == ModelServerRole::Prefill {
                    decode_loads
                        .get(&candidate.pipeline_scope_id)
                        .copied()
                        .unwrap_or(0)
                } else {
                    0
                };

                let total_penalty = self
                    .composite_penalty(candidate, request)
                    .saturating_add(downstream);

                RouteScore {
                    matched_tokens: tokens,
                    tier_preference: tier,
                    locality_preference: locality,
                    load: total_penalty.saturating_neg(),
                }
            })
            .collect()
    }
}
