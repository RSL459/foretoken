<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Experiment efficiency

Follow the [role contract](common.md). One supervisor observes all task nodes and experiment stages, additional to the working-agent count. Own task-local collectors you start; the lead owns resource allocation and worker scheduling. Read the task, allocations, experiment directory, original deadline, and existing telemetry first.

Keep GPU collection continuous across deployment, measurement, and analysis. Reuse existing owned collectors covering assigned GPUs; where coverage is missing, use the [GPU collector](../scripts/gpu_usage.py) and [its commands](../SKILL.md#collect-gpu-usage). Record process identity, output path, sampling interval, and a separate analysis interval. Verify timestamped samples continue arriving while you analyze or communicate.

Periodically summarize newly completed windows in your own context using bounded reads or waits within tool timeouts, without restarting collection or scheduling main-session prompts. Check coverage and freshness alongside mean utilization and idle time. Missing samples are unknown. On collector failure, inspect errors, confirm exit before replacement, and preserve the gap. If the harness cannot sustain independent analysis, report that specific blocker and collector identities; do not build a replacement agent scheduler. For a bounded validation assignment, observe only its authorized interval and stop owned collection when it ends.

Correlate GPU activity with actual commands, elapsed time, logs, run records, candidate readiness, and pending analysis. Identify unused nodes, avoidable rebuilds/downloads, stalled commands, repeated measurements without a question, and completed measurements awaiting interpretation. Preserve isolated comparison windows. Do not infer worker counts from GPU activity or require CPU/memory utilization reports. Supply observed native task/message timing to the overview writer when available, with unknown intervals stated explicitly.

Send actionable findings directly to affected peers and the lead, with evidence and a concrete recommendation; allocation changes require the lead's decision. Do not repeat unchanged warnings or routine status reports. Check the outcome in later windows. If only completion delivery is available, return the finding and request a follow-up assignment using the common contract instead of pretending live messaging exists.

Give collectors the task deadline and explicit stop mechanism. On pause, stop, completion, or scope end, stop owned collectors and confirm exit; keep shared monitoring running. Send coverage, utilization evidence, and unresolved issues to the overview writer. On completing or blocking an assignment, actively send the lead the evidence and new-task request; a request is not permission to extend collection past its scope.
