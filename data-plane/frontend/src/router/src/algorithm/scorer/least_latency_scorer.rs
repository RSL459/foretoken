// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Scoring prefill and decode latency at the eligible target-average request length.

use crate::{
    RouteCandidate, RouteScore, RouteScorer, RouterRequest, RoutingProgress, RoutingStage,
};
use foretoken_kv_indexer::KvPrefixIndexer;
use std::collections::BTreeSet;

/// Prefers lower expected latency using daily request lengths and cumulative latency means.
#[derive(Default)]
pub struct LeastLatencyScorer;

/// Ranks an available latency cost above candidates without complete observations.
fn cost_score(cost: Option<f64>) -> RouteScore {
    RouteScore {
        preference: cost.map_or(f64::NEG_INFINITY, |cost| -cost),
    }
}

impl RouteScorer for LeastLatencyScorer {
    fn needs_request_length_history(&self) -> bool {
        true
    }

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
        // Metrics belong to targets, so expanding DP ranks must not reweight their means.
        // Length observations contribute even when another metric leaves that candidate unscored.
        let mut seen_targets = BTreeSet::new();
        let mut prompt_sum = 0.0;
        let mut prompt_count = 0;
        let mut generation_sum = 0.0;
        let mut generation_count = 0;
        for candidate in candidates {
            if !candidate.stage_eligible || !seen_targets.insert(&candidate.route_target_id) {
                continue;
            }
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
                    return cost_score(None);
                };
                let metric = &stats.request_cost;
                let (Some(_), Some(prompt), Some(prefill), Some(generation), Some(decode)) = (
                    metric.queue_seconds,
                    stats.prompt_tokens_per_request,
                    metric.prefill_seconds,
                    stats.generation_tokens_per_request,
                    metric.decode_seconds,
                ) else {
                    return cost_score(None);
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
                // AIBrix requires the queue histogram but reads GetSimpleValue(), which is zero.
                let prefill_latency = prefill.mean() / avg_prompt_tokens * guess_prompt_tokens;
                let decode_latency =
                    decode.mean() / avg_generation_tokens * guess_generation_tokens;
                let cost = 0.0 + prefill_latency + decode_latency;
                // RouteScore has no validity bit; keep undefined costs out of total ordering.
                cost_score(cost.is_finite().then_some(cost))
            })
            .collect()
    }

    /// Chooses a random eligible target only when no selectable target has latency observations.
    fn score_for_selection(
        &self,
        request: &RouterRequest,
        candidates: &[RouteCandidate],
        kv_prefix_indexer: &dyn KvPrefixIndexer,
        routing_progress: &RoutingProgress<'_>,
        customized_context: &mut (),
    ) -> super::ScoringOutcome {
        let mut scores = self.score(
            request,
            candidates,
            kv_prefix_indexer,
            routing_progress,
            customized_context,
        );
        let selectable = candidates
            .iter()
            .enumerate()
            .filter(|(_, candidate)| {
                candidate.stage_eligible
                    && (routing_progress.current_stage != RoutingStage::Initial
                        || !request.busy_targets.contains(&(
                            candidate.route_target_id.clone(),
                            candidate.data_parallel_rank,
                        )))
            })
            .map(|(index, _)| index)
            .collect::<Vec<_>>();
        if !selectable
            .iter()
            .any(|&index| scores[index].preference.is_finite())
            && !selectable.is_empty()
        {
            scores[selectable[fastrand::usize(0..selectable.len())]].preference = 0.0;
        }
        scores.into()
    }
}
