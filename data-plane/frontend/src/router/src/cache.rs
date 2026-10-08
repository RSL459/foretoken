// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Complete-block prefix observations for request-specific routing costs.

use crate::{RouteCandidate, RouterRequest};
use foretoken_kv_indexer::{KvPrefixIndexer, KvPrefixQueryResult};
use foretoken_model_protocol::{KvCacheLocality, KvStorageTier, ModelServerRole};

pub(crate) struct CacheMatch {
    pub(crate) matched_blocks: usize,
    pub(crate) total_blocks: usize,
    pub(crate) block_size: usize,
    pub(crate) device_blocks: usize,
    pub(crate) host_blocks: usize,
    pub(crate) disk_blocks: usize,
    pub(crate) shared_blocks: usize,
}

/// Reads complete-block counts from the exact route binding, preserving block units.
pub(crate) fn cache_match(
    request: &RouterRequest,
    candidate: &RouteCandidate,
    kv: &dyn KvPrefixIndexer,
) -> Option<CacheMatch> {
    if candidate.role == ModelServerRole::Encoder {
        return None;
    }
    let lookup = request
        .kv_prefix_lookup(
            candidate.route_target_id.as_str(),
            candidate.data_parallel_rank,
        )
        .ok()?;
    let KvPrefixQueryResult::Matches(matches) = kv.prefix_matches(lookup) else {
        return None;
    };
    let block_size = matches.block_size()? as usize;
    let mut info = CacheMatch {
        matched_blocks: 0,
        total_blocks: request.token_count() / block_size,
        block_size,
        device_blocks: 0,
        host_blocks: 0,
        disk_blocks: 0,
        shared_blocks: 0,
    };
    for matched in matches {
        if matched.placement.locality == KvCacheLocality::Unspecified {
            continue;
        }
        let count = (matched.matched_tokens / block_size).min(info.total_blocks);
        info.matched_blocks = info.matched_blocks.max(count);
        match matched.placement.tier {
            KvStorageTier::Device => info.device_blocks = info.device_blocks.max(count),
            KvStorageTier::HostPinned => info.host_blocks = info.host_blocks.max(count),
            KvStorageTier::Disk => info.disk_blocks = info.disk_blocks.max(count),
            KvStorageTier::External => info.shared_blocks = info.shared_blocks.max(count),
        }
    }
    Some(info)
}
