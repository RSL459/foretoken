// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Candidate-list filtering and Filter implementations.

mod allow_all_filter;

use foretoken_kv_indexer::KvPrefixIndexer;

use crate::{CandidateIndex, RouteCandidate, RouteTargetStatsReader, RouterRequest};

pub use allow_all_filter::AllowAllFilter;

/// Filters the complete compatible, healthy route target snapshot for one routing round.
///
/// A filter returns positions from `candidates`, which permits it to retain any subset without
/// returning candidate identities or metadata. The pipeline owns eligibility and later
/// stage/domain narrowing.
///
/// - `request`: model, optional revision, prompt tokens, sampling, multimodal, LoRA, and priority.
/// - `candidates`: routable ModelGroups with ID, scaling target, role, model, revision, and current load.
/// - `kv_prefix_indexer`: query local or offloaded matched prompt tokens for any candidate.
/// - `route_target_stats_reader`: query load, scheduler, KV usage, throughput, and latency for a chosen
///   `Duration`.
/// - `customized_context`: user-defined `C`, created per request and shared by Prefill and Decode.
///
/// Returns indexes of candidates that may continue to scoring. Out-of-range or duplicate indexes
/// are reported as routing errors.
pub trait RouteFilter<C: Send + 'static = ()>: Send + Sync {
    fn filter(
        &self,
        request: &RouterRequest,
        candidates: &[RouteCandidate],
        kv_prefix_indexer: &dyn KvPrefixIndexer,
        route_target_stats_reader: &dyn RouteTargetStatsReader,
        customized_context: &mut C,
    ) -> Vec<CandidateIndex>;
}
