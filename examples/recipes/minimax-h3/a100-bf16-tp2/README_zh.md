<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# 双 NVIDIA A100 上的 MiniMax H3 BF16

[English](README.md) | 简体中文

在两张 A100 80 GB 上，以原生 BF16、TP=2 部署 MiniMax H3。
视频请求通过 Foretoken 标准前端进入；Omni adapter 负责内部引擎执行和生命周期。

同一份配方用于 FL2VA 或 Ref2VA，在部署前选择分区。

## 构建和安装

按照 [k3d 指南](../../../../docs/k3d-deployment_zh.md) 准备可用的 Foretoken 集群。
节点至少需要 256 GiB 主机内存，并为所选分区的权重预留足够的缓存空间。
在 Foretoken 仓库根目录执行：

```bash
make image-vllm-omni VLLM_OMNI_IMAGE=foretoken-vllm-omni:h3
make image-model-server-omni \
  INFERENCE_ENGINE_IMAGE=foretoken-vllm-omni:h3 \
  OMNI_MODEL_SERVER_IMAGE=foretoken-omni-model-server:h3
```

引擎构建固定使用公开 vLLM-Omni 提交
`ad025defe68a46bdc3590c53161889aa6932ff4c` 和 `vllm/vllm-openai:v0.30.0`。
源码和依赖在镜像内安装，不复制主机 checkout 或 Conda 环境，也不依赖未发布的 H3 补丁。
需要固定基础镜像身份时，可用 `VLLM_OMNI_BASE_IMAGE` 指定不可变 digest。

k3d 用户将镜像导入自己的集群（`CLUSTER` 来自 k3d 指南）：

```bash
k3d image import --cluster "$CLUSTER" foretoken-omni-model-server:h3
```

其他集群将 Omni 镜像推送到节点可访问的镜像仓库。
在 `platform-values.yaml` 中使用现有平台配置选择它：

```yaml
runtime:
  vllmOmni:
    image: foretoken-omni-model-server:h3
```

```bash
foretoken install -e . --values platform-values.yaml
```

平台镜像由标准源码安装命令构建并分发。远程集群按
[源码部署指南](../../../../docs/custom-deployment_zh.md) 添加 `--registry`。

## 部署和请求

默认模型源是公开 Hugging Face 仓库 `MiniMaxAI/MiniMax-H3`。
通过 `model.yaml` 中的 `spec.engineArgs.task-type` 选择 `fl2va`（默认）或 `ref2va`，
由上游 loader 解析对应分区。两个分区使用同一个仓库 ID。
Foretoken 提供配置的模型缓存，首次启动时自动下载权重。登录是可选项，不是前置条件。

按 [模型存储](../../../../docs/model-storage_zh.md) 将 `cache.yaml` 设置为 GPU 节点
可访问的数据目录。RuntimeCache 指向缓存根目录，不是模型分区目录。

### FL2VA（默认）

准备本地参考 PNG，将 `REFERENCE_IMAGE` 设置为它的路径：

```bash
RECIPE=examples/recipes/minimax-h3/a100-bf16-tp2
REFERENCE_IMAGE=/path/to/reference.png
foretoken deploy "$RECIPE" --timeout 1h
ENDPOINT="$(foretoken endpoint "$RECIPE" --timeout 10m)"
curl --fail-with-body --max-time 4000 \
  -X POST "${ENDPOINT%/}/v1/videos/sync" \
  -F model=MiniMaxAI/MiniMax-H3 \
  -F 'prompt=A cinematic tracking shot of a sailboat crossing a calm bay at sunrise.' \
  -F "input_reference=@${REFERENCE_IMAGE};type=image/png" \
  -F width=1024 -F height=576 -F num_frames=124 -F fps=24 \
  -F num_inference_steps=50 -F aspect_ratio=16:9 -F flow_shift=12 -F seed=1 \
  -F 'extra_params={"task":"fl2va","audio_flow_shift":3}' \
  --output h3-fl2va.mp4
```

recipe 包含 `FrontendService`，端点发现复用标准 LoadBalancer/Gateway 接入方式，
不直接暴露内部 ModelGroup Service。控制器根据申请的两张 GPU 推导 TP=2。

前端和 Omni 同步请求预算均为 4000 秒。构建 adapter 镜像时，
`OMNI_VIDEO_SYNC_TIMEOUT` 同时设置 Omni 的 HTTP 超时和完整生成请求的 worker RPC 预算；
`timeouts.drain` 是独立的 Pod 关闭排空预算。

### 参考视频生成

使用 Ref2VA 时，将 `model.yaml` 中的 `spec.engineArgs.task-type` 改为 `ref2va`，
再部署同一份配方。只有两张可用 GPU 时，先删除已有部署以释放 GPU；
切换前先等待正在生成的请求完成；已有权重仍保留在缓存中。
准备一个本地参考 MP4，将 `REFERENCE_VIDEO` 设置为它的路径：

```bash
RECIPE=examples/recipes/minimax-h3/a100-bf16-tp2
REFERENCE_VIDEO=/path/to/reference.mp4
foretoken delete "$RECIPE" --timeout 2h
foretoken deploy "$RECIPE" --timeout 1h
ENDPOINT="$(foretoken endpoint "$RECIPE" --timeout 10m)"
curl --fail-with-body --max-time 4000 \
  -X POST "${ENDPOINT%/}/v1/videos/sync" \
  -F model=MiniMaxAI/MiniMax-H3 \
  -F 'prompt=Continue the scene shown in the reference video with a smooth camera movement.' \
  -F "input_references=@${REFERENCE_VIDEO};type=video/mp4" \
  -F width=1024 -F height=576 -F num_frames=124 -F fps=24 \
  -F num_inference_steps=50 -F aspect_ratio=16:9 -F flow_shift=12 -F seed=1 \
  -F 'extra_params={"task":"ref2va","audio_flow_shift":3}' \
  --output h3-ref2va.mp4
```

请求中的任务必须与部署分区一致。参考媒体处理由 vLLM-Omni 完成，
Foretoken 通过标准路由转发原始 multipart 输入。
切回 FL2VA 时，先删除部署，将 `task-type` 改回 `fl2va` 并重新部署，再使用上面的 FL2VA 请求。

两个分区均已在双 A100 80 GB 上通过标准前端完成真实生成：原生 BF16、TP=2、
50 步去噪、1024x576、124 帧、24 FPS。返回的视频通过完整解码和抽帧画面检查。
生成测试复用原始 HF 权重缓存；HF、ModelScope 和 HF 兼容镜像站的下载检查
覆盖配置文件，不包含重新下载全部权重。

## 其他模型源

ModelScope 的 H3 仓库名称与 HF 不同。使用时修改 `model.yaml` 中的以下字段，
请求的 `model` 字段也改为 `MiniMax/MiniMax-H3`：

```yaml
spec:
  model: MiniMax/MiniMax-H3
  source: modelscope
```

保留所选的 `task-type`。镜像包含 ModelScope SDK，上游 loader 将对应分区的文件
下载到同一个已配置的 RuntimeCache。下面的 Hugging Face 镜像站设置不适用于 ModelScope。

使用 Hugging Face 兼容镜像站时，配置现有平台选项：

```yaml
runtime:
  vllm:
    modelSource:
      endpoint: https://your-huggingface-compatible-mirror.example
```

控制器只将此端点投影到 Hugging Face 工作负载。镜像站须提供对应仓库和 revision；
下载失败时 Foretoken 不会自动切换来源。

离线或已下载权重可选用 `source: local`，将 `model` 设置为挂载的 checkpoint 根目录
或所选分区目录，具体见 [模型源](../../../../docs/model-sources_zh.md)。
multipart `model` 字段使用同一个模型标识。
如需认证以使用登录用户的下载配额，复用平台 Secret 配置，不将凭据写入镜像。

```bash
foretoken delete "$RECIPE" --timeout 2h
```

删除部署后保留配置的模型缓存。
