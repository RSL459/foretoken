<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Multi-Model Quick Start

[English](README.md) | [中文](README_zh.md)

Serve two models through one frontend: `Qwen/Qwen3-0.6B` scales from one to three replicas with queue demand; `unsloth/Llama-3.2-1B-Instruct` runs one fixed replica.

The initial deployment requests two GPUs, 12 CPU cores, and 100 GiB of memory. At full scale it requests four GPUs, 20 CPU cores, and 196 GiB of memory, including the frontend. Allow additional capacity for the platform.

## Deploy and request

Install Foretoken using the repository [Quick Start](../../README.md#quick-start), then run from the repository root:

```bash
foretoken deploy examples/multi-model-quickstart --timeout 20m
export FRONTEND_URL="$(foretoken endpoint examples/multi-model-quickstart)"
for MODEL in Qwen/Qwen3-0.6B unsloth/Llama-3.2-1B-Instruct; do
  curl --fail-with-body "$FRONTEND_URL/v1/chat/completions" \
    -H 'Content-Type: application/json' \
    -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Hello\"}],\"max_tokens\":32}"
  printf '\n'
done
```

The request's `model` selects the service. The examples share model storage with the single-model Quick Start; see [model storage](../../docs/model-storage.md) for cluster-specific choices. Gateway access is configured in [Gateway mode](../../cli/README.md#gateway-mode).

## Observe queue autoscaling

Qwen evaluates demand every five seconds, changes by at most one replica per evaluation, and uses a five-minute scale-down stabilization window.

In a separate terminal, watch its capacity:

```bash
kubectl get modelpool,modelgroup -n foretoken-multi-model-demo --watch
```

In the deployment terminal, send 32 requests with at most eight in flight:

```bash
seq 1 32 | xargs -P8 -I{} sh -c '
  curl --fail --silent --show-error \
    "$FRONTEND_URL/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"Qwen/Qwen3-0.6B\",\"messages\":[{\"role\":\"user\",\"content\":\"Explain Kubernetes request routing in detail.\"}],\"max_tokens\":512}"
'
```

Queue pressure can add replicas when GPU capacity and request duration permit. Inspect recommendations and applied capacity with:

```bash
kubectl get modelservice multi-model-qwen3-0.6b \
  -n foretoken-multi-model-demo -o json | jq '.status.autoscaling'
```

See [autoscaling](../../docs/autoscaling.md) to tune queue targets, polling, or stabilization.

## Clean up

```bash
foretoken delete examples/multi-model-quickstart
```
