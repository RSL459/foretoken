<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 服务可观测性

[English](README.md) | 简体中文

部署[快速开始](../quickstart/README_zh.md)的服务，并在 `observability.yaml` 中配置告警。该文件分别补充 FrontendService 和 ModelService 的配置，两份规则列表默认都为空。

通过 `foretoken install` 安装平台后，只在对应列表中添加需要的告警名称，然后部署：

```bash
foretoken deploy examples/observability --timeout 20m
```

该部署沿用快速开始的模型、资源、命名空间和数据目录。按其示例发送请求，再到 Grafana 打开 **Foretoken System Overview**。告警名称及触发条件见[告警参考](../../observability/runbooks/alerts_zh.md)。

关闭某条告警时，移除其名称并再次部署该目录。删除整个部署：

```bash
foretoken delete examples/observability
```

共享监控仍保留。监控访问和通知接入见[可观测性指南](../../observability/README_zh.md)。
