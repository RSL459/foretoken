<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Lark alert notifications

English | [简体中文](README_zh.md)

Send Foretoken alerts to a Lark group through its custom bot and the cluster's Alertmanager. Notifications include affected resources, alert details, timestamps, and runbook links.

## Before you start

Enable [Foretoken alerts](../../README.md#alerts) and obtain a custom bot webhook from the destination Lark group. The installed Prometheus Operator and Alertmanager must support `webhookConfigs.payload`.

The target Alertmanager must select the `foretoken-lark` configuration through `alertmanagerConfigSelector`. For the same-namespace installation below, the monitoring administrator can set `spec.alertmanagerConfigMatcherStrategy.type` to `OnNamespaceExceptForAlertmanagerNamespace` to accept alerts from Foretoken workload namespaces. See [Alertmanager configuration](https://prometheus-operator.dev/docs/developer/alerting/).

## Connect the bot

In [alertmanagerconfig.yaml](alertmanagerconfig.yaml), set `$language` to `zh` (the default), `en`, or `bilingual`. `$timezone` defaults to `Local`, using the Alertmanager container's time zone; an IANA name such as `Europe/Berlin` overrides it. Messages include the UTC offset.

Run from the repository root. Replace `monitoring` with the Alertmanager namespace and the webhook placeholder with the bot's URL:

```bash
ALERTMANAGER_NAMESPACE=monitoring

# Store the webhook in a Secret.
kubectl create secret generic foretoken-lark-webhook \
  --namespace "$ALERTMANAGER_NAMESPACE" \
  --from-literal=url='<LARK_CUSTOM_BOT_WEBHOOK_URL>'

# Add the notification receiver in the same namespace.
kubectl apply \
  --namespace "$ALERTMANAGER_NAMESPACE" \
  --filename observability/integrations/lark/alertmanagerconfig.yaml
```

If the Secret already exists, update it through your usual secret-management process. Keep its value out of version control.

## Verify delivery

In Alertmanager, confirm that the configuration is loaded and routes to Lark. Use a test alert with `service=foretoken` and an actual Foretoken workload namespace, then confirm that the Lark group receives both firing and resolved notifications.

If no message arrives, check the configuration selector, namespace matching, and Alertmanager delivery logs.

## Remove the integration

```bash
kubectl delete alertmanagerconfig foretoken-lark \
  --namespace "$ALERTMANAGER_NAMESPACE"
kubectl delete secret foretoken-lark-webhook \
  --namespace "$ALERTMANAGER_NAMESPACE"
```
