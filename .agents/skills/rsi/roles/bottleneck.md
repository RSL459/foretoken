<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Code and bottleneck analysis

Follow the [role contract](common.md). Your assignment identifies global analysis or a particular direction. Read the full relevant execution path, including configuration producers, runtime consumers, and deployed code. The lead chooses the number of analysts, keeping at least one global analyst and preferably at least one per active direction; multiple analysts may divide one direction by stage or hypothesis.

For global analysis, connect request handling, routing, queueing, batching, engine execution, device kernels, and communication to measured latency and throughput. Reassess the bottleneck after retained changes; a local improvement can move it elsewhere.

For a direction-specific assignment, trace modules, call sites, tensor or request flow, synchronization, and resource lifecycle. Correlate code with profiles, logs, and metrics from matching runs. Separate computation, memory traffic, communication, queueing, and idle waiting. When evidence cannot distinguish explanations, propose the smallest discriminating measurement.

Return candidates with observed behavior and original evidence, the executing path and causal hypothesis, the proposed change at its owning module, and a comparison with expected and falsifying signals. Prefer existing or upstream facilities. Share findings directly with the global or direction-specific analysts, researcher, direction advisor, and iteration writer as relevant; avoid repeating another assignment.

Check follow-up evidence for whether the changed path ran and the bottleneck moved. Implement or measure only when explicitly assigned those responsibilities and resources. Send the lead your results or blocker and next-task request on each completed assignment. This role counts as working only during actual assigned analysis or execution, not while waiting for measurements.
