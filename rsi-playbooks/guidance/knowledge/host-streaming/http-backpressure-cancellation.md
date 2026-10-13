<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# HTTP backpressure and cancellation in token streams

English | [简体中文](http-backpressure-cancellation_zh.md) · [Host and streaming](README.md) · [Knowledge](../README.md)

## Regular generation can become bursty delivery

A stream crosses several queues: engine output, decoded events, application response, proxy buffers, transport windows, and client parsing. A successful write or enqueue means a local layer accepted data, not that the user received it. Therefore regular token production with bursty client events is compatible with either buffering or a slow consumer; it does not by itself establish an inference bottleneck.

SSE is a text framing protocol, not a one-token-per-packet guarantee. UTF-8 lines accumulate an event that is dispatched at a blank line. A network read may contain part of an event or many events. Comments can keep a connection alive without producing application data. TCP packet boundaries, HTTP chunks, SSE events, and generated tokens are distinct units.

## Where backpressure actually reaches the producer

For a queue holding B bytes, producer rate p and consumer rate c, dB/dt = p − c while both run. If p > c, an unbounded queue hides the mismatch until memory grows or the process fails. A bounded queue instead eventually suspends or rejects the producer. With initial occupancy B₀ and capacity K, saturation occurs after approximately (K − B₀)/(p − c) under constant rates. These are local rates: another downstream queue can absorb data and postpone feedback.

Envoy's documented flow control uses buffer limits and read suppression to propagate pressure. HTTP/2 introduces both stream and connection-level constraints; one paused stream and many streams sharing a constrained connection are not equivalent. Streaming filters can pass large responses incrementally, whereas a filter that requires the entire body must buffer it. Increasing a buffer may smooth bursts but delays pressure and consumes more memory; it is not a cure for sustained rate mismatch.

Application architecture determines the last reachable boundary. If a response body polls a lazy generation stream, pausing downstream reads may stop upstream polling. If an independent task continues receiving engine outputs into an unbounded channel, socket backpressure will not stop generation. A bounded channel can limit host memory while still leaving engine work active. Device scheduling should not be held behind every slow socket indefinitely: resource policy and transport flow control have different responsibilities.

## Disconnect is not completed cancellation

Dropping an HTTP connection, stopping application iteration, requesting engine abort, and releasing KV blocks are separate events. The service needs request identity and ownership across those transitions. An abort acknowledgement can mean the control message was accepted rather than that in-flight device work has stopped. Already submitted kernels or another pipeline step may finish before the scheduler observes cancellation.

If a cancelled request keeps outputting r tokens per second for delay Δ, wasted work is roughly rΔ tokens, with occupied KV memory persisting until cleanup. Under frequent disconnects, this can reduce goodput for healthy requests even when average successful-request latency looks unchanged. Measuring only the client's timeout misses this interval.

Foretoken already has cancellable output-stream ownership, an explicit model-server abort exchange, and idle-timeout cleanup. Its SSE heartbeats preserve transport liveness without resetting backend idle or request deadlines. These are existing service mechanisms, not proposed new optimizations. The remaining research question is whether a particular deployment propagates pressure and cancellation promptly across all queues and engine ranks.

## Discriminating experiments

Compare a continuously reading client with one that pauses reads after the same application event. Hold prompt and output budget constant. Observe queue occupancy, resident memory, engine token production, client event cadence, and other requests sharing the same process or HTTP/2 connection. Growing host memory with unchanged engine cadence points to decoupled buffering. Flat memory and paused upstream polling show pressure propagation, but do not yet prove that the engine stops generating.

Next disconnect during prefill, ordinary decode, and a blocked write. Measure client-close to abort-request, engine-terminal, and resource-release delays separately. Check surviving requests for stalls and resource recovery. A terminal marker received by the client is not sufficient evidence for a disconnect path that never receives one.

Finally compare direct and proxied streaming using identical payloads. If only proxied arrivals cluster while engine output remains regular, inspect filters, flush boundaries, and transport windows. Heartbeats address idle connections; they cannot guarantee prompt content delivery or correct backend cancellation.

## Sources and verification

Checked 2026-10-14; queue calculations are illustrative, not Foretoken measurements.

- [WHATWG SSE specification](https://html.spec.whatwg.org/multipage/server-sent-events.html): UTF-8, line parsing, blank-line dispatch, comments, and reconnection. EventSource reconnection is not automatic request replay for every LLM HTTP client.
- [Envoy flow-control documentation](https://www.envoyproxy.io/docs/envoy/latest/faq/configuration/flow_control): listener/cluster/stream limits and buffering filters; moving official documentation read on the check date.
- [Foretoken shared stream handling](../../../../data-plane/frontend/src/server/src/api/stream.rs) and [HTTP model facade](../../../../data-plane/frontend/src/llm-facade/src/http.rs): checked at `e6ae3df6`; heartbeat, idle cleanup, and accepted-abort versus final-termination ownership.
- [Foretoken metric definitions](../../../../benchmarks/docs/metrics.md): received chunk intervals and successful-request timing, which do not expose backend resource-release time.
