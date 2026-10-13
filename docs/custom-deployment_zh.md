<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# 从源码部署 Foretoken

[English](custom-deployment.md) | [中文](custom-deployment_zh.md)

从本地源码构建 Foretoken，并将源码改动部署到 Kubernetes 集群。

## 从源码安装

本机需要 Python 3.11+、Git、kubectl 和 Helm。集群需要允许运行 BuildKit Pod 和发布 Job，并有默认 StorageClass 保存编译缓存与发布的应用文件。需要自定义存储类时，在 `deploy/platform-values.yaml` 中分别用 `development.build.storageClassName` 或 `applicationFiles.storageClassName` 覆盖，并通过 `--values` 传入。

```bash
git clone https://github.com/shiweijiezero/foretoken.git
cd foretoken
kubectl config current-context
```

从当前源码安装 CLI：

```bash
pip install -e .
```

本地 kind 或 k3d 集群无需镜像仓库，可直接构建并安装：

```bash
foretoken install -e .
```

已有通过 Foretoken 命令安装的发布版平台，也可用同一命令切换到当前源码。编译在集群中执行。k3d 的 GPU 配置见[使用 k3d 部署 Foretoken](k3d-deployment_zh.md)。

## 部署与更新代码

在支持 GPU 的集群上部署仓库维护的[快速开始示例](../README_zh.md#快速开始)：

```bash
foretoken deploy examples/quickstart --timeout 20m
```

平台从源码安装后，部署命令会使用当前目录所在的 Foretoken Git 源码树。修改代码后，再执行同一条命令即可。若要从其他目录指定源码，使用 `foretoken deploy examples/quickstart -e /path/to/foretoken --timeout 20m`；Kustomize 路径仍相对于当前目录解析。

部署只为这些服务构建并选择前端和模型服务的运行环境，不会重新安装共享控制器或 CRD。平台代码或配置改动需要显式执行 `foretoken install -e .`。代码更新会重启受影响的工作负载，并可能重新加载模型权重。请求与清理操作见快速开始中的[发送请求](../README_zh.md#4-发送测试请求)和[停止与卸载](../README_zh.md#停止与卸载)。

CLI 的 Python 代码从执行 `pip install -e .` 时关联的源码树加载；修改其 Python 依赖后，需要重新安装。

### 在独立 worktree 中运行候选方案

先按上面的源码安装步骤安装一次共享平台。各 worktree 独立保存源码状态和编译缓存，可以并行构建和部署。每个候选使用不同的 Kubernetes namespace，隔离模型服务与前端。

从仓库根目录创建一个候选，并通过 Kustomize 覆盖快速开始示例：

```bash
git worktree add ../candidate-a -b experiment/candidate-a
cd ../candidate-a
mkdir -p examples/candidate
cat > examples/candidate/kustomization.yaml <<'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: candidate-a
resources:
  - ../quickstart
patches:
  - target:
      kind: ModelService
    patch: |-
      - op: replace
        path: /spec/resources/requests/gpu/count
        value: 2
      - op: replace
        path: /spec/engineArgs/tensor-parallel-size
        value: 2
  - target:
      kind: RuntimeCache
    patch: |-
      - op: replace
        path: /spec
        value:
          initialSize: 20Gi
          accessMode: ReadWriteOnce
          retentionPolicy: Delete
EOF

foretoken deploy examples/candidate --timeout 20m
foretoken perf examples/candidate --num-prompts 20 \
  --output experiment --output-dir results/candidates --iteration candidate-a
```

示例为每个候选动态创建 PVC，无需逐个挂载 worktree 的宿主机目录；复用已有模型目录的方式见[模型存储](model-storage_zh.md)。

其他候选沿用同一流程，分别使用不同的 worktree、分支、namespace 和 iteration 名称。八个这样的部署共请求 16 张 GPU：每个候选只有一个单节点模型副本，请求两张 GPU，并单独将张量并行度设为 2。集群还需有足够的 CPU、内存及平台资源。需要限定节点时，在模型配置中添加 `spec.nodeSelector`；它选择节点，不指定 GPU 编号。需要独立物理设备时，应使用独占 GPU 资源，而不是时间切片的逻辑副本。

测量结果和输出目录保留在各自 worktree 中，对照方法见[实验记录手册](../rsi-playbooks/experiment-records_zh.md)。共享 CPU、存储和网络的活动仍可能影响测量。GPU 全部占用时，更新可能先停止旧候选，待设备释放后启动替代版本。

候选结束后，只删除自己的部署：

```bash
foretoken delete examples/candidate
```

所有候选结束后，再统一卸载平台。

## 修改推理引擎

修改 vLLM 时，关联与运行时 Python、PyTorch 和设备环境匹配的 Git 源码目录。假设源码位于 `../vllm`：

```bash
foretoken deploy examples/quickstart --engine-source ../vllm --timeout 20m
```

引擎选择按当前 worktree 记录，其他 worktree 不继承这些目录；需要修改引擎时，为各自候选明确选择源码目录。修改 Python、Triton 或 NVIDIA CUDA/C++ 源码后，重新执行 `foretoken deploy`，所需编译会自动完成。镜像仓库和平台设置沿用共享安装。

沐曦原生 kernel 由插件源码提供。将插件与匹配的 core 源码一起关联：

```bash
foretoken deploy examples/quickstart \
  --engine-source ../vllm \
  --engine-source vllm-metax=../vllm-metax --timeout 20m
```

### 更换运行环境

普通部署不需要修改基础镜像。默认镜像包含运行模型服务所需的 Python、PyTorch、CUDA 和 vLLM。

如果需要使用自定义环境，修改 [`deploy/inference-engines/vllm/source-environment.json`](../deploy/inference-engines/vllm/source-environment.json) 中的 `baseImage`：

```json
{"baseImage": "ghcr.io/example/custom-vllm:latest"}
```

源码安装、`make image-model-server`、`deploy/dev-build` 和发布构建都会使用这个设置。镜像必须与 Foretoken 的 vLLM 适配器兼容，并且构建器可以访问。已有源码安装修改后，重新执行 `foretoken deploy`。

只为某次安装指定不同基础镜像时，在 `deploy/platform-values.yaml` 中设置 `runtime.vllm.image`：

```yaml
runtime:
  vllm:
    image: ghcr.io/example/custom-vllm:latest
```

重新执行安装命令，传入 `--values deploy/platform-values.yaml`，并保留镜像仓库和引擎源码选项。使用 `-e` 时，Foretoken 以此镜像为构建基础；将该字段设为 `auto` 可恢复自动选择。安装完成后重新部署工作负载。

沐曦基础镜像构建见[准备沐曦 Foretoken 平台](development/metax-platform_zh.md#从源码安装)。

### vLLM-Omni 运行时

vLLM-Omni 使用独立的模型服务镜像。在具备 Docker BuildKit、Make 和 rustup 管理的 Rust 工具链的机器上，从仓库根目录构建：

```bash
make image-vllm-omni VLLM_OMNI_IMAGE=foretoken-vllm-omni:latest
make image-model-server-omni \
  INFERENCE_ENGINE_IMAGE=foretoken-vllm-omni:latest \
  OMNI_MODEL_SERVER_IMAGE=foretoken-omni-model-server:latest
```

使用 k3d 时，将 `CLUSTER` 设为已有集群的名称，再导入镜像：

```bash
CLUSTER=foretoken-qwen-test
k3d image import --cluster "$CLUSTER" foretoken-omni-model-server:latest
```

远程集群沿用 [Kubernetes 部署指南](kubernetes-deployment_zh.md) 中的 `REGISTRY` 设置；仓库需要认证时，先完成登录，再推送模型服务镜像：

```bash
docker tag foretoken-omni-model-server:latest "$REGISTRY/omni-model-server:latest"
docker push "$REGISTRY/omni-model-server:latest"
```

在 `deploy/platform-values.yaml` 中将 `runtime.vllmOmni.image` 设为节点可拉取的镜像。以下使用本地镜像名；通过仓库分发时，改为推送后的完整地址：

```yaml
runtime:
  vllmOmni:
    image: foretoken-omni-model-server:latest
```

应用运行时设置：

```bash
foretoken install -e . --values deploy/platform-values.yaml
```

远程平台构建保留 `--registry "$REGISTRY"`，以及原有的其他安装选项。前面的 vLLM editable 源码更新针对标准 vLLM 后端。

安装完成后，用 `foretoken deploy` 部署 Omni 服务的 Kustomize 目录。修改代码后，重新构建并分发 Omni 镜像，将 `runtime.vllmOmni.image` 改为新的 tag 或 digest 引用，再执行安装命令并重新部署同一 Kustomize 目录。
