// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Scoring by sequence length distribution and current load.
//! Routes requests with similar sequence lengths to the same nodes to reduce fragmentation and optimize batching.

use foretoken_kv_indexer::KvPrefixIndexer;
use foretoken_model_protocol::ModelServerRole;

use super::{decode_loads_by_pipeline_scope, kv_prefix_best_match, load};
use std::sync::Arc;

use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, ScorerDescriptor};

inventory::submit! {
    ScorerDescriptor {
        name: "sequence_length_aware",
        factory: || Arc::new(SequenceLengthAwareScorer::default()),
    }
}

/// Divides the raw token-length difference before adding it to the load penalty. This scales the
/// sequence-length signal to the same magnitude as `running_requests` so it acts as a meaningful
/// tie-breaker without dominating the load term.
const SEQUENCE_LENGTH_PENALTY_DIVISOR: i64 = 256;

/// Prefers candidates whose current sequence length profile matches the request's sequence length,
/// optimizing for batching efficiency, followed by KV locality and load.
///
/// The sequence-length penalty lands in the final `RouteScore::load` tie-breaker: KV-prefix match
/// length, tier, and locality still rank first lexicographically.
#[derive(Default)]
pub struct SequenceLengthAwareScorer;

impl RouteScorer for SequenceLengthAwareScorer {
    fn score(
        &self,
        request: &RouterRequest,
        candidates: &[RouteCandidate],
        kv: &dyn KvPrefixIndexer,
        _: &mut (),
    ) -> Vec<RouteScore> {
        let decode_loads = decode_loads_by_pipeline_scope(candidates);
        // 计算预估的总序列长度 (Prompt + 预估生成的 Token 数)
        let request_seq_len = request.token_count() as i64 + request.max_new_tokens() as i64;

        candidates
            .iter()
            .map(|candidate| {
                // 1. 获取 KV Prefix 匹配情况
                let (tokens, tier, locality) = kv_prefix_best_match(request, candidate, kv);

                // 2. 序列长度差异计算 (Sequence Length Penalty)
                // 如果缺乏统计数据，则默认不产生惩罚
                let candidate_avg_seq_len = candidate
                    .route_target_stats
                    .as_ref()
                    .and_then(|stats| stats.avg_sequence_length)
                    .and_then(|len| i64::try_from(len).ok())
                    .unwrap_or(request_seq_len);

                // 绝对差异按 Chunk 大小做平滑，使惩罚量与并发负载(个位数~几十)同一量级
                let seq_len_diff_penalty = request_seq_len.abs_diff(candidate_avg_seq_len) as i64
                    / SEQUENCE_LENGTH_PENALTY_DIVISOR;

                // 3. 计算基础负载与下游节点负载
                let downstream = if candidate.role == ModelServerRole::Prefill {
                    decode_loads
                        .get(&candidate.pipeline_scope_id)
                        .copied()
                        .unwrap_or(0)
                } else {
                    0
                };

                let base_load = load(candidate).saturating_add(downstream);

                // 结合基础负载与序列长度差异惩罚 (值越大代表负面影响越大)
                let total_penalty = base_load.saturating_add(seq_len_diff_penalty);

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
