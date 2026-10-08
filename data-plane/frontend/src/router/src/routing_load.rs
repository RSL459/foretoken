// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Frontend-owned routing reservations and request-specific load projections.

use crate::{RouteCandidate, RouteTargetId, RouterRequest, RoutingLoadSnapshot};
use foretoken_kv_indexer::KvPrefixIndexer;
use std::collections::{BTreeMap, BTreeSet};
use std::sync::{Arc, Mutex};

/// Shared routing reservations retained by RuntimeBuilder across serving-snapshot updates.
/// Sessions from retiring generations continue releasing their own reservations into this state.
#[derive(Clone, Default)]
pub struct RoutingLoadState(pub(crate) Arc<Mutex<RoutingReservations>>);

impl RoutingLoadState {
    /// Reads this frontend's current reservations for one target and rank without modifying them.
    pub fn snapshot(&self, target: &RouteTargetId, rank: u32) -> RoutingLoadSnapshot {
        self.0
            .lock()
            .expect("routing load lock poisoned")
            .snapshot(&(target.clone(), rank))
    }
}

pub(crate) type ReservationKey = (RouteTargetId, u32);

#[derive(Debug, Clone, PartialEq)]
pub(crate) struct ActivePrompt {
    tokens: Arc<[u32]>,
    identity: String,
    prefill_tokens: usize,
}

#[derive(Default)]
pub(crate) struct RoutingReservations {
    requests: BTreeMap<ReservationKey, BTreeMap<String, ActivePrompt>>,
}

impl RoutingReservations {
    /// Takes a coherent candidate snapshot under the routing transaction's lock.
    pub(crate) fn snapshot(&self, key: &ReservationKey) -> RoutingLoadSnapshot {
        let Some(requests) = self.requests.get(key) else {
            return RoutingLoadSnapshot::default();
        };
        RoutingLoadSnapshot {
            requests: requests.len() as i64,
            tokens: requests.values().fold(0_i64, |tokens, request| {
                tokens.wrapping_add(request.prefill_tokens as i64)
            }),
        }
    }

    /// Copies active prompts for the scorer's block projection while the routing lock is held.
    pub(crate) fn active_prompts(&self, key: &ReservationKey) -> Vec<ActivePrompt> {
        self.requests
            .get(key)
            .map(|requests| requests.values().cloned().collect())
            .unwrap_or_default()
    }

    /// Reserves a selected stage before dispatch; the owning session or stream must release it.
    pub(crate) fn reserve(
        &mut self,
        request: &RouterRequest,
        candidate: &RouteCandidate,
        prefill_tokens: usize,
    ) {
        let key = (
            candidate.route_target_id.clone(),
            candidate.data_parallel_rank,
        );
        self.requests.entry(key).or_default().insert(
            request.request_id().to_owned(),
            ActivePrompt {
                tokens: Arc::from(request.prompt_token_ids()),
                identity: cache_identity(request),
                prefill_tokens,
            },
        );
    }

    /// Releases prompt-token load when the first response reaches the frontend.
    pub(crate) fn release_prompt_load(&mut self, key: &ReservationKey, id: &str) {
        if let Some(request) = self
            .requests
            .get_mut(key)
            .and_then(|requests| requests.get_mut(id))
        {
            request.prefill_tokens = 0;
        }
    }

    /// Removes exactly one request-stage contribution on completion, rejection, or cancellation.
    pub(crate) fn release(&mut self, key: &ReservationKey, id: &str) {
        if let Some(requests) = self.requests.get_mut(key) {
            requests.remove(id);
            if requests.is_empty() {
                self.requests.remove(key);
            }
        }
    }
}

/// Projects complete prompt blocks after admission, deduplicating only when reuse is assumed.
/// Ordinary disaggregated Decode accounts for each request's prompt independently.
pub(crate) fn potential_decode_blocks(
    prompts: &[ActivePrompt],
    request: &RouterRequest,
    block_size: usize,
    assume_kv_reuse: bool,
) -> usize {
    if !assume_kv_reuse {
        return prompts
            .iter()
            .map(|prompt| prompt.tokens.len() / block_size)
            .sum::<usize>()
            + request.token_count() / block_size;
    }
    let mut blocks = BTreeSet::new();
    for prompt in prompts {
        add_prompt_blocks(&mut blocks, &prompt.tokens, &prompt.identity, block_size);
    }
    add_prompt_blocks(
        &mut blocks,
        request.prompt_token_ids(),
        &cache_identity(request),
        block_size,
    );
    blocks.len()
}

/// Adds complete prefix identities to the projection; partial tails consume prefill work only.
fn add_prompt_blocks(
    blocks: &mut BTreeSet<[u8; 32]>,
    tokens: &[u32],
    identity: &str,
    block_size: usize,
) {
    let mut hash = blake3::Hasher::new();
    hash.update(&(identity.len() as u64).to_le_bytes());
    hash.update(identity.as_bytes());
    for block in tokens.chunks_exact(block_size) {
        for token in block {
            hash.update(&token.to_le_bytes());
        }
        blocks.insert(*hash.finalize().as_bytes());
    }
}

/// Separates active prefixes by model and cache identity, treating an empty salt as absent.
fn cache_identity(request: &RouterRequest) -> String {
    let Some(generate_request) = &request.generate_request else {
        return request.request_id().to_owned();
    };
    serde_json::to_string(&(
        &request.model,
        generate_request
            .cache_salt
            .as_deref()
            .filter(|salt| !salt.is_empty()),
        generate_request
            .lora_request
            .as_ref()
            .map(|lora| lora.lora_int_id),
        generate_request
            .mm_features
            .as_ref()
            .map(|_| generate_request.request_id.as_str()),
    ))
    .expect("cache identity contains only strings")
}

/// Returns uncached indexed tokens and the partial prompt tail for routing load accounting.
pub(crate) fn uncached_tokens(
    request: &RouterRequest,
    candidate: &RouteCandidate,
    kv: &dyn KvPrefixIndexer,
) -> usize {
    let Some(info) = crate::cache::cache_match(request, candidate, kv) else {
        return request.token_count();
    };
    let indexed = info.total_blocks * info.block_size;
    indexed.saturating_sub(info.matched_blocks * info.block_size)
        + request.token_count().saturating_sub(indexed)
}
