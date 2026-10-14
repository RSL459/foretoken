<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Diagnose hidden queueing through arrival-relative latency measurement

English | [简体中文](diagnose-hidden-queueing-through-arrival-relative-latency-measurement_zh.md) · [Measurement and simulation](README.md) · [Knowledge](../README.md)

## Equal mean lengths do not imply equal work

A workload with 90 short requests and 10 long requests is not equivalent to 100 requests of the mean length. Long prefill can interrupt decode, long outputs retain KV state, and a burst of long requests can create a persistent backlog. Correlation also matters: prompt length, output length, arrival time, shared prefixes, and session history jointly determine batching and cache reuse.

A timestamp-and-token-count trace preserves some of these properties, not all. Azure's 2024 inference dataset contains timestamps, context lengths, and generated lengths but no prompt text. Matching those lengths with synthetic text does not reconstruct real prefix sharing, tokenizer cost, tool use, or stopping behavior. Content datasets answer a different question. Combining independently sampled content and arrivals is useful, but it creates a constructed workload rather than reproducing a recorded service.

## Closed-loop and open-loop answer different questions

In a closed-loop workload, each client starts its next request after completion, possibly after think time Z. With C continuously active clients and mean response time R, throughput is approximately C/(R + Z). Slower service therefore automatically lowers offered load. This is appropriate for a fixed population of interactive users but can conceal overload experienced by arrivals independent of completion.

An open-loop workload schedules arrivals externally at rate λ. With an illustrative constant capacity μ, backlog grows approximately at λ − μ when λ exceeds μ. A concurrency cap, connection pool, or overloaded load generator can place the queue before the service instead of removing it. Reporting only actual-send-to-response latency omits that waiting.

Let scheduled arrival be tₐ, actual send tₛ, and completion t𝒻. Then arrival-relative latency is t𝒻 − tₐ = (tₛ − tₐ) + (t𝒻 − tₛ). A benchmark that slows issuance and forgets tₐ can make a struggling service look healthy: coordinated omission. Retaining scheduled times exposes that omission; it does not make the generator capable of sustaining the intended rate.

Foretoken's scheduler preserves planned arrival offsets when a concurrency limit delays admission. The HTTP runner records `send_delay`, and trace runs expose `replay_delay` and arrival-relative TTFT/latency. The trace run record currently marks `open_loop=False`, so the word “trace” is not proof of uncapped dispatch. Ordinary latency summaries still use the request clock; inspect the additional arrival-relative fields rather than assuming every SLO includes replay delay. AIPerf likewise distinguishes request latency from credit-issued-to-completion effective latency, including client-side queueing.

## Queueing amplifies small service-time changes

The illustrative M/M/1 response time is 1/(μ − λ), assuming Poisson arrivals, exponential independent service times, one server, and a stationary stable queue. It is not an inference-engine predictor: continuous batching, KV limits, and prefill/decode interference violate its assumptions. Its useful lesson is sensitivity. With μ = 100 requests/s and λ = 90, the model gives 100 ms; reducing capacity to 95 gives 200 ms, despite only a 5% capacity change.

Bursts and service-time variability can produce long waits even below average capacity. A Poisson workload is not a substitute for a trace whose arrivals correlate with request length. Shuffling lengths while preserving timestamps destroys that correlation. Likewise, smoothing timestamps changes the queueing question rather than merely making the benchmark easier to repeat.

## Experiments that reveal the missing queue

Use three views of the same request population: fixed concurrency, uncapped externally scheduled arrivals where the generator can sustain them, and capped replay retaining scheduled times. Compare offered, sent, completed, and failed counts, send delay, arrival-relative latency, and server waiting. If request-clock latency stays flat while send delay rises, load is accumulating upstream. If both rise, the client cap and service queue are contributing.

Then preserve length pairs and compare original ordering with a deliberately shuffled control. A change concentrated in burst recovery or cache hit rates reveals sensitivity to correlation, not just average length. Treat synthetic prefix sharing as a separate intervention. Hold actual output length and stop behavior constant when comparing scheduling; changing the output distribution changes the service demand itself.

Little's relation L = λW is a useful consistency check for a stable population with matching boundaries: mean in-flight work equals arrival rate times mean time in that system. Do not mix sent-request concurrency with arrival-relative waiting or successful-only throughput with all-attempt latency. Separate the admission interval from drain time; finite windows can hide unfinished work if only completed requests are retained.

## References

- [Azure inference dataset description](https://github.com/Azure/AzurePublicDataset/blob/master/AzureLLMInferenceDataset2024.md): 2024 code/conversation trace schema, privacy omission, and collection dates.
- [AIPerf effective versus active metrics](https://github.com/ai-dynamo/aiperf/blob/e1daadd10faa395100384358131d784d6858c5ae/docs/reference/effective-vs-active-metrics.md): revision dated 2026-10-12; credit queueing, effective latency, and success-only versus adjusted metrics.
- [Foretoken scheduling](../../../../benchmarks/src/benchmarks/runs/scheduling.py), [HTTP run ownership](../../../../benchmarks/src/benchmarks/runs/http.py), and [metrics](../../../../benchmarks/docs/metrics.md): at `e6ae3df6`; planned arrivals, admission limits, draining, and trace-relative timing.
