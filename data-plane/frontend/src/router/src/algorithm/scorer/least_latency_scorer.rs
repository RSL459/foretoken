// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
// SPDX-FileCopyrightText: Copyright 2024 The Aibrix Team

//! Scoring expected queue, prefill, and decode latency at the candidate-average request length.

use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, RoutingProgress};
use foretoken_kv_indexer::KvPrefixIndexer;

/// Prefers lower expected latency using daily request lengths and cumulative latency means.
#[derive(Default)]
pub struct LeastLatencyScorer;

impl RouteScorer for LeastLatencyScorer {
    /// Returns execution-latency costs or marks candidates with missing observations unscored.
    #[allow(unused_variables)]
    fn score(
        &self,
        request: &RouterRequest,
        candidates: &[RouteCandidate],
        kv_prefix_indexer: &dyn KvPrefixIndexer,
        routing_progress: &RoutingProgress<'_>,
        customized_context: &mut (),
    ) -> Vec<RouteScore> {
        // Estimate a common request length from positive per-candidate means, not pooled samples.
        // Length observations contribute even when another metric leaves that candidate unscored.
        let mut prompt_sum = 0.0;
        let mut prompt_count = 0;
        let mut generation_sum = 0.0;
        let mut generation_count = 0;
        for candidate in candidates {
            let Some(stats) = &candidate.route_target_stats else {
                continue;
            };
            if let Some(mean) = stats.prompt_tokens_per_request
                && mean > 0.0
            {
                prompt_sum += mean;
                prompt_count += 1;
            }
            if let Some(mean) = stats.generation_tokens_per_request
                && mean > 0.0
            {
                generation_sum += mean;
                generation_count += 1;
            }
        }
        let guess_prompt_tokens = if prompt_count > 0 {
            prompt_sum / prompt_count as f64
        } else {
            10.0
        };
        let guess_generation_tokens = if generation_count > 0 {
            generation_sum / generation_count as f64
        } else {
            100.0
        };
        candidates
            .iter()
            .map(|candidate| {
                let Some(stats) = &candidate.route_target_stats else {
                    return super::cost_score(None);
                };
                let metric = &stats.request_cost;
                let (Some(queue), Some(prompt), Some(prefill), Some(generation), Some(decode)) = (
                    metric.queue_seconds,
                    stats.prompt_tokens_per_request,
                    metric.prefill_seconds,
                    stats.generation_tokens_per_request,
                    metric.decode_seconds,
                ) else {
                    return super::cost_score(None);
                };
                let avg_prompt_tokens = if prompt > 0.0 {
                    prompt
                } else {
                    guess_prompt_tokens
                };
                let avg_generation_tokens = if generation > 0.0 {
                    generation
                } else {
                    guess_generation_tokens
                };
                // Preserve AIBrix's division-then-multiplication and left-to-right addition.
                // Foretoken supplies the queue histogram mean, not AIBrix's zero-valued
                // HistogramMetricValue.GetSimpleValue() adapter result.
                let prefill_latency = prefill.mean() / avg_prompt_tokens * guess_prompt_tokens;
                let decode_latency =
                    decode.mean() / avg_generation_tokens * guess_generation_tokens;
                super::cost_score(Some(queue.mean() + prefill_latency + decode_latency))
            })
            .collect()
    }
}
