// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
// SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

//! Scoring prefill and decode load in KV blocks with cache-reuse credit.

use crate::{RouteCandidate, RouteScore, RouteScorer, RouterRequest, RoutingProgress};
use foretoken_kv_indexer::KvPrefixIndexer;
use foretoken_model_protocol::ModelServerRole;
use serde::Deserialize;

/// Disjoint worker-local cache tiers and an independent shared-cache prefix, in engine blocks.
#[derive(Default)]
struct CacheCostInput {
    device_blocks: usize,
    host_blocks: usize,
    disk_blocks: usize,
    shared_blocks: usize,
}

impl CacheCostInput {
    /// Converts indexed prefix lengths into non-overlapping worker tiers for the cost model.
    fn read(
        request: &RouterRequest,
        candidate: &RouteCandidate,
        kv: &dyn KvPrefixIndexer,
        block_size: usize,
    ) -> Self {
        let Some(cache) = crate::cache::cache_match(request, candidate, kv) else {
            return Self::default();
        };
        let device = cache.device_blocks * cache.block_size / block_size;
        let host = cache.host_blocks * cache.block_size / block_size;
        let disk = cache.disk_blocks * cache.block_size / block_size;
        Self {
            device_blocks: device,
            host_blocks: host.saturating_sub(device),
            disk_blocks: disk.saturating_sub(device.max(host)),
            shared_blocks: cache.shared_blocks * cache.block_size / block_size,
        }
    }
}

/// Scores Dynamo's reference KV cost with frontend-local, prompt-only active-block tracking.
#[derive(Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct KvCostScorer {
    overlap_score_credit: f64,
    overlap_score_credit_decay: f64,
    prefill_load_scale: f64,
    decode_active_request_weight: f64,
    host_cache_hit_weight: f64,
    disk_cache_hit_weight: f64,
    shared_cache_multiplier: f64,
    router_track_prefill_tokens: bool,
}

impl Default for KvCostScorer {
    fn default() -> Self {
        Self {
            overlap_score_credit: 1.0,
            overlap_score_credit_decay: 0.0,
            prefill_load_scale: 1.0,
            decode_active_request_weight: 0.0,
            host_cache_hit_weight: 0.75,
            disk_cache_hit_weight: 0.25,
            shared_cache_multiplier: 0.0,
            router_track_prefill_tokens: true,
        }
    }
}

impl KvCostScorer {
    /// Estimates avoided prefill work for reservation and scoring, excluding shared-cache credit.
    fn cached_tokens(&self, cache: &CacheCostInput, block_size: usize) -> usize {
        let effective_blocks = cache.device_blocks as f64
            + cache.host_blocks as f64 * self.host_cache_hit_weight
            + cache.disk_blocks as f64 * self.disk_cache_hit_weight;
        (effective_blocks * block_size as f64).round().max(0.0) as usize
    }

    fn tracks_prefill(&self, candidate: &RouteCandidate) -> bool {
        self.router_track_prefill_tokens
            && matches!(
                candidate.role,
                ModelServerRole::Aggregate | ModelServerRole::Prefill
            )
    }

    /// Computes one native block cost from the current routing snapshot and prepared cache input.
    fn worker_cost(
        &self,
        request: &RouterRequest,
        candidate: &RouteCandidate,
        cache: &CacheCostInput,
        block_size: usize,
        min_active_prefill_tokens: usize,
    ) -> f64 {
        let decode_cost = crate::routing_load::potential_decode_blocks(
            &candidate.active_prompts,
            request,
            block_size,
            candidate.role != ModelServerRole::Decode,
        ) as f64;
        let active_request_cost =
            self.decode_active_request_weight * candidate.local_load.requests.max(0) as f64;
        // Foretoken's disaggregated Decode always follows Prefill. Match Dynamo's ordinary
        // disaggregated request override (zero overlap credit), not conditional disaggregation.
        if candidate.role == ModelServerRole::Decode {
            return decode_cost + active_request_cost;
        }
        let track_prefill = self.tracks_prefill(candidate);
        let active_prefill_tokens = candidate.local_load.tokens.max(0) as usize;
        let overlap_credit_decay = if track_prefill && self.overlap_score_credit_decay > 0.0 {
            let excess_blocks = active_prefill_tokens.saturating_sub(min_active_prefill_tokens)
                as f64
                / block_size as f64;
            let request_blocks = request.token_count().div_ceil(block_size);
            let normalized_load = excess_blocks / request_blocks.max(1) as f64;
            1.0 / (1.0 + self.overlap_score_credit_decay * normalized_load)
        } else {
            1.0
        };
        let effective_credit = self.overlap_score_credit * overlap_credit_decay;
        // Shared hits cover a contiguous prefix and receive credit only beyond device hits.
        // Host and disk counts already exclude all faster worker-local tiers.
        let shared_overlap = self.shared_cache_multiplier
            * cache.shared_blocks.saturating_sub(cache.device_blocks) as f64;
        let overlap_credit = effective_credit * cache.device_blocks as f64
            + self.host_cache_hit_weight * cache.host_blocks as f64
            + self.disk_cache_hit_weight * cache.disk_blocks as f64
            + shared_overlap;
        let raw_prefill_tokens = if track_prefill {
            let cached_tokens = self.cached_tokens(cache, block_size);
            let uncached_tokens = request.token_count().saturating_sub(cached_tokens);
            (active_prefill_tokens + uncached_tokens).saturating_add(cached_tokens)
        } else {
            0
        };
        let raw_prefill_blocks = raw_prefill_tokens as f64 / block_size as f64;
        self.prefill_load_scale * (raw_prefill_blocks - overlap_credit).max(0.0)
            + decode_cost
            + active_request_cost
    }
}

impl RouteScorer for KvCostScorer {
    /// Requests live prefix observations before cache-aware scoring.
    fn needs_kv_prefix(&self) -> bool {
        true
    }

    /// Reserves effective prefill tokens until the first response; Decode has no prompt work left.
    fn prefill_token_load(
        &self,
        request: &RouterRequest,
        candidate: &RouteCandidate,
        kv_prefix_indexer: &dyn KvPrefixIndexer,
    ) -> usize {
        if !self.tracks_prefill(candidate) {
            return 0;
        }
        let Some(block_size) = candidate.kv_block_size else {
            return request.token_count();
        };
        let size = block_size.get() as usize;
        let cache = CacheCostInput::read(request, candidate, kv_prefix_indexer, size);
        request
            .token_count()
            .saturating_sub(self.cached_tokens(&cache, size))
    }

    /// Applies cost weights once at pipeline construction, rejecting invalid numeric parameters.
    fn configure(&mut self, parameters: serde_json::Value) -> Result<(), String> {
        let config: Self = serde_json::from_value(parameters).map_err(|error| error.to_string())?;
        for (name, value) in [
            ("overlap_score_credit", config.overlap_score_credit),
            (
                "overlap_score_credit_decay",
                config.overlap_score_credit_decay,
            ),
            ("prefill_load_scale", config.prefill_load_scale),
            (
                "decode_active_request_weight",
                config.decode_active_request_weight,
            ),
            ("host_cache_hit_weight", config.host_cache_hit_weight),
            ("disk_cache_hit_weight", config.disk_cache_hit_weight),
            ("shared_cache_multiplier", config.shared_cache_multiplier),
        ] {
            if !value.is_finite() || value < 0.0 {
                return Err(format!("{name} must be finite and non-negative"));
            }
        }
        for (name, value) in [
            ("host_cache_hit_weight", config.host_cache_hit_weight),
            ("disk_cache_hit_weight", config.disk_cache_hit_weight),
            ("shared_cache_multiplier", config.shared_cache_multiplier),
        ] {
            if value > 1.0 {
                return Err(format!("{name} must be between 0 and 1"));
            }
        }
        *self = config;
        Ok(())
    }

    /// Returns reference KV-block costs in candidate order, using only eligible load minima.
    fn score(
        &self,
        request: &RouterRequest,
        candidates: &[RouteCandidate],
        kv_prefix_indexer: &dyn KvPrefixIndexer,
        _routing_progress: &RoutingProgress<'_>,
        _customized_context: &mut (),
    ) -> Vec<RouteScore> {
        let minimum = if self.router_track_prefill_tokens && self.overlap_score_credit_decay > 0.0 {
            candidates
                .iter()
                .filter(|candidate| {
                    candidate.stage_eligible
                        && candidate.kv_block_size.is_some()
                        && self.tracks_prefill(candidate)
                })
                .map(|candidate| candidate.local_load.tokens.max(0) as usize)
                .min()
                .unwrap_or(0)
        } else {
            0
        };
        candidates
            .iter()
            .map(|candidate| {
                if candidate.role == ModelServerRole::Encoder {
                    return super::cost_score(None);
                }
                let Some(block_size) = candidate.kv_block_size else {
                    return super::cost_score(None);
                };
                let size = block_size.get() as usize;
                let cache = CacheCostInput::read(request, candidate, kv_prefix_indexer, size);
                super::cost_score(Some(self.worker_cost(request, candidate, &cache, size, minimum)))
            })
            .collect()
    }
}
