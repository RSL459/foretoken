// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Bounded cumulative route-target snapshots and arbitrary-window statistics.

use std::collections::VecDeque;
use std::time::{Duration, Instant};

use foretoken_model_protocol::{CumulativeHistogram, DataParallelRankTelemetry, TelemetryResponse};
use foretoken_router::{RouteTargetLatencyStats, RouteTargetRankStats, RouteTargetStats};

pub(crate) struct RouteTargetStatsHistory {
    retention: Duration,
    snapshots: VecDeque<TelemetryResponse>,
    last_received_at: Option<Instant>,
}

impl RouteTargetStatsHistory {
    /// Creates empty telemetry history retained for at most `retention`.
    ///
    /// `BackendRegistry` owns the history for one physical route target and appends successful probes.
    pub(crate) fn new(retention: Duration) -> Self {
        Self {
            retention,
            snapshots: VecDeque::new(),
            last_received_at: None,
        }
    }

    /// Records one cumulative telemetry snapshot and evicts expired or reset history.
    ///
    /// Backend readiness refresh supplies the snapshot, which is stored in this bounded history.
    pub(crate) fn push(&mut self, snapshot: TelemetryResponse) {
        if self.snapshots.back().is_some_and(|previous| {
            snapshot.collected_at_unix_ms <= previous.collected_at_unix_ms
                || counters_reset(previous, &snapshot)
        }) {
            self.snapshots.clear();
        }
        let newest = snapshot.collected_at_unix_ms;
        self.snapshots.push_back(snapshot);
        self.last_received_at = Some(Instant::now());
        let retention_ms = u64::try_from(self.retention.as_millis()).unwrap_or(u64::MAX);
        while self
            .snapshots
            .front()
            .is_some_and(|oldest| newest.saturating_sub(oldest.collected_at_unix_ms) > retention_ms)
        {
            self.snapshots.pop_front();
        }
    }

    /// Returns current gauges immediately and derives counter statistics when history covers the
    /// requested observation window.
    ///
    /// The registry exposes the returned snapshot to Router scorers; history ownership remains local.
    pub(crate) fn stats(
        &self,
        window: Duration,
        maximum_age: Duration,
    ) -> Option<RouteTargetStats> {
        if self.last_received_at?.elapsed() > maximum_age {
            return None;
        }
        let current = self.snapshots.back()?;
        let baseline = u64::try_from(window.as_millis())
            .ok()
            .and_then(|window_ms| current.collected_at_unix_ms.checked_sub(window_ms))
            .and_then(|target| {
                self.snapshots
                    .iter()
                    .rev()
                    .find(|snapshot| snapshot.collected_at_unix_ms <= target)
            });
        let observed_ms = baseline
            .and_then(|baseline| {
                current
                    .collected_at_unix_ms
                    .checked_sub(baseline.collected_at_unix_ms)
            })
            .filter(|observed_ms| *observed_ms > 0);
        let observed_seconds = observed_ms.map(|observed_ms| observed_ms as f64 / 1_000.0);

        Some(RouteTargetStats {
            collected_at_unix_ms: current.collected_at_unix_ms,
            observed_window: Duration::from_millis(observed_ms.unwrap_or(0)),
            running_requests: current.running_requests,
            max_running_requests: current.max_running_requests,
            scheduler_running_requests: current.scheduler_running_requests,
            scheduler_waiting_requests: current.scheduler_waiting_requests,
            loaded_lora_adapters: vec![],
            kv_cache_usage: current.kv_cache_usage,
            by_data_parallel_rank: current
                .by_data_parallel_rank
                .iter()
                .map(|(rank, current)| {
                    let baseline =
                        baseline.and_then(|snapshot| snapshot.by_data_parallel_rank.get(rank));
                    (*rank, rank_stats(current, baseline, observed_seconds))
                })
                .collect(),
        })
    }
}

// Keeps every rate and latency tied to the same rank-local cumulative producer epoch.
fn rank_stats(
    current: &DataParallelRankTelemetry,
    baseline: Option<&DataParallelRankTelemetry>,
    observed_seconds: Option<f64>,
) -> RouteTargetRankStats {
    RouteTargetRankStats {
        running_requests: current.running_requests,
        max_running_requests: current.max_running_requests,
        scheduler_running_requests: current.scheduler_running_requests,
        scheduler_waiting_requests: current.scheduler_waiting_requests,
        active_prefill_tokens: current.active_prefill_tokens,
        inflight_tokens: current.inflight_tokens,
        kv_cache_usage: current.kv_cache_usage,
        prompt_tokens_per_second: baseline
            .zip(observed_seconds)
            .and_then(|(baseline, seconds)| {
                rate(
                    baseline.prompt_tokens_total,
                    current.prompt_tokens_total,
                    seconds,
                )
            }),
        generation_tokens_per_second: baseline.zip(observed_seconds).and_then(
            |(baseline, seconds)| {
                rate(
                    baseline.generation_tokens_total,
                    current.generation_tokens_total,
                    seconds,
                )
            },
        ),
        ttft: baseline.and_then(|baseline| latency(&baseline.ttft_seconds, &current.ttft_seconds)),
        tpot: baseline.and_then(|baseline| latency(&baseline.tpot_seconds, &current.tpot_seconds)),
        e2e_latency: baseline
            .and_then(|baseline| latency(&baseline.e2e_seconds, &current.e2e_seconds)),
    }
}

fn rate(previous: Option<u64>, current: Option<u64>, seconds: f64) -> Option<f64> {
    Some(current?.checked_sub(previous?)? as f64 / seconds)
}

// Derives one window-local mean and bucket p95 from cumulative telemetry, rejecting resets or
// incompatible bucket layouts rather than combining observations from different histogram epochs.
fn latency(
    previous: &CumulativeHistogram,
    current: &CumulativeHistogram,
) -> Option<RouteTargetLatencyStats> {
    let samples = current.count.checked_sub(previous.count)?;
    if samples == 0 || current.buckets.len() != previous.buckets.len() {
        return None;
    }
    let sum_seconds = current.sum_seconds - previous.sum_seconds;
    if !sum_seconds.is_finite() || sum_seconds < 0.0 {
        return None;
    }
    let rank = samples.saturating_mul(95).div_ceil(100);
    let mut p95_ms = None;
    for (previous_bucket, current_bucket) in previous.buckets.iter().zip(&current.buckets) {
        if previous_bucket.le_seconds != current_bucket.le_seconds {
            return None;
        }
        if current_bucket.count.checked_sub(previous_bucket.count)? >= rank {
            p95_ms = Some(current_bucket.le_seconds * 1_000.0);
            break;
        }
    }
    Some(RouteTargetLatencyStats {
        samples,
        average_ms: sum_seconds * 1_000.0 / samples as f64,
        p95_ms,
    })
}

fn counters_reset(previous: &TelemetryResponse, current: &TelemetryResponse) -> bool {
    option_decreased(previous.prompt_tokens_total, current.prompt_tokens_total)
        || option_decreased(
            previous.generation_tokens_total,
            current.generation_tokens_total,
        )
        || histogram_reset(&previous.ttft_seconds, &current.ttft_seconds)
        || histogram_reset(&previous.tpot_seconds, &current.tpot_seconds)
        || histogram_reset(&previous.e2e_seconds, &current.e2e_seconds)
        || previous
            .by_data_parallel_rank
            .keys()
            .ne(current.by_data_parallel_rank.keys())
        || previous
            .by_data_parallel_rank
            .iter()
            .any(|(rank, previous)| {
                current
                    .by_data_parallel_rank
                    .get(rank)
                    .is_none_or(|current| rank_counters_reset(previous, current))
            })
}

fn rank_counters_reset(
    previous: &DataParallelRankTelemetry,
    current: &DataParallelRankTelemetry,
) -> bool {
    option_decreased(previous.prompt_tokens_total, current.prompt_tokens_total)
        || option_decreased(
            previous.generation_tokens_total,
            current.generation_tokens_total,
        )
        || histogram_reset(&previous.ttft_seconds, &current.ttft_seconds)
        || histogram_reset(&previous.tpot_seconds, &current.tpot_seconds)
        || histogram_reset(&previous.e2e_seconds, &current.e2e_seconds)
}

fn histogram_reset(previous: &CumulativeHistogram, current: &CumulativeHistogram) -> bool {
    current.count < previous.count
        || current.sum_seconds < previous.sum_seconds
        || current.buckets.len() != previous.buckets.len()
        || previous
            .buckets
            .iter()
            .zip(&current.buckets)
            .any(|(previous, current)| {
                current.le_seconds != previous.le_seconds || current.count < previous.count
            })
}

fn option_decreased(previous: Option<u64>, current: Option<u64>) -> bool {
    matches!((previous, current), (Some(previous), Some(current)) if current < previous)
}
