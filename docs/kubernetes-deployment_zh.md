<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# 在 Kubernetes 上部署 Foretoken

[English](kubernetes-deployment.md) | [中文](kubernetes-deployment_zh.md)

在已有的 K3s、RKE2、KubeSphere、云上或其他 Kubernetes 集群中安装 Foretoken，并通过 OpenAI 兼容接口调用模型。

## 开始前

准备 Python 3.11+、Git、kubectl、Helm 和集群 kubeconfig。GPU 节点需要安装对应驱动和 Kubernetes 设备插件。集群需要默认 StorageClass；多节点共享模型存储时，存储类需支持 `ReadWriteMany`。

```bash
kubectl config current-context
kubectl get nodes
```

## 1. 安装 Foretoken

需要部署源码改动时，改用[源码安装](#将当前源码部署到集群)。

```bash
git clone https://github.com/shiweijiezero/foretoken.git
cd foretoken
pip install foretoken
foretoken install
```

CLI 会选择 NVIDIA 或沐曦运行时。沐曦集群的准备步骤见[沐曦平台指南](development/metax-platform_zh.md)。

模型服务需要可从集群外访问的地址。云上 Kubernetes 和 K3s 通常已提供 LoadBalancer 地址分配；未提供地址分配的集群可按[下方说明](#分配服务地址)设置可用地址范围。复用已有 Gateway 的步骤见[网关模式](../cli/README_zh.md#网关模式)。

## 2. 部署并调用模型

快速开始申请 1 张 GPU、8 核 CPU 和 52 GiB 内存，另外需要为平台预留资源。示例缓存在此集群中使用动态 PVC：只有一个可调度节点时使用 `ReadWriteOnce`，多个节点时使用 `ReadWriteMany`。选择 StorageClass 或复用已有文件的方式见[模型存储](model-storage_zh.md)。

```bash
foretoken deploy examples/quickstart --timeout 20m
FRONTEND_URL="$(foretoken endpoint examples/quickstart)"
curl --fail-with-body "$FRONTEND_URL/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"Qwen/Qwen3-0.6B","messages":[{"role":"user","content":"你好"}],"max_tokens":32}'
printf '\n'
```

## 3. 删除 Foretoken

```bash
foretoken delete examples/quickstart
foretoken uninstall
```

Kubernetes 集群继续保留。

## 分配服务地址

安装提示 `LoadBalancer support Not verified` 时，向集群管理员取得节点子网中未使用的地址范围。在 `deploy/platform-values.yaml` 中保存，将示例替换为实际范围：

```yaml
loadBalancer:
  managedAddresses:
    - 192.168.1.240-192.168.1.250
```

在原安装命令中传入 `--values deploy/platform-values.yaml`。Foretoken 会准备 Layer 2 模式的 MetalLB，为服务分配地址；节点和客户端需能够访问这些地址。

## 将当前源码部署到集群

先按上方的 `git clone` 和 `cd` 命令获取源码，再从仓库根目录运行。源码安装需要构建 Pod 和所有节点均可访问的镜像仓库。将示例中的仓库地址替换为自己的仓库前缀：

```bash
pip install -e .
REGISTRY=registry.example.com:5000/foretoken
foretoken install -e . --registry "$REGISTRY"
foretoken deploy examples/quickstart --timeout 20m
```

修改源码后，重复运行 `foretoken deploy`。关联引擎源码和更换运行环境的用法见[源码部署指南](custom-deployment_zh.md)。

### 需要认证的镜像仓库

源码安装前，使用 Docker 登录，并在平台和工作负载的命名空间创建凭据：

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

命名空间已经存在时，跳过创建步骤。在 `deploy/platform-values.yaml` 中保存引用：

```yaml
imagePullSecrets:
  - name: registry-auth
workload:
  imagePullSecrets:
    - name: registry-auth
```

在源码安装命令中加入 `--values deploy/platform-values.yaml`。其他使用这些镜像的工作负载命名空间也需要同名 Secret。
