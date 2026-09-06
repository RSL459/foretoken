// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Public scorer telemetry and KV request behavior tests.

use std::sync::Arc;
use std::time::Duration;

use foretoken_kv_indexer::{
    KvPrefixIndexer, KvPrefixLookup, KvPrefixMatches, KvPrefixQueryResult,
    KvPrefixUnavailableReason,
};
use foretoken_model_protocol::ModelServerRole;
use foretoken_router::algorithm::{AllowAllFilter, LeastLoadedScorer, MaxPicker};
use foretoken_router::{
    PipelineRouter, RouteCandidate, RouteScorer, RouteTargetId, RouteTargetRankStats,
    RouteTargetStats, Router, RouterPipeline,
};

use super::support::{TestStatsReader, inventory, request, route, stats};

struct NoKvFacts;

impl KvPrefixIndexer for NoKvFacts {
    fn prefix_matches(&self, _: KvPrefixLookup<'_>) -> KvPrefixQueryResult {
        KvPrefixQueryResult::Matches(KvPrefixMatches::default())
    }
}

// Protects cache locality from requests whose cache identity cannot be shared safely.
#[test]
fn kv_lookup_rejects_requests_with_separate_cache_semantics() {
    let mut salted = request();
    Arc::get_mut(&mut salted.generate_request)
        .expect("test request has one owner")
        .cache_salt = Some("tenant-a".into());
    assert!(matches!(
        salted.kv_prefix_lookup("target", 0),
        Err(KvPrefixUnavailableReason::UnsupportedRequest)
    ));

    let mut disabled = request();
    Arc::get_mut(&mut disabled.generate_request)
        .expect("test request has one owner")
        .sampling_params
        .skip_reading_prefix_cache = Some(true);
    assert!(matches!(
        disabled.kv_prefix_lookup("target", 0),
        Err(KvPrefixUnavailableReason::UnsupportedRequest)
    ));
}

fn target_stats(running_requests: u64) -> Arc<RouteTargetStats> {
    let rank = RouteTargetRankStats {
        running_requests,
        max_running_requests: 128,
        scheduler_running_requests: None,
        scheduler_waiting_requests: None,
        active_prefill_tokens: 0,
        inflight_tokens: 0,
        kv_cache_usage: None,
        prompt_tokens_per_second: None,
        generation_tokens_per_second: None,
        ttft: None,
        tpot: None,
        e2e_latency: None,
    };
    Arc::new(RouteTargetStats {
        collected_at_unix_ms: 1,
        observed_window: Duration::from_secs(60),
        running_requests,
        max_running_requests: 128,
        scheduler_running_requests: None,
        scheduler_waiting_requests: None,
        by_data_parallel_rank: [(0, rank)].into_iter().collect(),
        loaded_lora_adapters: vec![],
        kv_cache_usage: None,
    })
}

fn candidate(id: &str, role: ModelServerRole, load: u64) -> RouteCandidate {
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
        route_target_stats: Some(target_stats(load)),
        pending_requests: 0,
        pending_tokens: 0,
    }
}

// Protects path projection from combining a Prefill target with another pipeline's Decode load.
#[test]
fn prefill_downstream_load_is_scoped_to_its_pipeline_scope() {
    let mut prefill_a = route("prefill-a", ModelServerRole::Prefill);
    let mut decode_a = route("decode-a", ModelServerRole::Decode);
    let mut prefill_b = route("prefill-b", ModelServerRole::Prefill);
    let mut decode_b = route("decode-b", ModelServerRole::Decode);
    prefill_a.pipeline_scope_id = Some("pipeline-scope-a".into());
    decode_a.pipeline_scope_id = Some("pipeline-scope-a".into());
    prefill_b.pipeline_scope_id = Some("pipeline-scope-b".into());
    decode_b.pipeline_scope_id = Some("pipeline-scope-b".into());
    let observations = stats();
    observations.lock().unwrap().extend([
        (RouteTargetId::new("prefill-a"), (*target_stats(0)).clone()),
        (RouteTargetId::new("decode-a"), (*target_stats(100)).clone()),
        (RouteTargetId::new("prefill-b"), (*target_stats(10)).clone()),
        (RouteTargetId::new("decode-b"), (*target_stats(1)).clone()),
    ]);
    let router = PipelineRouter::with_pipeline(
        inventory(vec![prefill_a, decode_a, prefill_b, decode_b]),
        RouterPipeline::new(
            Arc::new(AllowAllFilter),
            Arc::new(LeastLoadedScorer),
            Arc::new(MaxPicker),
        ),
    )
    .with_route_target_stats_reader(Arc::new(TestStatsReader::new(observations)))
    .with_kv_prefix_indexer(Arc::new(NoKvFacts));

    assert_eq!(
        router
            .start(request())
            .select_initial()
            .unwrap()
            .route_target_id,
        RouteTargetId::new("prefill-b")
    );
}

// Protects AIBrix least-request semantics from double-counting the scheduler queue.
#[test]
fn least_loaded_uses_model_server_outstanding_requests() {
    let idle = candidate("idle", ModelServerRole::Aggregate, 1);
    let mut queued = candidate("queued", ModelServerRole::Aggregate, 2);
    let queued_stats = Arc::get_mut(queued.route_target_stats.as_mut().unwrap()).unwrap();
    let queued_rank = queued_stats.by_data_parallel_rank.get_mut(&0).unwrap();
    queued_rank.scheduler_running_requests = Some(2);
    queued_rank.scheduler_waiting_requests = Some(5);

    let scores = LeastLoadedScorer.score(&request(), &[idle, queued], &NoKvFacts, &mut ());
    let scores = scores.scores().expect("current load is present");

    assert_eq!(scores[0].value(), 1.0);
    assert_eq!(scores[1].value(), 0.0);
    assert!(scores[0] > scores[1]);
}
