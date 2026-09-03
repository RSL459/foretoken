// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Candidate scoring and Scorer implementations.

mod capacity_aware_scorer;
mod kv_cache_utilization_scorer;
mod kv_least_loaded_scorer;
mod latency_aware_scorer;
mod least_loaded_scorer;
mod lora_aware_scorer;
mod mmcache_affinity_scorer;
mod prefix_decay_scorer;
mod prefix_scorer;
mod queue_depth_scorer;
mod running_request_scorer;
mod sequence_length_aware_scorer;
mod session_aware_scorer;
mod throughput_aware_scorer;
mod uniform_scorer;
mod weighted_sum_scorer;

use std::collections::BTreeMap;

use foretoken_kv_indexer::KvPrefixIndexer;
use foretoken_model_protocol::{KvCacheLocality, KvStorageTier, ModelServerRole};

use crate::{RouteCandidate, RouteScore, RouterRequest};

pub use capacity_aware_scorer::CapacityAwareScorer;
pub use kv_cache_utilization_scorer::KvCacheUtilizationScorer;
pub use kv_least_loaded_scorer::KvLeastLoadedScorer;
pub use latency_aware_scorer::LatencyAwareScorer;
pub use least_loaded_scorer::LeastLoadedScorer;
pub use lora_aware_scorer::LoraAwareScorer;
pub use mmcache_affinity_scorer::MmcacheAffinityScorer;
pub use prefix_decay_scorer::PrefixDecayScorer;
pub use prefix_scorer::PrefixScorer;
pub use queue_depth_scorer::QueueDepthScorer;
pub use running_request_scorer::RunningRequestScorer;
pub use sequence_length_aware_scorer::SequenceLengthAwareScorer;
pub use session_aware_scorer::SessionAwareScorer;
pub use throughput_aware_scorer::ThroughputAwareScorer;
pub use uniform_scorer::UniformScorer;
pub use weighted_sum_scorer::WeightedSumScorer;

/// Scores the complete filtered compatible, healthy route target snapshot for one routing round.
///
/// The returned score slice is parallel to `candidates`: position `n` scores candidate `n`. This
/// lets a scorer express ranking without echoing candidate identity or metadata. The Router
/// applies execution-stage and E/P/D route-set eligibility only after scores are available.
///
/// - `request`: model, prompt tokens, sampling, multimodal, LoRA, and priority.
/// - `candidates`: Filter output with route metadata and the Router's immutable current-round
///   aggregate target observation, when telemetry is available.
/// - `kv_prefix_indexer`: query local or offloaded matched prompt tokens for any candidate.
/// - `customized_context`: user-defined `C`, created per request and shared by Prefill and Decode.
///
/// Returns one score for every input candidate. A length mismatch is reported as a routing error.
pub trait RouteScorer<C: Send + 'static = ()>: Send + Sync {
    fn score(
        &self,
        request: &RouterRequest,
        candidates: &[RouteCandidate],
        kv_prefix_indexer: &dyn KvPrefixIndexer,
        customized_context: &mut C,
    ) -> Vec<RouteScore>;
}

/// Returns the best available view of a candidate's current engine request load.
///
/// Model-server admission and vLLM scheduler gauges overlap, so the load is their maximum rather
/// than their sum. Built-in load scorers consume this derived value; the candidate retains its
/// telemetry snapshot.
pub(crate) fn load(candidate: &RouteCandidate) -> i64 {
    candidate.route_target_stats.as_ref().map_or(0, |stats| {
        let scheduler_requests = stats
            .scheduler_running_requests
            .unwrap_or(0)
            .saturating_add(stats.scheduler_waiting_requests.unwrap_or(0));
        let requests = stats.running_requests.max(scheduler_requests);
        i64::try_from(requests).unwrap_or(i64::MAX)
    })
}

/// Returns the least model-server route load among Decode eligible route options in each E/P/D route set.
pub(crate) fn decode_loads_by_pipeline_scope(
    candidates: &[RouteCandidate],
) -> BTreeMap<Option<String>, i64> {
    let mut loads = BTreeMap::new();
    for candidate in candidates
        .iter()
        .filter(|candidate| candidate.role == ModelServerRole::Decode)
    {
        loads
            .entry(candidate.pipeline_scope_id.clone())
            .and_modify(|current: &mut i64| *current = (*current).min(load(candidate)))
            .or_insert_with(|| load(candidate));
    }
    loads
}

/// Best readable KV-prefix match facts for `request` on `candidate`, or zeros when the candidate
/// role does not consume prompt tokens or prefix locality is unavailable.
///
/// Returns `(matched_tokens, tier_preference, locality_preference)` already in their final
/// lexicographic `RouteScore` forms. Providers outside this crate are not trusted to have applied
/// indexer filtering: unknown locality is equivalent to no cache match.
pub(crate) fn kv_prefix_best_match(
    request: &RouterRequest,
    candidate: &RouteCandidate,
    kv: &dyn KvPrefixIndexer,
) -> (i64, i8, i8) {
    if !matches!(
        candidate.role,
        ModelServerRole::Aggregate | ModelServerRole::Prefill
    ) {
        // Decode consumes generated tokens, not the prompt KV prefix.
        return (0, 0, 0);
    }
    let lookup = request.kv_prefix_lookup(
        candidate.route_target_id.as_str(),
        candidate.data_parallel_rank,
    );
    match lookup.map_or_else(
        foretoken_kv_indexer::KvPrefixQueryResult::Unavailable,
        |lookup| kv.prefix_matches(lookup),
    ) {
        foretoken_kv_indexer::KvPrefixQueryResult::Matches(matches) => matches
            .into_iter()
            .filter(|m| m.placement.locality != KvCacheLocality::Unspecified)
            .max_by_key(|m| {
                (
                    m.matched_tokens,
                    tier_preference(m.placement.tier),
                    locality_preference(m.placement.locality),
                )
            })
            .map(|m| {
                (
                    i64::try_from(m.matched_tokens).unwrap_or(i64::MAX),
                    tier_preference(m.placement.tier),
                    locality_preference(m.placement.locality),
                )
            })
            .unwrap_or((0, 0, 0)),
        foretoken_kv_indexer::KvPrefixQueryResult::Unavailable(_) => (0, 0, 0),
    }
}

/// Lexicographic policy deliberately has no measured weights.
pub(crate) fn tier_preference(t: KvStorageTier) -> i8 {
    match t {
        KvStorageTier::Device => 4,
        KvStorageTier::HostPinned => 3,
        KvStorageTier::Disk => 2,
        KvStorageTier::External => 1,
    }
}

/// Lexicographic policy deliberately has no measured weights.
pub(crate) fn locality_preference(locality: KvCacheLocality) -> i8 {
    match locality {
        KvCacheLocality::Unspecified => 0,
        KvCacheLocality::Local => 2,
        KvCacheLocality::Remote => 1,
    }
}
