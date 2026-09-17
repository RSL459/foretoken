<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Service observability

English | [简体中文](README_zh.md)

Deploy the [Quick Start](../quickstart/README.md) with alert settings kept in `observability.yaml`. It patches the FrontendService and ModelService independently; both rule lists are empty by default.

After installing the platform with `foretoken install`, add only the wanted rule names to the corresponding list and run:

```bash
foretoken deploy examples/observability --timeout 20m
```

The deployment uses the Quick Start's model, resources, namespace, and data directory. Follow its request example, then open **Foretoken System Overview** in Grafana. Alert names and trigger conditions are listed in the [alert reference](../../observability/runbooks/alerts.md).

To disable a rule, remove its name and deploy the directory again. To remove the deployment:

```bash
foretoken delete examples/observability
```

Shared monitoring remains installed. See [Observability](../../observability/README.md) for monitoring access and notification setup.
