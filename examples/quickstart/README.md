<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Single-Model Quick Start

[English](README.md) | [中文](README_zh.md)

Serve `Qwen/Qwen3-0.6B` through an OpenAI-compatible frontend. The example requests one GPU, 8 CPU cores, and 52 GiB of memory, including two frontend replicas; allow additional capacity for the platform.

## Deploy and request

Install Foretoken using the repository [Quick Start](../../README.md#quick-start), then run from the repository root:

```bash
foretoken deploy examples/quickstart --timeout 20m
FRONTEND_URL="$(foretoken endpoint examples/quickstart)"
curl --fail-with-body "$FRONTEND_URL/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"Qwen/Qwen3-0.6B","messages":[{"role":"user","content":"Reply with: Foretoken is ready"}],"max_tokens":32,"temperature":0}'
printf '\n'
```

Gateway deployments also need the request Host; see [Gateway mode](../../cli/README.md#gateway-mode).

## Change the model or capacity

Edit [`model.yaml`](model.yaml) for the model, replica count, resources, and [engine parameters](../../docs/inference-parameters.md). Edit [`frontend.yaml`](frontend.yaml) to change frontend replicas. Redeploy the same directory after changing configuration.

[`cache.yaml`](cache.yaml) uses the repository-root `data/` on local k3d and dynamic storage on other clusters. See [model storage](../../docs/model-storage.md) for existing directories or a custom StorageClass.

For two models and queue-based autoscaling, use the [multi-model example](../multi-model-quickstart/README.md). For AWQ or loading-time quantization, use [quantized models](../quantized-model/README.md).

## Clean up

```bash
foretoken delete examples/quickstart
```

This deletes the example namespace and its services and PVCs. Directory-backed model files remain for reuse.
