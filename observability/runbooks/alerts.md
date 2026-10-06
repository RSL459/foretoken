<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Alert reference

English | [简体中文](alerts_zh.md)

Choose alerts for a frontend or model service, configure any required thresholds, and use the notification to locate the affected service or device.

## Choose alerts

| Rule | Service | Trigger |
| --- | --- | --- |
| [ForetokenMetricsTargetDown](#foretokenmetricstargetdown) | Frontend or model | A metrics endpoint cannot be scraped for 1 minute. |
| [ForetokenFrontendHTTPResponseStart5xxRatioHigh](#foretokenfrontendhttpresponsestart5xxratiohigh) | Frontend | HTTP response-start 5xx exceeds 5% for 2 minutes, at least 0.1 responses/s over a 5-minute window. |
| [ForetokenAdmissionCapacityRejectionRatioHigh](#foretokenadmissioncapacityrejectionratiohigh) | Frontend | Admission capacity rejections exceed the configured fraction. |
| [ForetokenAdmissionTimeoutRatioHigh](#foretokenadmissiontimeoutratiohigh) | Frontend | Admission timeouts exceed the configured fraction. |
| [ForetokenAdmissionAdmittedQueueP95High](#foretokenadmissionadmittedqueuep95high) | Frontend | Queue-wait p95 for admitted requests exceeds the configured duration. |
| [ForetokenAdmissionTelemetryMissing](#foretokenadmissiontelemetrymissing) | Frontend | Scraping succeeds but required admission metrics are missing for 5 minutes. |
| [ForetokenNVIDIAGPUTemperatureHigh](#foretokennvidiagputemperaturehigh) | Model | NVIDIA GPU temperature reaches the threshold for 2 minutes; default 85°C. |
| [ForetokenNVIDIAGPUPowerUsageHigh](#foretokennvidiagpupowerusagehigh) | Model | NVIDIA GPU power reaches the configured threshold for 5 minutes. |

## Enable and configure

Add the selected rules under the service's `spec`. For example:

```yaml
observability:
  alerts:
    rules:
      - ForetokenMetricsTargetDown
```

Redeploy the service configuration to apply changes. Remove a rule, or set `rules: []`, to disable it. A runnable deployment is available in the [observability example](../../examples/observability/README.md).

Rules with configurable thresholds use `observability.alerts.thresholds`:

| Rule | Fields under `thresholds` |
| --- | --- |
| Capacity rejection | `admission.capacityRejectionRatio` and `admission.minResultRate` |
| Admission timeout | `admission.timeoutRatio` and `admission.minResultRate` |
| Admitted queue p95 | `admission.admittedQueueP95Seconds` and `admission.minQueuedAdmissionRate` |
| GPU temperature | Optional `nvidiaTemperatureCelsius`, default `85` |
| GPU power | Required positive `nvidiaPowerWatts` |

Admission fractions use completed calls in the corresponding stage and range from 0 to 1. Queue-latency thresholds use seconds; minimum rates use calls/s. The queue rule's minimum rate counts requests that queued and were admitted.

Under `thresholds.admission`, optional `scope` defaults to `service` and can be `pod`; `window` defaults to `1m` and `for` to `5m`. These durations accept whole seconds, minutes, or hours.

Connect a [Lark](../integrations/lark/README.md), [Slack](../integrations/slack/README.md), or [DingTalk](../integrations/dingtalk/README.md) receiver to receive notifications. If selected rules do not appear, check the service's `AlertsReady` condition.

## Respond to an alert

Open Foretoken System Overview in Grafana and select the namespace and frontend or model named in the notification.

### ForetokenMetricsTargetDown

Check the scrape error in Prometheus Targets, then inspect the affected Pod and network access to its metrics endpoint.

### ForetokenFrontendHTTPResponseStart5xxRatioHigh

Inspect frontend status-code trends and logs. Use the Admission section to identify capacity rejection or timeout responses, then check model availability and backend errors.

### ForetokenAdmissionCapacityRejectionRatioHigh

Compare each frontend Pod's traffic, occupancy, and configured limits. `intake` identifies HTTP residency limits; `work` identifies work admission. Check backend load before adjusting frontend limits.

### ForetokenAdmissionTimeoutRatioHigh

Compare queue occupancy and waiting time with `queueTimeout` and the request timeout. The result breakdown separates queue expiry from the request budget expiring before admission.

### ForetokenAdmissionAdmittedQueueP95High

Inspect the admitted-wait curve alongside queue occupancy and model capacity. Use timeout results to see whether requests are also leaving the queue without admission.

### ForetokenAdmissionTelemetryMissing

Inspect the Admission replica table for incomplete reporting and compare Pod runtime versions. Check monitoring configuration if the issue persists after an upgrade completes.

### ForetokenNVIDIAGPUTemperatureHigh

Check temperature, cooling, and workload on the device named in the notification.

### ForetokenNVIDIAGPUPowerUsageHigh

Compare the device's power draw and workload with its intended operating envelope and configured alert threshold.
