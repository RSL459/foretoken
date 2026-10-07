<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Foretoken command-line tool

English | [简体中文](README_zh.md)

Use `foretoken` to install the platform, deploy model services, inspect their status, and run benchmarks.

## Install

Prepare Python 3.11+, kubectl, Helm, and a Kubernetes context. GPU nodes need the vendor driver and device plugin. To create a local cluster first, follow the [k3d](../docs/k3d-deployment.md) or [kind](../docs/kind-deployment.md) guide.

```bash
pip install foretoken
foretoken --version
foretoken install
```

This installs the published platform with monitoring and persistent logs. For development, run `pip install -e .` and `foretoken install -e .` from the checkout root instead; see [source deployment](../docs/custom-deployment.md) for registry and engine settings.

## Deploy and operate model services

Get the examples from the [Quick Start](../README.md#install-and-deploy), then run from the checkout root:

```bash
foretoken deploy examples/quickstart --timeout 20m
foretoken endpoint examples/quickstart
```

`deploy` applies the configuration and waits for readiness, showing progress and logs. It also updates existing services to the current platform version. Updating the platform alone leaves existing services on their selected versions.

Inspect a deployment, or follow all services in a namespace:

```bash
foretoken status examples/quickstart
foretoken status -n foretoken-demo --watch
```

Press Ctrl+C to stop watching. For multiple models, use the [multi-model example](../examples/multi-model-quickstart/README.md).

## Gateway mode

To expose services through a shared hostname-based gateway:

```bash
foretoken install --frontend-mode gateway
```

For a source installation, retain `-e .` and your registry and engine options. To reuse an existing Gateway, add `--gateway-name inference-gateway --gateway-namespace gateway-system`; select a listener with `--gateway-section-name` when needed.

Choose a hostname for the service and add it to `examples/quickstart/frontend.yaml`:

```yaml
spec:
  hostname: foretoken.example.com
```

Redeploy, resolve the gateway address and hostname, then send a request:

```bash
foretoken deploy examples/quickstart --timeout 20m
FORETOKEN_FRONTEND_URL="$(foretoken endpoint examples/quickstart)"
FORETOKEN_REQUEST_HOST="$(foretoken endpoint examples/quickstart --host)"

curl --fail-with-body "$FORETOKEN_FRONTEND_URL/v1/chat/completions" \
  -H "Host: $FORETOKEN_REQUEST_HOST" \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen/Qwen3-0.6B","messages":[{"role":"user","content":"Hello"}]}'
```

## Customize installation

Use `foretoken install --values PATH` for platform overrides. The following guides own the corresponding settings:

| Task | Guide |
| --- | --- |
| Configure registry access, service IPs, or shared-cluster prerequisites | [Kubernetes deployment](../docs/kubernetes-deployment.md) |
| Build from a Foretoken or engine checkout | [Source deployment](../docs/custom-deployment.md) |
| Select MetaX hardware | [MetaX deployment](../docs/metax-deployment.md) |
| Configure model storage, Dragonfly, or ModelExpress | [Model storage](../docs/model-storage.md) |
| Configure Grafana, logs, or alerts | [Observability](../observability/README.md) |

Run `foretoken install --help` for available options.

## Benchmark and profile

| Task | Command | Guide |
| --- | --- | --- |
| Measure latency and throughput | `foretoken perf` | [Performance](../benchmarks/docs/perf/README.md) |
| Score model answers | `foretoken eval` | [Evaluation](../benchmarks/docs/eval/README.md) |
| Redraw saved results | `foretoken plot RESULT_DIR` | [Plots and comparisons](../benchmarks/docs/perf/sweep.md) |
| Record CPU/GPU execution | `foretoken perf --profile` | [Profiling](../benchmarks/docs/profile/README.md) |

Each command's guide provides a complete example; `foretoken COMMAND --help` lists its options.

## Clean up

```bash
foretoken delete examples/quickstart
foretoken uninstall
```

Uninstall preserves CRDs, log storage, and reused cluster components. For a local cluster created with the CLI, remove it with `foretoken cluster delete k3d --name foretoken-dev` or the equivalent `kind` command.
