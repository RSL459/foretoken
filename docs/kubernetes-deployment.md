<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Deploy Foretoken on Kubernetes

[English](kubernetes-deployment.md) | [中文](kubernetes-deployment_zh.md)

Install Foretoken on an existing K3s, RKE2, KubeSphere, cloud, or other Kubernetes cluster, then serve a model through an OpenAI-compatible endpoint.

## Before you start

Prepare Python 3.11+, Git, kubectl, Helm, and a kubeconfig for the cluster. GPU nodes need their vendor driver and Kubernetes device plugin. The cluster needs a default StorageClass; shared model storage on multiple nodes requires `ReadWriteMany` support.

```bash
kubectl config current-context
kubectl get nodes
```

## 1. Install Foretoken

To deploy edited source, use the [source installation](#deploy-current-source-to-this-cluster) instead.

```bash
git clone https://github.com/shiweijiezero/foretoken.git
cd foretoken
pip install foretoken
foretoken install
```

The CLI selects the NVIDIA or MetaX runtime. For MetaX cluster preparation, see the [MetaX platform guide](development/metax-platform.md).

Model services need an externally reachable address. Cloud Kubernetes and K3s usually provide LoadBalancer addresses. On clusters without address allocation, configure an address range as described [below](#assign-service-addresses). For an existing Gateway, follow [Gateway mode](../cli/README.md#gateway-mode).

## 2. Deploy and request a model

The Quick Start requests one GPU, 8 CPU cores, and 52 GiB of memory, plus platform capacity. Its cache uses a dynamic PVC on this cluster, with `ReadWriteOnce` on a single schedulable node or `ReadWriteMany` on multiple nodes. See [model storage](model-storage.md) to select a StorageClass or use existing files.

```bash
foretoken deploy examples/quickstart --timeout 20m
FRONTEND_URL="$(foretoken endpoint examples/quickstart)"
curl --fail-with-body "$FRONTEND_URL/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"Qwen/Qwen3-0.6B","messages":[{"role":"user","content":"Hello"}],"max_tokens":32}'
printf '\n'
```

## 3. Remove Foretoken

```bash
foretoken delete examples/quickstart
foretoken uninstall
```

The Kubernetes cluster remains running.

## Assign service addresses

If installation reports `LoadBalancer support Not verified`, obtain a range of unused addresses in the nodes' subnet from the cluster administrator. Save it in `deploy/platform-values.yaml`, replacing the example range:

```yaml
loadBalancer:
  managedAddresses:
    - 192.168.1.240-192.168.1.250
```

Reapply your installation command with `--values deploy/platform-values.yaml`. Foretoken prepares MetalLB in Layer 2 mode to assign addresses to services. Nodes and clients must be able to reach these addresses.

## Deploy current source to this cluster

Get the checkout with the `git clone` and `cd` commands above, then run from its root. A source installation needs a registry reachable by the cluster's build Pods and every node. Replace the example registry with your repository prefix:

```bash
pip install -e .
REGISTRY=registry.example.com:5000/foretoken
foretoken install -e . --registry "$REGISTRY"
foretoken deploy examples/quickstart --timeout 20m
```

After editing the checkout, repeat `foretoken deploy`. Engine checkouts and runtime changes are covered by [source deployment](custom-deployment.md).

### Authenticated registry

Before the source installation, use Docker to log in and create credentials in the platform and workload namespaces:

```bash
docker login registry.example.com:5000
kubectl create namespace foretoken-platform
kubectl apply -f examples/quickstart/namespace.yaml
for NAMESPACE in foretoken-platform foretoken-demo; do
  kubectl create secret generic registry-auth \
    --namespace "$NAMESPACE" \
    --from-file=.dockerconfigjson="$HOME/.docker/config.json" \
    --type=kubernetes.io/dockerconfigjson
done
```

For namespaces that already exist, skip their creation. Save these references in `deploy/platform-values.yaml`:

```yaml
imagePullSecrets:
  - name: registry-auth
workload:
  imagePullSecrets:
    - name: registry-auth
```

Add `--values deploy/platform-values.yaml` to the source installation command. Create the same Secret in any additional workload namespace that uses these images.
