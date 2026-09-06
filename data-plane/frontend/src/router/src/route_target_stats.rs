// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Read-only route target statistics used by Router candidate snapshots.

use std::collections::BTreeMap;
use std::time::Duration;

use crate::RouteTargetId;

/// Latency distribution calculated over one observation window.
#[derive(Debug, Clone, PartialEq)]
pub struct RouteTargetLatencyStats {
    /// Samples observed in the window.
    pub samples: u64,
    /// Arithmetic mean in milliseconds.
    pub average_ms: f64,
    /// Bucket-derived p95, or `None` when it exceeds the largest exported boundary.
    pub p95_ms: Option<f64>,
}

/// Windowed and instantaneous observations for one exact data-parallel rank.
#[derive(Debug, Clone, PartialEq)]
pub struct RouteTargetRankStats {
    /// Requests accepted by Model Server and not yet complete on this rank.
    pub running_requests: u64,
    /// Maximum sequences this rank's EngineCore scheduler can run in one iteration.
    pub max_running_requests: u64,
    /// Requests currently running in this rank's scheduler.
    pub scheduler_running_requests: Option<u64>,
    /// Requests currently waiting in this rank's scheduler.
    pub scheduler_waiting_requests: Option<u64>,
    /// Prompt tokens that have not produced their first output token on this rank.
    pub active_prefill_tokens: u64,
    /// Prompt plus declared maximum output tokens for requests admitted on this rank.
    pub inflight_tokens: u64,
    /// Current KV-cache utilization for this rank in `0.0..=1.0`.
    pub kv_cache_usage: Option<f64>,
    /// Prompt tokens processed per second over the target observation window.
    pub prompt_tokens_per_second: Option<f64>,
    /// Generated tokens per second over the target observation window.
    pub generation_tokens_per_second: Option<f64>,
    /// Time to first token over the target observation window.
    pub ttft: Option<RouteTargetLatencyStats>,
    /// Time per output token over the target observation window.
    pub tpot: Option<RouteTargetLatencyStats>,
    /// End-to-end request latency over the target observation window.
    pub e2e_latency: Option<RouteTargetLatencyStats>,
}

/// Latest route target gauges and optional counter statistics calculated over `observed_window`.
#[derive(Debug, Clone, PartialEq)]
pub struct RouteTargetStats {
    /// Collection time of the latest cumulative snapshot.
    pub collected_at_unix_ms: u64,
    /// Actual counter interval, or zero while retained history does not yet cover the requested
    /// window. Current gauges remain usable in that state.
    pub observed_window: Duration,
    /// Requests currently admitted by Model Server.
    pub running_requests: u64,
    /// Sum of the per-rank scheduler running-sequence limits.
    pub max_running_requests: u64,
    /// Requests currently running in the vLLM scheduler.
    pub scheduler_running_requests: Option<u64>,
    /// Requests currently waiting in the vLLM scheduler.
    pub scheduler_waiting_requests: Option<u64>,
    /// Exact per-rank observations. A missing rank is unavailable, never an aggregate fallback.
    pub by_data_parallel_rank: BTreeMap<u32, RouteTargetRankStats>,
    /// LoRA adapter names currently reported as resident in GPU memory.
    pub loaded_lora_adapters: Vec<String>,
    /// Current vLLM KV-cache utilization in the range `0.0..=1.0`.
    pub kv_cache_usage: Option<f64>,
}

/// Reads locally cached route target statistics without request-path network I/O.
pub trait RouteTargetStatsReader: Send + Sync {
    /// Calculates statistics for `route_target_id` over the Router-selected `window`.
    ///
    /// Returns `None` only when current telemetry is unavailable. Windowed fields remain `None`
    /// until retained history covers the requested interval.
    fn stats(&self, route_target_id: &RouteTargetId, window: Duration) -> Option<RouteTargetStats>;
}

/// Route Target-statistics reader used when telemetry is not configured.
pub(crate) struct NoopRouteTargetStatsReader;

impl RouteTargetStatsReader for NoopRouteTargetStatsReader {
    #[allow(unused_variables)]
    fn stats(&self, route_target_id: &RouteTargetId, window: Duration) -> Option<RouteTargetStats> {
        None
    }
}
