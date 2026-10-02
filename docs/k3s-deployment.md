<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Deploy Foretoken on K3s

[English](k3s-deployment.md) | [中文](k3s-deployment_zh.md)

Use this guide when creating a small K3s cluster on one or more Linux machines. For an existing K3s cluster, start with [Deploy Foretoken from Source](custom-deployment.md#remote-clusters).

## 1. Install a K3s server

Run this on the first Linux machine as root:

```bash
curl -sfL https://get.k3s.io | sh -
```

Check the node:

```bash
sudo k3s kubectl get nodes
```

The K3s kubeconfig is `/etc/rancher/k3s/k3s.yaml`. To use it with the regular `kubectl` client:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl get nodes
```

For a GPU workload, install the NVIDIA driver, NVIDIA Container Toolkit, and Kubernetes device plugin on the nodes before deploying a model.

## 2. Add worker nodes

On the server, read the join token:

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```

On each worker, replace the placeholders and run:

```bash
curl -sfL https://get.k3s.io | \
  K3S_URL=https://SERVER_ADDRESS:6443 \
  K3S_TOKEN=SERVER_NODE_TOKEN \
  sh -
```

Verify the cluster from the server:

```bash
sudo k3s kubectl get nodes -o wide
```

## 3. Install Foretoken

Release installation uses the platform's published images:

```bash
pip install foretoken
foretoken install
```

Source installation builds images in Kubernetes and requires a registry reachable by the Build Pods and every node. Follow [Deploy Foretoken from Source](custom-deployment.md#remote-clusters), then run:

```bash
pip install -e .
foretoken install -e . --registry REGISTRY
```

Deploy the Quick Start:

```bash
foretoken deploy examples/quickstart --timeout 20m
```

## 4. Remove K3s

K3s installs an uninstall script on each machine. Remove workers first, then the server:

```bash
/usr/local/bin/k3s-agent-uninstall.sh
/usr/local/bin/k3s-uninstall.sh
```

Only run the script that exists on each machine. These commands remove the K3s installation and its local cluster data.
