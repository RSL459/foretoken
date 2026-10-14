<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Reduce device idle gaps through host/device execution overlap

English | [简体中文](reduce-device-idle-gaps-through-host-device-execution-overlap_zh.md) · [Host and streaming](README.md) · [Knowledge](../README.md)

## Why fast kernels can leave the device waiting

A decode step can contain little device work but substantial host work: choose requests, allocate metadata, construct inputs, submit kernels, consume results, and prepare the next step. A faster kernel exposes these costs rather than eliminating them. Likewise, an `async` HTTP handler can execute synchronous tokenization or parsing before its next suspension point. Other connections then wait on that event-loop thread even when spare CPU cores exist.

Three different dependencies matter. Python bytecode threads ordinarily contend for the GIL. An asyncio event loop cooperatively runs tasks, so synchronous work blocks that loop whether or not the underlying extension releases the GIL. Finally, the device may need a host decision that depends on a just-produced token. Moving work to another thread changes only the first two boundaries; it does not remove the data dependency.

## Overlap is a dependency transformation

Let host preparation take H milliseconds and device execution take D. A fully serialized steady-state loop has interval H + D. If preparation of the next step can run during the current device step, the ideal interval approaches max(H, D), plus uncovered synchronization and result-processing costs. These are pipeline intervals, not the latency of a newly admitted request. Pipeline fill, queueing, and result delivery still contribute to that latency.

For illustration, H = 2 ms and D = 3 ms gives a 5 ms serialized interval and a 3 ms ideal overlapped interval. If metadata needs the current output, a device-side relay, deferred reconciliation, or a different scheduling decision is necessary before that bound is reachable. A thread pool alone cannot produce it.

At the cited vLLM revision, `AsyncScheduler` accounts for output placeholders while steps are in flight and reconciles them with returned outputs, including stale delivery after preemption. SGLang's overlap utilities publish request-indexed device state, record events, and resolve future inputs after the appropriate fence. Host copies are conditional on consumers needing CPU metadata. Event ordering and tensor lifetime belong to this implementation boundary; removing a wait without preserving them can feed the next batch stale state.

## Moving CPU work without creating another queue

Offloading a blocking operation can restore HTTP responsiveness while leaving total CPU demand unchanged. It can also add executor wait, serialization, and wakeup costs. Native tokenizers that release the GIL can benefit from threads; Python-heavy parsing may primarily gain event-loop isolation rather than parallel throughput. Process separation permits independent Python execution but adds IPC and state ownership.

Free-threaded CPython is not a drop-in inference optimization. The Python 3.14 documentation distinguishes build support from the runtime GIL state: incompatible extensions can re-enable the GIL. Removing the GIL also does not make an event loop preempt synchronous callbacks or remove native library locks. Compatibility and single-thread overhead must be assessed for the actual engine environment.

The cited vLLM renderer has executor wrappers for non-streaming derender work, plain streaming detokenization, and parsed streaming. Remaining questions include executor saturation, parser replay cost, and competition between tokenization and stream rendering.

## Experiments that distinguish the causes

Keep model, generated-token count, batch composition, and graph mode fixed. First compare device-step intervals with host submission and result-ready times. If GPU gaps coincide with scheduler execution, investigate the host/device dependency; if engine cadence is regular but HTTP chunks stall together, investigate the event loop or executor instead.

Then vary one resource: isolate host cores, change executor concurrency, or separate ingestion from output processing. Measure executor wait separately from service time and capture loop lag. A responsive loop with unchanged output throughput indicates isolation, not reduced work. Extra threads that increase runnable time without reducing gaps indicate contention or the GIL. Evaluate ordinary unprofiled runs afterwards: a pipeline change can raise throughput while worsening first-response latency or cancellation delay.

## References

- [Python 3.14 asyncio development](https://docs.python.org/3.14/library/asyncio-dev.html) and [free-threading](https://docs.python.org/3.14/howto/free-threading-python.html): cooperative scheduling, executors, and extension compatibility.
- [vLLM AsyncScheduler](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/v1/core/sched/async_scheduler.py) and [online renderer](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/renderers/online_derenderer.py): source revision dated 2026-10-13.
- [PR #49396](https://github.com/vllm-project/vllm/pull/49396): merged 2026-07-22. [Issue #57350](https://github.com/vllm-project/vllm/issues/57350): closed, with a streaming executor path in the revision above.
- [SGLang overlap utilities](https://github.com/sgl-project/sglang/blob/e9400c5a8f3a0d0312a37aecef694f5edfd69341/python/sglang/srt/managers/overlap_utils.py): revision dated 2026-10-13; backend-specific synchronization differs.
