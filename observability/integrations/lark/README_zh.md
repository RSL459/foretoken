<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Lark 告警通知

[English](README.md) | 简体中文

通过群自定义机器人和集群中的 Alertmanager，将 Foretoken 告警发送到 Lark 群。通知包含受影响资源、告警详情、时间和排障链接。

## 开始前

启用 [Foretoken 告警](../../README_zh.md#告警)，并取得目标 Lark 群的自定义机器人 webhook。已安装的 Prometheus Operator 和 Alertmanager 需要支持 `webhookConfigs.payload`。

目标 Alertmanager 需要通过 `alertmanagerConfigSelector` 选中 `foretoken-lark` 配置。按下文安装到 Alertmanager 所在命名空间时，监控管理员可将 `spec.alertmanagerConfigMatcherStrategy.type` 设为 `OnNamespaceExceptForAlertmanagerNamespace`，接收 Foretoken 工作负载命名空间的告警。参阅 [Alertmanager 配置指南](https://prometheus-operator.dev/docs/developer/alerting/)。

## 接入机器人

在 [alertmanagerconfig.yaml](alertmanagerconfig.yaml) 中将 `$language` 设为 `zh`（默认）、`en` 或 `bilingual`。`$timezone` 默认使用 `Local`，跟随 Alertmanager 容器的时区；可改为 `Europe/Berlin` 等 IANA 时区名称。消息中的时间包含 UTC 偏移。

在仓库根目录执行。将 `monitoring` 替换为 Alertmanager 所在命名空间，将 webhook 占位符替换为机器人的 URL：

```bash
ALERTMANAGER_NAMESPACE=monitoring

# 将 webhook 保存到 Secret。
kubectl create secret generic foretoken-lark-webhook \
  --namespace "$ALERTMANAGER_NAMESPACE" \
  --from-literal=url='<LARK_CUSTOM_BOT_WEBHOOK_URL>'

# 在同一命名空间添加通知接收器。
kubectl apply \
  --namespace "$ALERTMANAGER_NAMESPACE" \
  --filename observability/integrations/lark/alertmanagerconfig.yaml
```

如果 Secret 已存在，按现有凭据管理流程更新，不将其内容提交到版本库。

## 验证投递

在 Alertmanager 中确认配置已加载并路由到 Lark。测试告警使用 `service=foretoken` 和实际的 Foretoken 工作负载命名空间，分别确认群内收到触发和解除通知。

没有收到消息时，检查配置选择器、命名空间匹配和 Alertmanager 投递日志。

## 移除集成

```bash
kubectl delete alertmanagerconfig foretoken-lark \
  --namespace "$ALERTMANAGER_NAMESPACE"
kubectl delete secret foretoken-lark-webhook \
  --namespace "$ALERTMANAGER_NAMESPACE"
```
