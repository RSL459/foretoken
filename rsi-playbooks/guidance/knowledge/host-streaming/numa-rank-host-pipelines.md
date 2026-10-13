<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# NUMA placement and multi-rank host contention

English | [简体中文](numa-rank-host-pipelines_zh.md) · [Host and streaming](README.md) · [Knowledge](../README.md)

## More accelerators also create more host work

A multi-rank replica has API ingestion, scheduler processes, device workers, communication progress, tokenizer threads, and output processing. Increasing tensor or data parallelism can lower device work per rank while increasing runnable host tasks. A machine with low aggregate CPU utilization can still starve the one core or container quota that feeds the next collective.

The current vLLM optimization documentation explicitly budgets physical CPU cores for API, engine-core, and GPU worker processes, and notes that more API servers or data-parallel engines require additional cores. This is deployment guidance, not a universal utilization threshold or a measured Foretoken resource default. Hyperthreads do not provide the same execution capacity as separate physical cores.

## Quota, affinity, and locality are different constraints

Linux cgroup `cpu.max` expresses CPU runtime quota per period. A group allowed on eight CPUs but granted 200 ms every 100 ms has approximately two cores of aggregate quota. Concurrent workers can consume that budget early, then be throttled until replenishment. A periodic device gap can therefore coexist with low host-wide utilization. Parent cgroup limits can constrain a child even when its own limit looks generous.

CPU affinity limits where threads run; it does not reserve those cores or raise the quota. Conversely, increasing quota does not eliminate contention on an oversubscribed affinity set. CPU pressure measures runnable waiting, while throttling counters indicate quota enforcement. Neither substitutes for per-process run-queue and scheduling evidence.

NUMA policy governs memory placement, usually when pages are faulted. Binding a thread after allocating buffers does not automatically relocate those pages. A worker near its GPU can still read metadata or copy from pinned buffers allocated by a different socket. Local execution, first-touch allocation, and permitted memory nodes must be considered together. Binding minimizes remote access for a localized workload; interleaving may help memory-bandwidth-heavy shared workloads but increases access distance for some consumers. The best choice depends on who actually reads the pages.

## A slow host rank can look like slow communication

Let aᵣ be rank r's arrival time at a collective. Ignoring topology details, completion cannot precede max(aᵣ) plus the collective's post-arrival transfer work. An early rank can show a long communication interval because it waits for a late rank, even if network bandwidth is healthy. The root cause may be CPU descheduling, metadata construction, a synchronous host copy, or uneven preceding device work.

For illustration, three ranks arrive at 1 ms and one at 5 ms. If transfer takes another 1 ms, early ranks spend approximately 5 ms in the collective while the late rank spends 1 ms. Optimizing transfer by 0.2 ms leaves the dominant 4 ms arrival skew intact. Communication-library algorithms and GPU execution can complicate this decomposition, but the example explains why entry times must accompany durations.

SGLang's inspected overlap utilities show another host boundary: CPU sequence-length mirrors are updated only for backends or verification paths that require them. Device-side relays can avoid a host synchronization, while a backend-specific metadata requirement restores it. CUDA and other backend paths are not interchangeable; hardware-independent conclusions need the actual adapter and consumer path.

## Experiments that isolate placement and contention

Measure the same batch shape with fixed device allocation. Inspect effective CPU sets, quota hierarchy, memory nodes, and per-rank runnable time. Change quota without affinity, then affinity without quota. If periodic gaps disappear only with more quota, the cause is not remote NUMA memory. If dedicated physical cores help under the same quota, run-queue competition or sibling-thread sharing is more plausible.

For locality, compare allocation and execution on the same node with deliberately remote allocation; preserve buffer sizes and transfer directions. Changing placement after warmup without recreating buffers does not isolate first touch. Separate pinned-buffer traffic from tokenizer or shared model metadata access.

For multi-rank diagnosis, align traces by a shared step or collective identity and compare preceding host work, GPU completion, and collective entry across every rank. Do not align independent node clocks by timestamp alone. If host placement changes remove arrival skew while transfer duration after the last arrival stays stable, the host pipeline is the promising boundary. Measure single-user latency and saturated throughput separately: reserving cores may improve cadence but reduce the number of replicas a node can host.

## Sources and verification

Checked 2026-10-14. The numerical examples are causal illustrations, not hardware measurements.

- [vLLM optimization documentation](https://docs.vllm.ai/en/latest/configuration/optimization/): physical-core guidance and busy-loop scheduler contention; moving page read on the check date.
- [Linux cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html) and [NUMA memory policy](https://docs.kernel.org/admin-guide/mm/numa_memory_policy.html): quota, effective CPU sets, pressure, allocation policy, and migration semantics; live kernel documentation.
- [SGLang overlap utilities](https://github.com/sgl-project/sglang/blob/e9400c5a8f3a0d0312a37aecef694f5edfd69341/python/sglang/srt/managers/overlap_utils.py): device/CPU metadata boundaries; revision dated 2026-10-13.
- [Nsight Systems guide](https://docs.nvidia.com/nsight-systems/UserGuide/index.html): process scope, CPU/device correlation, timestamp normalization, and distributed clock alignment; relevant sections read on the check date.
- [Foretoken CPU observations](../../../../benchmarks/docs/metrics.md#cpu-and-memory-observations): counter-derived estimates and trailing-window curves; checked at `e6ae3df6`, not per-rank scheduling traces.
