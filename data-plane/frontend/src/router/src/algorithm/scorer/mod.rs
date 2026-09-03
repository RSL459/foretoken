// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Candidate scoring and Scorer implementations.

mod kv_least_loaded_scorer;
mod least_loaded_scorer;
mod prefix_scorer;
mod uniform_scorer;

use std::collections::BTreeMap;

use foretoken_kv_indexer::KvPrefixIndexer;
use foretoken_model_protocol::{KvCacheLocality, KvStorageTier, ModelServerRole};

use crate::{RouteCandidate, RouteScore, RouterRequest};

pub use kv_least_loaded_scorer::KvLeastLoadedScorer;
pub use least_loaded_scorer::LeastLoadedScorer;
pub use prefix_scorer::PrefixScorer;
pub use uniform_scorer::UniformScorer;

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

/// Returns the best readable KV-prefix match for a prompt-consuming candidate.
///
/// The tuple is already converted to the lexicographic fields used by `RouteScore`:
/// `(matched_tokens, tier_preference, locality_preference)`. Providers outside this crate are not
/// trusted to have filtered unknown locality, so an unspecified locality is equivalent to no
/// confirmed cache match.
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
            .filter(|matched| matched.placement.locality != KvCacheLocality::Unspecified)
            .max_by_key(|matched| {
                (
                    matched.matched_tokens,
                    tier_preference(matched.placement.tier),
                    locality_preference(matched.placement.locality),
                )
            })
            .map(|matched| {
                (
                    i64::try_from(matched.matched_tokens).unwrap_or(i64::MAX),
                    tier_preference(matched.placement.tier),
                    locality_preference(matched.placement.locality),
                )
            })
            .unwrap_or((0, 0, 0)),
        foretoken_kv_indexer::KvPrefixQueryResult::Unavailable(_) => (0, 0, 0),
    }
}

/// Lexicographic policy deliberately has no measured weights.
fn tier_preference(tier: KvStorageTier) -> i8 {
    match tier {
        KvStorageTier::Device => 4,
        KvStorageTier::HostPinned => 3,
        KvStorageTier::Disk => 2,
        KvStorageTier::External => 1,
    }
}

/// Lexicographic policy deliberately has no measured weights.
fn locality_preference(locality: KvCacheLocality) -> i8 {
    match locality {
        // The scorer filters this value before ranking; retain zero for exhaustive typed handling.
        KvCacheLocality::Unspecified => 0,
        KvCacheLocality::Local => 2,
        KvCacheLocality::Remote => 1,
    }
}
