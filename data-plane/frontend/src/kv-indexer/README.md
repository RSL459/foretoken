<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# KV prefix index

The KV prefix index records which KV cache blocks are available on each model server. The Router uses it to determine how many prompt tokens a specific ModelGroup and DP rank can reuse instead of computing them again.

This component reports KV cache availability. It does not select a route.

## How it works

1. Model servers report KV block store, remove, and clear events.
2. The index keeps blocks from each event source, ModelGroup, and DP rank separate, so data from different model instances cannot be mixed.
3. The Router queries a specific route and DP rank with the request's prompt tokens.
4. The index returns only storage placements that the route can read.

A query returns one of the following results:

- `Matches`: the query completed and includes the matched prompt-token count and storage placements.
- `Unavailable`: the index cannot answer the query, for example because the request has no token IDs or the event source has not finished synchronizing. This does not mean a confirmed KV cache miss.

## KV block events

- `BlockStored` records a newly stored block and its relationship to the previous block.
- `BlockRemoved` removes the referenced block. If the index cannot identify it, it does not guess or remove another record.
- `AllBlocksCleared` removes all records for the corresponding event source and DP rank.

Events from each source have a continuous sequence starting at zero. If events are missing or reordered, or the epoch changes, the index does not expose incomplete data to the Router. Queries become available again after synchronization recovers.

## Storage placements

Foretoken maps vLLM storage types to four placements:

- `GPU` and `DEVICE` → `Device`
- `CPU` and `CPU_PINNED` → `HostPinned`
- `STORAGE`, `DISK`, and `NVME` → `Disk`
- `REMOTE`, `EXTERNAL`, `NETWORK`, and `SHARED` → `External`

`Device` is directly readable by the current device. `HostPinned`, `Disk`, and `External` require the corresponding restore or transfer capability; otherwise, the index does not return them as reusable placements.

## vLLM event conversion

The model-server adapter converts vLLM KV events, block identifiers, and parent relationships into Foretoken's common format. Remove events carry only vLLM block hashes, so the adapter retains the mapping needed to find blocks reported by earlier store events. Foretoken does not directly compare raw vLLM hashes with request-side block identifiers.
