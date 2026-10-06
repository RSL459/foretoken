<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Foretoken alert reference

English | [简体中文](alerts_zh.md)

Select rules in the owning service's `spec.observability.alerts.rules`. An empty list disables alerts without disabling metrics. Prometheus must select the workload namespace and its `PrometheusRule`; check the service's `AlertsReady` condition if rules do not appear.

## Configure admission alerts

Admission alerts belong to `FrontendService`, not individual models. For example, add this under `spec` to alert on sustained capacity rejections:

```yaml
observability:
  alerts:
    rules:
      - ForetokenAdmissionCapacityRejectionRatioHigh
    thresholds:
      admission:
        capacityRejectionRatio: 0.05
        minResultRate: 1
```

Redeploy the service configuration to apply the change. These example thresholds tolerate 5% capacity rejections when at least one admission call completes per second; choose tolerances for the service's workload. All admission alerts have warning severity and are disabled unless selected.

| Field under `thresholds.admission` | Required by | Meaning |
| --- | --- | --- |
| `capacityRejectionRatio` | Capacity rejection rule | Rejection fraction, from 0 to 1; intake and work are evaluated separately. |
| `timeoutRatio` | Timeout rule | Fraction of work admission calls ending in queue timeout or deadline expiry, from 0 to 1. |
| `admittedQueueP95Seconds` | Queue p95 rule | Maximum tolerated p95 wait, in seconds, for calls that queued and were admitted. |
| `minResultRate` | Both ratio rules | Minimum completed admission calls/s in the evaluated scope. |
| `minQueuedAdmissionRate` | Queue p95 rule | Minimum queued-and-admitted samples/s in the evaluated scope. |
| `scope` | Optional for business rules | `service` (default) or `pod`; only the selected scope produces alerts. |
| `window` | Optional for business rules | Rate calculation window, default `1m`; increase it for slower scrape intervals. |
| `for` | Optional for business rules | Continuous persistence before firing, default `5m`. |

Thresholds and minimum sample rates have no defaults; supply only those required by the selected rules. Durations use whole seconds, minutes, or hours, such as `90s` or `5m`. A longer calculation window can keep a past burst above threshold; `for` evaluates that windowed signal, not individual requests.

The telemetry rule needs no thresholds and always evaluates individual scrape targets for 5 minutes. Notifications group admission alerts by namespace, frontend, alert name, and stage, with Pod details when available. Configure a [Lark](../integrations/lark/README.md), [Slack](../integrations/slack/README.md), or [DingTalk](../integrations/dingtalk/README.md) receiver for delivery.

## Investigate an alert

Open Foretoken System Overview and select the alert's namespace and frontend. Use admission results and Pod details to distinguish frontend capacity, queue waiting, and request deadlines; then compare model queues, latency, and device utilization.

### ForetokenAdmissionCapacityRejectionRatioHigh

The capacity-rejected fraction exceeds the configured tolerance, with the minimum result rate, for the configured persistence. `intake` measures immediate HTTP residency admission; `work` measures admission before preprocessing or generation. Each stage uses its own completed-call denominator, including other result categories. Internal calls are excluded.

Inspect configured frontend capacity and uneven Pod traffic before changing limits. Capacity rejection means a frontend admission limit was reached, not that GPUs are necessarily saturated.

### ForetokenAdmissionTimeoutRatioHigh

The combined `queue_timeout` and `deadline_exceeded` fraction exceeds the configured tolerance among completed HTTP work admission calls. Compare the two result categories separately: one exhausts the queue wait limit, the other exhausts the request budget before admission finishes. Deadlines during body reading or inference are not counted here.

### ForetokenAdmissionAdmittedQueueP95High

The p95 wait exceeds the configured seconds threshold while queued-and-admitted samples meet the minimum rate. Only calls that actually queued and were admitted contribute; immediate admissions, timeouts, and cancellations do not. Inspect queue occupancy and backend capacity alongside the separate timeout results.

### ForetokenAdmissionTelemetryMissing

A target is successfully scraped but has lacked required admission metrics for 5 minutes. Check runtime versions and per-Pod coverage, particularly during upgrades. Every target must publish algorithm information and baseline HTTP intake/work counters; concurrency also requires its resource occupancy and limit gauges. Idle targets need no wait histogram samples. This alert indicates incomplete telemetry, not inference unavailability; failed scrapes use `ForetokenMetricsTargetDown` instead.

### ForetokenMetricsTargetDown

A discovered frontend or model-server `/metrics` endpoint cannot be scraped for 1 minute. Inspect Prometheus Targets, Pod health, and scraper network access. It resolves when scraping resumes or the endpoint leaves service discovery; it does not detect endpoints absent from discovery.

### ForetokenFrontendHTTPResponseStart5xxRatioHigh

More than 5% of frontend HTTP response starts are 5xx for 2 minutes, with at least 0.1 response starts/s over a 5-minute window. This measures response starts, not completed inference or errors occurring after an SSE response begins. Admission 503/504 responses remain included; use admission results to identify their contribution.

### ForetokenNVIDIAGPUTemperatureHigh

An attributed NVIDIA GPU reaches the selected ModelService's temperature threshold for 2 minutes. `thresholds.nvidiaTemperatureCelsius` defaults to 85°C. Inspect temperature, cooling, and device load for the reported Pod and device.

### ForetokenNVIDIAGPUPowerUsageHigh

An attributed NVIDIA GPU reaches the selected ModelService's power threshold for 5 minutes. Select the rule and supply a positive `thresholds.nvidiaPowerWatts`. Check workload and device power settings against the intended operating envelope. GPU rules cover the service's owned ModelGroups and do not apply to MetaX devices.
