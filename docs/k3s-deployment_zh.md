<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# 在 K3s 上部署 Foretoken

[English](k3s-deployment.md) | [中文](k3s-deployment_zh.md)

如果需要在一台或多台 Linux 机器上创建小型 K3s 集群，请使用本指南。已有 K3s 集群请直接阅读[从源码部署 Foretoken](custom-deployment_zh.md#远程集群)。

## 1. 安装 K3s server

在第一台 Linux 机器上以 root 执行：

```bash
curl -sfL https://get.k3s.io | sh -
```

检查节点：

```bash
sudo k3s kubectl get nodes
```

K3s kubeconfig 位于 `/etc/rancher/k3s/k3s.yaml`。使用普通 `kubectl` 客户端时：

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl get nodes
```

如果要运行 GPU 工作负载，请先在节点安装 NVIDIA 驱动、NVIDIA Container Toolkit 和 Kubernetes device plugin。

## 2. 加入 worker 节点

在 server 上读取加入 token：

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```

在每台 worker 上替换占位符后执行：

```bash
curl -sfL https://get.k3s.io | \
  K3S_URL=https://SERVER_ADDRESS:6443 \
  K3S_TOKEN=SERVER_NODE_TOKEN \
  sh -
```

回到 server 检查集群：

```bash
sudo k3s kubectl get nodes -o wide
```

## 3. 安装 Foretoken

使用发布镜像安装平台：

```bash
pip install foretoken
foretoken install
```

源码安装会在 Kubernetes 中构建镜像，需要准备构建 Pod 和所有节点都能访问的镜像仓库。先按[从源码部署 Foretoken](custom-deployment_zh.md#远程集群)配置，再执行：

```bash
pip install -e .
foretoken install -e . --registry REGISTRY
```

部署快速开始示例：

```bash
foretoken deploy examples/quickstart --timeout 20m
```

## 4. 删除 K3s

K3s 会在每台机器上安装卸载脚本。先删除 worker，再删除 server：

```bash
/usr/local/bin/k3s-agent-uninstall.sh
/usr/local/bin/k3s-uninstall.sh
```

每台机器只执行实际存在的脚本；这些命令会删除 K3s 安装及本地集群数据。
