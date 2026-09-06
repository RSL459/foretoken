// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! vLLM-compatible Prometheus metrics and Foretoken-owned admission telemetry.

use std::collections::BTreeMap;
use std::sync::{Mutex, MutexGuard, OnceLock};
use std::time::{Instant, SystemTime, UNIX_EPOCH};

use axum::extract::{MatchedPath, Request};
use axum::http::header::CONTENT_TYPE;
use axum::http::{HeaderValue, StatusCode};
use axum::middleware::Next;
use axum::response::{IntoResponse, Response};
use foretoken_model_protocol::ModelServerRole;
use foretoken_router::{
    RouteScore, RouteScorerResult, RouteTargetSet, RoutingFallback, RoutingObserver, ScalingTarget,
    ScalingTargetKind,
};
use serde::Serialize;

pub use vllm_metrics::*;

const OPENMETRICS_CONTENT_TYPE: &str = "application/openmetrics-text; version=1.0.0; charset=utf-8";
const EXCLUDED_HANDLERS: &[&str] = &[
    "/metrics",
    "/healthz",
    "/readyz",
    "/statusz",
    "/internal/autoscaling/telemetry",
];

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize)]
pub struct QueuedTarget {
    pub service_uid: String,
    pub target_kind: String,
    pub target_id: String,
}

impl From<&ScalingTarget> for QueuedTarget {
    fn from(target: &ScalingTarget) -> Self {
        Self {
            service_uid: target.service_uid.clone(),
            target_kind: match target.kind {
                ScalingTargetKind::Pool => "Pool",
                ScalingTargetKind::EPDPipelineScope => "EPDPipelineScope",
            }
            .to_owned(),
            target_id: if target.kind == ScalingTargetKind::Pool {
                target.uid.clone()
            } else {
                target.service_uid.clone()
            },
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct AutoscalingTargetTelemetry {
    #[serde(flatten)]
    pub target: QueuedTarget,
    pub runtime_queued_requests: u64,
    pub dispatch_queued_requests: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct AutoscalingTelemetry {
    pub version: u8,
    pub collected_at_unix_ms: u64,
    pub targets: Vec<AutoscalingTargetTelemetry>,
}

#[derive(Debug, Clone, Copy)]
enum QueueStage {
    RuntimePreparation,
    BackendDispatch,
}

#[derive(Debug, Clone, Copy, Default)]
struct QueueCounts {
    runtime_preparation: u64,
    backend_dispatch: u64,
}

static QUEUED: OnceLock<Mutex<BTreeMap<QueuedTarget, QueueCounts>>> = OnceLock::new();
fn queued() -> &'static Mutex<BTreeMap<QueuedTarget, QueueCounts>> {
    QUEUED.get_or_init(|| Mutex::new(BTreeMap::new()))
}
fn queued_lock() -> MutexGuard<'static, BTreeMap<QueuedTarget, QueueCounts>> {
    queued()
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

#[derive(Debug, Clone, Copy, Default)]
struct ScoreTotals {
    count: u64,
    sum: f64,
}

#[derive(Default)]
struct RoutingMetrics {
    scorer_evaluations: BTreeMap<(String, &'static str), u64>,
    scorer_unavailable: BTreeMap<(String, &'static str), u64>,
    scorer_scores: BTreeMap<String, ScoreTotals>,
    fallbacks: BTreeMap<&'static str, u64>,
    selections: BTreeMap<&'static str, ScoreTotals>,
}

static ROUTING: OnceLock<Mutex<RoutingMetrics>> = OnceLock::new();

fn routing_lock() -> MutexGuard<'static, RoutingMetrics> {
    ROUTING
        .get_or_init(|| Mutex::new(RoutingMetrics::default()))
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

/// Process-level observer for low-cardinality scorer availability, scores, and final decisions.
#[derive(Default)]
pub struct RoutingMetricsObserver;

impl RoutingObserver for RoutingMetricsObserver {
    fn observe_scorer(&self, name: &str, result: &RouteScorerResult) {
        let mut metrics = routing_lock();
        let outcome = if matches!(result, RouteScorerResult::Scored(_)) {
            "scored"
        } else {
            "unavailable"
        };
        *metrics
            .scorer_evaluations
            .entry((name.to_owned(), outcome))
            .or_default() += 1;
        match result {
            RouteScorerResult::Scored(scores) => {
                let totals = metrics.scorer_scores.entry(name.to_owned()).or_default();
                for score in scores.iter().copied().filter(|score| score.is_applicable()) {
                    totals.count = totals.count.saturating_add(1);
                    totals.sum += score.value();
                }
            }
            RouteScorerResult::Unavailable(reason) => {
                *metrics
                    .scorer_unavailable
                    .entry((name.to_owned(), reason.as_str()))
                    .or_default() += 1;
            }
        }
    }

    fn observe_fallback(&self, fallback: RoutingFallback) {
        *routing_lock()
            .fallbacks
            .entry(fallback.as_str())
            .or_default() += 1;
    }

    fn observe_selection(&self, role: ModelServerRole, score: RouteScore) {
        let mut metrics = routing_lock();
        let totals = metrics.selections.entry(role_label(role)).or_default();
        totals.count = totals.count.saturating_add(1);
        totals.sum += score.value();
    }
}

fn role_label(role: ModelServerRole) -> &'static str {
    match role {
        ModelServerRole::Aggregate => "aggregate",
        ModelServerRole::Encoder => "encoder",
        ModelServerRole::Prefill => "prefill",
        ModelServerRole::Decode => "decode",
    }
}

/// RAII ownership of one request waiting for admission to a fixed target set.
pub struct QueueGuard {
    targets: Vec<QueuedTarget>,
    stage: QueueStage,
}
impl QueueGuard {
    /// Attributes a request waiting for its model runtime to become ready.
    pub fn runtime_preparation(targets: &RouteTargetSet) -> Self {
        Self::new(targets, QueueStage::RuntimePreparation)
    }

    /// Attributes a routed request waiting for the backend stream to begin.
    pub fn backend_dispatch(targets: &RouteTargetSet) -> Self {
        Self::new(targets, QueueStage::BackendDispatch)
    }

    fn new(targets: &RouteTargetSet, stage: QueueStage) -> Self {
        let targets = targets
            .targets()
            .iter()
            .map(QueuedTarget::from)
            .collect::<Vec<_>>();
        let mut values = queued_lock();
        for target in &targets {
            let counts = values.entry(target.clone()).or_default();
            match stage {
                QueueStage::RuntimePreparation => counts.runtime_preparation += 1,
                QueueStage::BackendDispatch => counts.backend_dispatch += 1,
            }
        }
        drop(values);
        Self { targets, stage }
    }
}
impl Drop for QueueGuard {
    fn drop(&mut self) {
        let mut values = queued_lock();
        for target in &self.targets {
            let counts = values.entry(target.clone()).or_default();
            let value = match self.stage {
                QueueStage::RuntimePreparation => &mut counts.runtime_preparation,
                QueueStage::BackendDispatch => &mut counts.backend_dispatch,
            };
            *value = value.saturating_sub(1);
        }
    }
}

/// Snapshots frontend-owned admission queue counts for autoscaling consumers.
///
/// The telemetry endpoint serializes the returned value; it is a derived report and does not retain a lock or request ownership.
pub fn autoscaling_telemetry() -> AutoscalingTelemetry {
    let targets = queued_lock()
        .iter()
        .map(|(target, counts)| AutoscalingTargetTelemetry {
            target: target.clone(),
            runtime_queued_requests: counts.runtime_preparation,
            dispatch_queued_requests: counts.backend_dispatch,
        })
        .collect();
    let collected_at_unix_ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
        .try_into()
        .unwrap_or(u64::MAX);
    AutoscalingTelemetry {
        version: 2,
        collected_at_unix_ms,
        targets,
    }
}

/// Renders the frontend's OpenMetrics response without KV-index status for callers that do not expose index diagnostics.
pub async fn scrape() -> Response {
    render(None)
}

/// Renders the OpenMetrics response with a caller-provided KV-index status snapshot.
///
/// The KV-aware metrics route supplies the status values; their ownership remains with the indexer.
pub async fn scrape_with_kv_index(
    state: &str,
    reason: Option<&str>,
    sources_healthy: usize,
    sources_total: usize,
) -> Response {
    render(Some((state, reason, sources_healthy, sources_total)))
}

// Renders upstream metrics first, then appends Foretoken-owned admission and optional KV-index
// families before restoring the single OpenMetrics EOF marker.
fn render(kv_index: Option<(&str, Option<&str>, usize, usize)>) -> Response {
    match METRICS.render() {
        Ok(mut body) => {
            if let Some(without_eof) = body.strip_suffix("# EOF\n") {
                body = without_eof.to_owned();
            }
            body.push_str(&render_admission_metrics());
            body.push_str(&render_routing_metrics());
            if let Some((state, reason, sources_healthy, sources_total)) = kv_index {
                body.push_str(&format!("# TYPE foretoken_kv_index_enabled gauge\nforetoken_kv_index_enabled {}\n# TYPE foretoken_kv_index_degraded gauge\nforetoken_kv_index_degraded{{reason=\"{}\"}} {}\n# TYPE foretoken_kv_index_sources_healthy gauge\nforetoken_kv_index_sources_healthy {}\n# TYPE foretoken_kv_index_sources_total gauge\nforetoken_kv_index_sources_total {}\n", usize::from(!matches!(state, "disabled" | "unavailable")), escape_label(reason.unwrap_or("none")), usize::from(state == "degraded"), sources_healthy, sources_total));
            }
            body.push_str("# EOF\n");
            (
                [(
                    CONTENT_TYPE,
                    HeaderValue::from_static(OPENMETRICS_CONTENT_TYPE),
                )],
                body,
            )
                .into_response()
        }
        Err(_) => StatusCode::INTERNAL_SERVER_ERROR.into_response(),
    }
}

fn render_admission_metrics() -> String {
    let values = queued_lock();
    let mut body = String::from(
        "# TYPE foretoken_upstream_queued_requests gauge\n# HELP foretoken_upstream_queued_requests Requests waiting for admission to a scaling target.\n",
    );
    for (target, counts) in values.iter() {
        let value = counts
            .runtime_preparation
            .saturating_add(counts.backend_dispatch);
        body.push_str(&format!("foretoken_upstream_queued_requests{{service_uid=\"{}\",target_kind=\"{}\",target_id=\"{}\"}} {}\n", escape_label(&target.service_uid), escape_label(&target.target_kind), escape_label(&target.target_id), value));
    }
    body
}

fn render_routing_metrics() -> String {
    let metrics = routing_lock();
    let mut body = String::from(
        "# TYPE foretoken_router_scorer_evaluations_total counter\n# HELP foretoken_router_scorer_evaluations_total Configured scorer evaluations by outcome.\n",
    );
    for ((scorer, result), value) in &metrics.scorer_evaluations {
        body.push_str(&format!(
            "foretoken_router_scorer_evaluations_total{{scorer=\"{}\",result=\"{}\"}} {}\n",
            escape_label(scorer),
            result,
            value
        ));
    }
    body.push_str("# TYPE foretoken_router_scorer_unavailable_total counter\n# HELP foretoken_router_scorer_unavailable_total Scorer evaluations omitted from composition by reason.\n");
    for ((scorer, reason), value) in &metrics.scorer_unavailable {
        body.push_str(&format!(
            "foretoken_router_scorer_unavailable_total{{scorer=\"{}\",reason=\"{}\"}} {}\n",
            escape_label(scorer),
            reason,
            value
        ));
    }
    body.push_str("# TYPE foretoken_router_scorer_score summary\n# HELP foretoken_router_scorer_score Normalized applicable candidate scores produced by each configured scorer.\n");
    for (scorer, totals) in &metrics.scorer_scores {
        body.push_str(&format!(
            "foretoken_router_scorer_score_sum{{scorer=\"{}\"}} {}\nforetoken_router_scorer_score_count{{scorer=\"{}\"}} {}\n",
            escape_label(scorer),
            totals.sum,
            escape_label(scorer),
            totals.count
        ));
    }
    body.push_str("# TYPE foretoken_router_fallback_total counter\n");
    for (fallback, value) in &metrics.fallbacks {
        body.push_str(&format!(
            "foretoken_router_fallback_total{{strategy=\"{}\"}} {}\n",
            fallback, value
        ));
    }
    body.push_str("# TYPE foretoken_router_selections_total counter\n# TYPE foretoken_router_selected_score summary\n");
    for (role, totals) in &metrics.selections {
        body.push_str(&format!(
            "foretoken_router_selections_total{{role=\"{}\"}} {}\nforetoken_router_selected_score_sum{{role=\"{}\"}} {}\nforetoken_router_selected_score_count{{role=\"{}\"}} {}\n",
            role, totals.count, role, totals.sum, role, totals.count
        ));
    }
    body
}
fn escape_label(value: &str) -> String {
    value
        .replace('\\', "\\\\")
        .replace('\n', "\\n")
        .replace('"', "\\\"")
}

/// Records one non-metrics HTTP request after its handler completes.
///
/// The Axum middleware stack consumes the unchanged response while this function updates frontend-owned vLLM-compatible counters.
pub async fn track_http_metrics(request: Request, next: Next) -> Response {
    let method = request.method().as_str().to_owned();
    let handler = request
        .extensions()
        .get::<MatchedPath>()
        .map_or_else(|| "none".to_owned(), |path| path.as_str().to_owned());
    let excluded = EXCLUDED_HANDLERS.contains(&handler.as_str());
    let started_at = Instant::now();
    let response = next.run(request).await;
    if excluded {
        return response;
    }
    let elapsed = started_at.elapsed().as_secs_f64();
    let metrics = &METRICS.api_server;
    metrics
        .http_requests
        .get_or_create(&HttpRequestLabels {
            method: method.clone(),
            status: status_group(response.status().as_u16()),
            handler: handler.clone(),
        })
        .inc();
    metrics
        .http_request_duration_seconds
        .get_or_create(&HttpHandlerLabels { method, handler })
        .observe(elapsed);
    metrics.http_request_duration_highr_seconds.observe(elapsed);
    response
}
fn status_group(status: u16) -> &'static str {
    match status / 100 {
        1 => "1xx",
        2 => "2xx",
        3 => "3xx",
        4 => "4xx",
        5 => "5xx",
        _ => "unknown",
    }
}
