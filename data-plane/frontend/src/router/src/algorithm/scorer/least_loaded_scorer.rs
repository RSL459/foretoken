// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Scoring by current route target load.

use foretoken_kv_indexer::KvPrefixIndexer;

use super::{RouteScorerResult, least_loaded_result};
use crate::{RouteCandidate, RouteScorer, RouterRequest};

/// Applies AIBrix's least-request policy to exact-rank admitted plus pending request counts.
#[derive(Default)]
pub struct LeastLoadedScorer;

impl RouteScorer for LeastLoadedScorer {
    #[allow(unused_variables)]
    fn score(
        &self,
        request: &RouterRequest,
        candidates: &[RouteCandidate],
        kv_prefix_indexer: &dyn KvPrefixIndexer,
        customized_context: &mut (),
    ) -> RouteScorerResult {
        least_loaded_result(candidates)
    }
}
