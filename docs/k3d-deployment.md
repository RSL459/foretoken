<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Deploy Foretoken with k3d

[English](k3d-deployment.md) | [中文](k3d-deployment_zh.md)

Run a GPU-enabled Kubernetes cluster on one Linux host. k3d runs its nodes in Docker containers; for multiple physical machines, use the [Kubernetes deployment guide](kubernetes-deployment.md).

## Before you start

Install Python 3.11+, Git, Docker, an NVIDIA driver, [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html), [k3d](https://k3d.io/stable/#installation), [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/), and [Helm](https://helm.sh/docs/intro/install/). Configure Docker with the NVIDIA runtime and confirm that `docker info` works without `sudo`.

The example requests one GPU, 8 CPU cores, and 52 GiB of host memory, plus capacity for the platform.

## 1. Get the examples and select a GPU

```bash
git clone https://github.com/shiweijiezero/foretoken.git
cd foretoken
pip install foretoken
nvidia-smi
```

Use an available GPU index from `nvidia-smi`. This example selects GPU 0; use `0,1` to expose two GPUs:

```bash
GPU_INDICES=0
CLUSTER=foretoken-dev
foretoken cluster create k3d --name "$CLUSTER" --gpus "$GPU_INDICES"
kubectl get nodes
```

The cluster uses the selected GPUs and mounts the repository's `data/` directory for model files and caches. The CLI installs the NVIDIA device plugin and selects the new Kubernetes context.

## 2. Install and deploy

```bash
foretoken install
foretoken deploy examples/quickstart --timeout 20m
```

This deploys one `Qwen/Qwen3-0.6B` model replica and a frontend service. To build the platform from this checkout instead, use `pip install -e .` and `foretoken install -e .`; subsequent source changes are deployed with the same `foretoken deploy` command. See [source deployment](custom-deployment.md) for engine changes.

## 3. Send a request

```bash
FRONTEND_URL="$(foretoken endpoint examples/quickstart)"
curl --fail-with-body "$FRONTEND_URL/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"Qwen/Qwen3-0.6B","messages":[{"role":"user","content":"Reply with: Foretoken is ready"}],"max_tokens":32,"temperature":0}'
printf '\n'
```

For hostname-based access through a Gateway, follow [Gateway mode](../cli/README.md#gateway-mode).

## 4. Clean up

```bash
foretoken cluster delete k3d --name "$CLUSTER"
```

Deleting the cluster stops its workloads and releases the GPUs. The host's `data/` directory remains available for a later cluster created from the same checkout.
