<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# RSI starting deployments

English | [简体中文](README_zh.md)

Use these configurations as editable starting points for [RSI tasks](../../rsi-playbooks/tasks/README.md). The [Qwen deployment](qwen-decode/) serves `Qwen/Qwen3.5-35B-A3B` in BF16 with tensor parallelism across four GPUs on one node. It starts without speculative decoding; the task can explore other configurations within its resource budget.

## Deploy Qwen

Use a [MetaX-enabled Foretoken platform](../../docs/development/metax-platform.md) with a runtime supporting this model, Gateway frontend access, and a default StorageClass supporting `ReadWriteOnce`. The example creates a dedicated namespace and a 128 GiB runtime-cache volume. It downloads model files from Hugging Face when needed; see [model storage](../../docs/model-storage.md) to reuse an existing model directory.

Run from the repository root:

```bash
foretoken deploy examples/rsi/qwen-decode --timeout 60m
foretoken status examples/rsi/qwen-decode
```

The deployment is ready when the model and frontend services are Ready. Its resource settings are:

| Workload | CPU request / limit | Memory request / limit | GPUs |
| --- | --- | --- | --- |
| Model, one replica | 16 / 30 | 256 / 508 GiB | 4 |
| Frontend, one replica | 1 / 2 | 2 / 4 GiB | 0 |
| Total | 17 / 32 | 258 / 512 GiB | 4 |

Requests leave scheduling space for platform services, builds, and benchmark clients. These are starting allocations, not measured optimal values; adjust them within the task's total budget. [model.yaml](qwen-decode/model.yaml) sets a 131072-token context limit and at most 16 sequences; check that the selected workload, including generated tokens, fits the context.

## Send a request

The CLI resolves the Gateway address; the HTTP Host selects this candidate, so the example hostname does not need a DNS record for these commands.

```bash
FRONTEND_URL="$(foretoken endpoint examples/rsi/qwen-decode)"
REQUEST_HOST="$(foretoken endpoint examples/rsi/qwen-decode --host)"

curl --fail-with-body --no-buffer "$FRONTEND_URL/v1/chat/completions" \
  -H "Host: $REQUEST_HOST" \
  -H 'Content-Type: application/json' \
  -d '{"model":"Qwen/Qwen3.5-35B-A3B","messages":[{"role":"user","content":"Explain tensor parallelism briefly."}],"max_tokens":128,"stream":true}'
```

Use the [Qwen task's evaluation commands](../../rsi-playbooks/tasks/qwen-decode.md#evaluation-commands) for performance comparisons. `foretoken perf` resolves the Gateway Host from the deployment configuration.

## Run independent candidates

Give each candidate its own [worktree and deployment](../../docs/custom-deployment.md#run-candidates-in-parallel). In each copy of this example, choose a unique namespace in both `namespace.yaml` and `kustomization.yaml`, and a unique `spec.hostname` in `frontend.yaml`. Each namespace gets its own runtime-cache PVC; keep writable caches separate even when reusing model files.

For the Qwen task's two eight-GPU nodes, place two four-GPU candidates on each node using `ModelService.spec.nodeSelector` when explicit placement is needed. Four candidates occupy all 16 GPUs. To run more experiments, replace some full-service allocations with smaller experiments, such as single-GPU kernel probes, and account for CPU, memory, storage, and competing load. Increasing `replicas` on one ModelService creates serving replicas, not isolated experiments.

## Clean up

After preserving results and confirming that the candidate is no longer needed, delete its own configuration:

```bash
foretoken delete examples/rsi/qwen-decode
```

This removes the example namespace and its cache PVC. The volume's data follows the StorageClass reclaim policy. Keep the shared platform while other candidates are using it.
