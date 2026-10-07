<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# 使用 k3d 部署 Foretoken

[English](k3d-deployment.md) | [中文](k3d-deployment_zh.md)

在一台 Linux 主机上运行支持 GPU 的 Kubernetes 集群。k3d 的节点运行在 Docker 容器中；跨物理机器部署请使用 [Kubernetes 部署指南](kubernetes-deployment_zh.md)。

## 开始前

安装 Python 3.11+、Git、Docker、NVIDIA 驱动、[NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)、[k3d](https://k3d.io/stable/#installation)、[kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/) 和 [Helm](https://helm.sh/docs/intro/install/)。为 Docker 配置 NVIDIA 运行时，并确认当前用户可以无 `sudo` 执行 `docker info`。

示例申请 1 张 GPU、8 核 CPU 和 52 GiB 主机内存，另外需要为平台预留资源。

## 1. 获取示例并选择 GPU

```bash
git clone https://github.com/shiweijiezero/foretoken.git
cd foretoken
pip install foretoken
nvidia-smi
```

按 `nvidia-smi` 的编号选择空闲 GPU。下面使用 GPU 0；需要两张卡时可改为 `0,1`：

```bash
GPU_INDICES=0
CLUSTER=foretoken-dev
foretoken cluster create k3d --name "$CLUSTER" --gpus "$GPU_INDICES"
kubectl get nodes
```

集群使用选定的 GPU，并挂载仓库中的 `data/` 保存模型和缓存。CLI 会安装 NVIDIA 设备插件，并切换到新集群的 Kubernetes context。

## 2. 安装平台并部署模型

```bash
foretoken install
foretoken deploy examples/quickstart --timeout 20m
```

示例部署一个 `Qwen/Qwen3-0.6B` 模型副本和一个前端服务。如需从当前源码构建平台，改用 `pip install -e .` 和 `foretoken install -e .`，后续代码修改仍通过同一条 `foretoken deploy` 命令部署。修改引擎的用法见[源码部署指南](custom-deployment_zh.md)。

## 3. 发送请求

```bash
FRONTEND_URL="$(foretoken endpoint examples/quickstart)"
curl --fail-with-body "$FRONTEND_URL/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"Qwen/Qwen3-0.6B","messages":[{"role":"user","content":"请回复：Foretoken 已就绪"}],"max_tokens":32,"temperature":0}'
printf '\n'
```

通过域名和 Gateway 访问的设置见[网关模式](../cli/README_zh.md#网关模式)。

## 4. 清理

```bash
foretoken cluster delete k3d --name "$CLUSTER"
```

删除集群会停止其中的工作负载并释放 GPU。宿主机的 `data/` 目录保留，之后从同一仓库创建集群时可以继续复用。
