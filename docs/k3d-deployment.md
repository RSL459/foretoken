<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Deploy Foretoken with k3d

[English](k3d-deployment.md) | [中文](k3d-deployment_zh.md)

k3d runs the lightweight k3s Kubernetes distribution in Docker containers. It is well suited to creating an isolated, disposable Foretoken cluster on a shared GPU server while retaining standard Helm, CRDs, and Kubernetes APIs. All k3d cluster nodes run on one Docker host; use k3s or Kubernetes for deployments across physical machines.

## Prerequisites

The host needs:

- Python 3.11 or later;
- Linux;
- an NVIDIA driver;
- NVIDIA Container Toolkit;
- Docker configured to use the NVIDIA runtime; and
- k3d, kubectl, and Helm.

## 1. Enter the repository and select GPUs

Get the repository and run the remaining commands from its root:

```bash
git clone https://github.com/shiweijiezero/foretoken.git
cd foretoken
pip install -e .
```

List GPUs:

```bash
nvidia-smi
```

Select GPUs without other workloads. The Quick Start needs one GPU, 8 CPU, and 52 GiB memory; allow additional capacity for the platform. The following uses GPUs 6 and 7 and the cluster name `foretoken-qwen-test`; change them to your available devices. Docker limits the physical GPUs visible to the node, and Pods request a count from that set:

```bash
export GPU_INDICES=6,7
export CLUSTER=foretoken-qwen-test
```

## 2. Create a GPU-restricted k3d cluster

```bash
foretoken cluster create k3d --name "$CLUSTER" --gpus "$GPU_INDICES"
kubectl get nodes
```

The command mounts the NVIDIA runtime and the repository `data/` directory, installs the NVIDIA device plugin, and selects the created kubeconfig context.

## 4. Install and access Foretoken

### 4.1 Choose a deployment method

Build and install the cluster platform from this checkout:

```bash
foretoken install -e .
```

To use published packages and images instead, get the examples from the chosen [release](https://github.com/shiweijiezero/foretoken/releases) and install:

```bash
pip install foretoken
foretoken install
```

### 4.2 Local mode

Deploy the Quick Start and resolve the address assigned by k3s ServiceLB:

```bash
foretoken deploy examples/quickstart --timeout 20m
FORETOKEN_FRONTEND_URL="$(foretoken endpoint examples/quickstart)"
FORETOKEN_REQUEST_HOST="$(foretoken endpoint examples/quickstart --host)"
```

### 4.3 Gateway mode

First, set the public hostname in `examples/quickstart/frontend.yaml`:

```yaml
spec:
  hostname: foretoken.example.com
```

Enable Gateway mode and deploy the Quick Start:

```bash
foretoken install -e . --frontend-mode gateway
# For a release installation: foretoken install --frontend-mode gateway
foretoken deploy examples/quickstart --timeout 20m
```

Resolve the configured Gateway endpoint:

```bash
FORETOKEN_FRONTEND_URL="$(foretoken endpoint examples/quickstart)"
FORETOKEN_REQUEST_HOST="$(foretoken endpoint examples/quickstart --host)"
```

### 4.4 Send an OpenAI API-compatible request

```bash
curl "$FORETOKEN_FRONTEND_URL/v1/chat/completions" \
  -H "Host: $FORETOKEN_REQUEST_HOST" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Qwen/Qwen3-0.6B",
    "messages": [{"role": "user", "content": "Reply with: Foretoken is ready"}],
    "max_tokens": 32,
    "temperature": 0
  }'
printf '\n'
```

## 5. Clean up

Delete the cluster:

```bash
k3d cluster delete "$CLUSTER"
```

Deleting the cluster stops its Pods and releases the GPUs. Keep `data`; restore its bind mount when creating another cluster to reuse the downloaded models.
