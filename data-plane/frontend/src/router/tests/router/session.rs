// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Aggregate, P/D, and E/P/D routing session tests.

use std::sync::Arc;
use std::time::Duration;

use foretoken_model_protocol::ModelServerRole;

use super::support::{TestStatsReader, inventory, inventory_with_unhealthy, request, route, stats};
use foretoken_router::algorithm::{AllowAllFilter, LeastLoadedScorer, MaxPicker};
use foretoken_router::{
    PipelineRouter, RouteError, RouteTargetId, RouteTargetRankStats, RouteTargetStats, Router,
    RouterPipeline,
};

fn target_stats(running_requests: u64) -> RouteTargetStats {
    let rank = RouteTargetRankStats {
        running_requests,
        max_running_requests: 8,
        scheduler_running_requests: Some(1),
        scheduler_waiting_requests: Some(2),
        active_prefill_tokens: 0,
        inflight_tokens: 0,
        kv_cache_usage: Some(0.5),
        prompt_tokens_per_second: Some(100.0),
        generation_tokens_per_second: Some(50.0),
        ttft: None,
        tpot: None,
        e2e_latency: None,
    };
    RouteTargetStats {
        collected_at_unix_ms: 1,
        observed_window: Duration::from_secs(60),
        running_requests,
        max_running_requests: 8,
        scheduler_running_requests: Some(1),
        scheduler_waiting_requests: Some(2),
        by_data_parallel_rank: [(0, rank)].into_iter().collect(),
        loaded_lora_adapters: vec![],
        kv_cache_usage: Some(0.5),
    }
}

// Protects aggregate routing identity, explicit rank zero, and stage ordering.
#[test]
fn single_rank_route_returns_an_explicit_rank_zero_decision() {
    let router = PipelineRouter::new(inventory(vec![route("a", ModelServerRole::Aggregate)]));
    let mut session = router.start(request());

    let decision = session.select_initial().unwrap();
    assert_eq!(decision.route_target_id, RouteTargetId::new("a"));
    assert_eq!(decision.role, ModelServerRole::Aggregate);
    assert_eq!(decision.data_parallel_rank, 0);
    assert_eq!(
        session.select_decode(),
        Err(RouteError::DecodeBeforePrefill)
    );
}

// Protects P/D routing from starting work without a serviceable Decode stage.
#[test]
fn prefill_is_not_selected_without_an_available_decode() {
    let router = PipelineRouter::new(inventory(vec![route("p", ModelServerRole::Prefill)]));
    let mut session = router.start(request());

    assert!(matches!(
        session.select_initial(),
        Err(RouteError::NoMatchingRouteTarget { .. })
    ));
}

// Protects E/P/D stage selection from crossing pipeline scopes or skipping the encoder.
#[test]
fn encoder_prefill_decode_stays_in_its_pipeline_scope_and_never_falls_back_without_encoder() {
    let router = PipelineRouter::new(inventory(vec![
        route("e", ModelServerRole::Encoder),
        route("p", ModelServerRole::Prefill),
        route("d", ModelServerRole::Decode),
    ]));
    let mut session = router.start(request());
    assert_eq!(
        session.select_initial().unwrap().route_target_id.as_str(),
        "e"
    );
    assert_eq!(
        session.select_prefill().unwrap().route_target_id.as_str(),
        "p"
    );
    assert_eq!(
        session.select_decode().unwrap().route_target_id.as_str(),
        "d"
    );

    let inventory = inventory_with_unhealthy(
        vec![
            route("e", ModelServerRole::Encoder),
            route("p", ModelServerRole::Prefill),
            route("d", ModelServerRole::Decode),
        ],
        [RouteTargetId::new("e")].into_iter().collect(),
    );
    assert!(matches!(
        PipelineRouter::new(inventory)
            .start(request())
            .select_initial(),
        Err(RouteError::NoMatchingRouteTarget { .. })
    ));
}

// Protects Decode selection from stale observations or premature binding.
#[test]
fn decode_uses_fresh_candidate_stats_and_is_not_bound_during_prefill_selection() {
    let stat_values = stats();
    let router = PipelineRouter::with_pipeline(
        inventory(vec![
            route("p", ModelServerRole::Prefill),
            route("d1", ModelServerRole::Decode),
            route("d2", ModelServerRole::Decode),
        ]),
        RouterPipeline::new(
            Arc::new(AllowAllFilter),
            Arc::new(LeastLoadedScorer),
            Arc::new(MaxPicker),
        ),
    )
    .with_route_target_stats_reader(Arc::new(TestStatsReader::new(stat_values.clone())));
    let mut session = router.start(request());
    assert_eq!(
        session.select_initial().unwrap().route_target_id.as_str(),
        "p"
    );

    stat_values.lock().unwrap().extend([
        (RouteTargetId::new("d1"), target_stats(10)),
        (RouteTargetId::new("d2"), target_stats(1)),
    ]);
    assert_eq!(
        session.select_decode().unwrap().route_target_id.as_str(),
        "d2"
    );
}

// Protects exact pending-dispatch ownership from telemetry-timestamp guesses and leaked counts.
#[test]
fn pending_selection_is_released_by_its_dispatch_completion() {
    let stat_values = stats();
    stat_values.lock().unwrap().extend([
        (RouteTargetId::new("a"), target_stats(0)),
        (RouteTargetId::new("b"), target_stats(0)),
    ]);
    let router = PipelineRouter::with_pipeline(
        inventory(vec![
            route("a", ModelServerRole::Aggregate),
            route("b", ModelServerRole::Aggregate),
        ]),
        RouterPipeline::new(
            Arc::new(AllowAllFilter),
            Arc::new(LeastLoadedScorer),
            Arc::new(MaxPicker),
        ),
    )
    .with_route_target_stats_reader(Arc::new(TestStatsReader::new(stat_values)));

    let request_with_id = |id: &str| {
        let mut value = request();
        Arc::get_mut(&mut value.generate_request)
            .expect("test request has one owner")
            .request_id = id.into();
        value
    };
    let mut first_session = router.start(request_with_id("first"));
    let first = first_session.select_initial().unwrap();
    assert_eq!(first.route_target_id.as_str(), "a");

    let mut second_session = router.start(request_with_id("second"));
    let second = second_session.select_initial().unwrap();
    assert_eq!(second.route_target_id.as_str(), "b");

    first_session.dispatch_complete(&first);
    let mut third_session = router.start(request_with_id("third"));
    let third = third_session.select_initial().unwrap();
    assert_eq!(third.route_target_id.as_str(), "a");
}
