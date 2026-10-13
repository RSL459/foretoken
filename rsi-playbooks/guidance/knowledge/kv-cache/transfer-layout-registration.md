<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Transfer Layout, Registration and Connector Composition

English | [简体中文](transfer-layout-registration_zh.md)

A KV transfer can be limited by descriptor construction, layout conversion or completion handling long before saturating the NIC. Compatible byte counts also do not guarantee compatible cache contents: both endpoints must interpret layers, blocks, heads, scales and positions consistently.

## Follow one transfer

First identify physical source and destination ranges, register their memory, publish the endpoint metadata, and build descriptors for the required blocks. Submit a batch, poll or await completion, then make destination data visible to the consumer. Source and destination allocations must outlive the operation; request completion and transfer submission are not interchangeable lifetime boundaries.

Mooncake's inspected [Transfer Engine interface](https://github.com/kvcache-ai/Mooncake/blob/342c8aeece6b4eefb76c6b8b31ccfac8dde07aa3/mooncake-transfer-engine/include/transfer_engine.h) provides local registration, batched registration, segment opening, batch allocation/submission and task/batch status queries. Reusing registered regions can avoid repeated setup, but requires explicit lifetime ownership. A batch ID is an operation handle, not permission to reuse buffers immediately after submission.

An illustrative latency model is `T = T_register + n T_descriptor + T_submit + D/B + T_completion + T_relayout`. Sixty-four layers of separately addressed tiny ranges can require many descriptors even for modest payload D. Coalescing contiguous ranges or using a cross-layer physical layout can reduce n; gathering into a staging tensor adds copy work and memory. The best result depends on message size, locality and whether the attention backend accepts that layout.

## Current compatibility is more specific than matching TP

At the [2026-10-14 snapshot](README.md#evidence-snapshot), vLLM's [NIXL compatibility matrix](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/features/nixl_connector_compatibility.md) requires matching architecture, cache dtype, attention geometry/backend and transfer mode. It already supports some heterogeneous tensor-parallel and block-size combinations. Mamba requires equal TP; heterogeneous block sizes are restricted to non-hybrid models with the producer's blocks smaller than the consumer's. MLA's replicated KV is not ordinary head sharding.

The documented `LBHNC` and `LBNHC` layouts have different head-splitting behavior, and cross-layer blocks require `BLHNC`. Layout permutation has its own restrictions. Quantized transfers require compatible scale representations; support for static or packed scales does not establish support for runtime dynamic scales. Read this matrix with the [worker source](https://github.com/vllm-project/vllm/tree/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/distributed/kv_transfer/kv_connector/v1/nixl), not an older assertion that all endpoints must have identical TP.

## Composition is not automatic load balancing

vLLM's [MultiConnector implementation](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/distributed/kv_transfer/kv_connector/v1/multi_connector.py) chooses the first connector reporting matched tokens as the load source, saves through all connectors, and aggregates asynchronous completion. It does not union partial hits or select the fastest source dynamically. Any connector returning a pending lookup makes the composite lookup pending, even if another has reported a hit. Ordering changes which source serves a hit; adding a storage connector can add save traffic even when it never wins loads.

LMCache's [MP retrieval](https://github.com/LMCache/LMCache/blob/4d69cdc43ac9bab9c0c1cd5cac380c480cb32224/docs/design/v1/multiprocess/modules/blend.md) handles token scatter and stream-ordered lock release. Dynamo's [physical transfer layer](https://github.com/ai-dynamo/dynamo/tree/7708f041a965e35374af976ab8ad610b9537e3bc/lib/kvbm-physical/src/transfer) owns executor and notification abstractions. These are existing integration boundaries, not interchangeable connector contracts.

## Local experiments and service validation

Hold payload bytes fixed while varying descriptor count, contiguous versus scattered ranges, first-time versus reused registration, and message size. Record CPU construction time, registration time, transfer readiness, bytes, staging copies and device wait. If coalescing helps only small messages, fixed overhead is implicated; if time follows bytes for large messages, bandwidth dominates.

Next exercise supported layout/TP/block combinations with real KV and compare outputs to local full prefill. Include quantized scales, partial final blocks, cancellation and a delayed asynchronous save. Reverse MultiConnector order and instrument the actual winning source. Compare all-save traffic and completion latency, not only load speed.

The remaining opportunity is reducing exposed descriptor/packing overhead and measuring composition behavior in the target workload.

[KV cache](README.md)
