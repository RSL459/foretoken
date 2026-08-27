// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Scoring by Session affinity (stickiness), KV-prefix locality, and current load.

use foretoken_kv_indexer::KvPrefixIndexer;
use foretoken_model_protocol::ModelServerRole;

use super::{decode_loads_by_pipeline_scope, kv_prefix_best_match, load};
use std::sync::Arc;

use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, ScorerDescriptor};

inventory::submit! {
    ScorerDescriptor {
        name: "session_aware",
        factory: || Arc::new(SessionAwareScorer::default()),
    }
}

/// Prefers candidates that hold existing Session affinity (session stickiness),
/// followed by longer confirmed KV-prefix matches, higher cache tier, and lower load.
///
/// The session target is resolved by the caller from `RouterRequest::session_id()` and carried as
/// `RouterRequest::session_target_id`. A hit raises `locality_preference`, which ranks after
/// `matched_tokens` and `tier_preference` in the lexicographic `RouteScore`: a much longer
/// KV-prefix match elsewhere still wins, but session stickiness beats locality among
/// otherwise-equal candidates.
#[derive(Default)]
pub struct SessionAwareScorer;

impl RouteScorer for SessionAwareScorer {
    fn score(
        &self,
        request: &RouterRequest,
        candidates: &[RouteCandidate],
        kv: &dyn KvPrefixIndexer,
        _: &mut (),
    ) -> Vec<RouteScore> {
        let decode_loads = decode_loads_by_pipeline_scope(candidates);

        // 获取请求中携带的 Session 标识或先前的亲和目标节点（若存在）
        let session_target = request.session_target_id();

        candidates
            .iter()
            .map(|candidate| {
                // 1. 判断当前候选节点是否命中该会话的亲和性（Session Affinity Match）
                let is_session_hit = session_target
                    .map(|target_id| target_id == candidate.route_target_id.as_str())
                    .unwrap_or(false);

                // 2. 计算 KV Cache 前缀匹配情况
                let (tokens, tier, locality) = kv_prefix_best_match(request, candidate, kv);

                // 3. 计算 downstream Decode 节点的负载
                let downstream = if candidate.role == ModelServerRole::Prefill {
                    decode_loads
                        .get(&candidate.pipeline_scope_id)
                        .copied()
                        .unwrap_or(0)
                } else {
                    0
                };

                // 4. 若命中 Session 粘性节点，提高 locality_preference 权重或匹配 Tokens 偏好
                //    确保相同 Session 的请求优先落到记录过的历史节点上
                let final_locality = if is_session_hit {
                    // 给 Session 命中赋予最高档的局部性偏好加成
                    locality.saturating_add(10)
                } else {
                    locality
                };

                RouteScore {
                    matched_tokens: tokens,
                    tier_preference: tier,
                    locality_preference: final_locality,
                    load: load(candidate).saturating_add(downstream).saturating_neg(),
                }
            })
            .collect()
    }
}
