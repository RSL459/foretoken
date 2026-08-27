// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Behavior tests for the Dynamo/AIBrix-inspired scorers.

use std::sync::Arc;
use std::time::Duration;

use foretoken_kv_indexer::{
    KvPrefixIndexer, KvPrefixLookup, KvPrefixMatch, KvPrefixMatches, KvPrefixQueryResult,
};
use foretoken_model_protocol::{KvCacheLocality, KvPlacement, KvStorageTier, ModelServerRole};
use foretoken_router::{
    PrefixDecayScorer, RouteCandidate, RouteScorer, RouteTargetLatencyStats, RouteTargetStats,
    ThroughputAwareScorer, WeightedSumScorer,
};

use super::support::{request, route};

fn prefix(tokens: usize) -> KvPrefixMatch {
    KvPrefixMatch {
        event_source_id: "source".into(),
        model_group_id: "owner".into(),
        epoch: "epoch".into(),
        dp_rank: 0,
        placement: KvPlacement {
            tier: KvStorageTier::Device,
            locality: KvCacheLocality::Local,
        },
        matched_complete_blocks: 1,
        matched_tokens: tokens,
        last_matched_hash: None,
    }
}

struct Facts;

impl KvPrefixIndexer for Facts {
    fn prefix_matches(&self, lookup: KvPrefixLookup<'_>) -> KvPrefixQueryResult {
        let tokens = match lookup.route_target_id {
            "busy" => 100,
            "idle" => 60,
            _ => 0,
        };
        KvPrefixQueryResult::Matches(KvPrefixMatches::new(vec![prefix(tokens)]))
    }
}

fn target_stats(build: impl FnOnce(&mut RouteTargetStats)) -> RouteTargetStats {
    let mut stats = RouteTargetStats {
        collected_at_unix_ms: 1,
        observed_window: Duration::from_secs(60),
        running_requests: 0,
        max_concurrent_requests: 0,
        scheduler_running_requests: None,
        scheduler_waiting_requests: None,
        kv_cache_usage: None,
        prompt_tokens_per_second: None,
        generation_tokens_per_second: None,
        ttft: None,
        tpot: None,
        e2e_latency: None,
        avg_sequence_length: None,
        loaded_lora_adapters: vec![],
    };
    build(&mut stats);
    stats
}

fn candidate(id: &str, role: ModelServerRole, stats: RouteTargetStats) -> RouteCandidate {
    let route = route(id, role);
    RouteCandidate {
        route_target_id: route.route_target_id,
        target: route.target,
        admission_targets: route.admission_targets,
        role,
        model: route.model,
        revision: route.revision,
        pipeline_scope_id: route.pipeline_scope_id,
        data_parallel_rank: 0,
        route_target_stats: Some(Arc::new(stats)),
    }
}

#[test]
fn prefix_decay_reduces_a_saturated_candidates_cache_credit() {
    let candidates = vec![
        candidate("busy", ModelServerRole::Aggregate, target_stats(|stats| {
            stats.running_requests = 8;
            stats.max_concurrent_requests = 8;
        })),
        candidate("idle", ModelServerRole::Aggregate, target_stats(|stats| {
            stats.max_concurrent_requests = 8;
        })),
    ];
    let scored = PrefixDecayScorer.score(&request(), &candidates, &Facts, &mut ());

    // "busy" has more raw prefix (100 vs 60) but is fully saturated, so its decayed credit
    // (100 × 0.5 = 50) falls below "idle" (60), proving load decays the cache advantage rather
    // than only breaking ties among equal prefix lengths.
    assert_eq!(scored[0].matched_tokens, 50);
    assert_eq!(scored[1].matched_tokens, 60);
    assert!(scored[1] > scored[0]);
}

#[test]
fn throughput_aware_prefers_higher_observed_throughput() {
    let candidates = vec![
        candidate("slow", ModelServerRole::Aggregate, target_stats(|stats| {
            stats.prompt_tokens_per_second = Some(5.0);
            stats.generation_tokens_per_second = Some(5.0);
        })),
        candidate("fast", ModelServerRole::Aggregate, target_stats(|stats| {
            stats.prompt_tokens_per_second = Some(500.0);
            stats.generation_tokens_per_second = Some(500.0);
        })),
    ];
    let scored = ThroughputAwareScorer.score(&request(), &candidates, &Facts, &mut ());

    assert!(scored[1] > scored[0]);
}

#[test]
fn weighted_sum_trades_load_against_latency() {
    let candidates = vec![
        // More loaded but far lower latency: the weighted composite still prefers it.
        candidate("busy-fast", ModelServerRole::Aggregate, target_stats(|stats| {
            stats.running_requests = 4;
            stats.max_concurrent_requests = 8;
            stats.e2e_latency = Some(RouteTargetLatencyStats {
                samples: 1,
                average_ms: 100.0,
                p95_ms: None,
            });
        })),
        // Idle but very high latency.
        candidate("idle-slow", ModelServerRole::Aggregate, target_stats(|stats| {
            stats.max_concurrent_requests = 8;
            stats.e2e_latency = Some(RouteTargetLatencyStats {
                samples: 1,
                average_ms: 10_000.0,
                p95_ms: None,
            });
        })),
    ];
    let scored = WeightedSumScorer.score(&request(), &candidates, &Facts, &mut ());

    // Load penalty 40×0.5 + latency penalty 30×0.1 = 23 beats idle-but-slow 30×1.0 = 30.
    assert!(scored[0] > scored[1]);
}
