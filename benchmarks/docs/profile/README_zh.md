<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 性能剖析

[English](README.md) | 简体中文 · [评测与性能剖析](../../README_zh.md)

采集一段 CPU/GPU 执行时间线，定位瓶颈。采集需要[源码安装的 CLI 和平台](../../../docs/custom-deployment_zh.md)，快速开始示例已配置持久存储。

## 同时运行 benchmark 和采集

从仓库根目录运行：

```bash
foretoken perf examples/quickstart \
  --profile --profile-engine pytorch --profile-duration 15s \
  --num-prompts 2 --max-tokens 128 --output local
```

该命令在 NVIDIA 或[沐曦 GPU](../../../docs/metax-deployment_zh.md) 上记录最多 15 秒的 PyTorch 执行，负载提前结束时停止采集。用 Foretoken Kustomize 目录选择服务，多模型部署加上 `--model`。采集会增加开销，延迟和吞吐量比较应另开一轮不带 `--profile` 的评测。

生成式请求、轨迹回放、多轮对话、混合数据集、SLO 探测和 HTTP 扫描都可同时采集。扫描中的每次重复在自己的结果目录保存 `profile.json`。

## 查看结果

在运行浏览器的电脑上，使用目标集群的 kubeconfig：

```bash
foretoken profile view
```

打开打印的网址并选择采集记录。PyTorch trace 在 Perfetto 中打开，浏览器需能访问 `ui.perfetto.dev`。Nsight 时间线通过“Open in NVIDIA Nsight Systems”在 NVIDIA 官方查看器中打开；兼容 Perfetto 的 mcTracer JSON 也在 Perfetto 中查看。

按 Ctrl+C 关闭查看器。采集文件可供以后查看和下载，临时评测部署清理后仍然保留。

## 部署并采集外部流量

```bash
foretoken deploy examples/quickstart \
  --profile --profile-engine pytorch --profile-duration 15s --timeout 20m
```

服务就绪后开始采集，在记录窗口内通过其他客户端发送流量。结束后服务继续运行，再次执行命令可采集下一段。

## 沐曦 mcTracer

model-server 镜像需要提供与 MACA SDK 匹配的 `mcTracer`（位于 `PATH`）和 `libmcpti.so`。在 ModelService YAML 的 `spec` 下添加：

```yaml
profiling:
  engine: mctracer
```

已有服务先用 `foretoken deploy` 应用设置，再执行评测或外部流量采集，参数改为 `--profile-engine mctracer`。CUDA Graph 可保持开启。YAML 选择模型启动时准备的工具，采集参数选择同一种工具；省略 YAML 设置时准备 PyTorch。

## Nsight Systems

Nsight Systems 在 NVIDIA GPU 上采集 CUDA 和 NVTX 活动，需要诊断镜像，以及选择 `spec.profiling.engine: nsight` 的部署。

### 准备诊断镜像

完成源码安装后，用本机构建的 model-server 镜像制作 Linux x86_64 镜像。将 `NSIGHT_IMAGE` 设为有推送权限且集群能拉取的 registry 地址：

```bash
docker build -f deploy/inference-engines/nsight/Dockerfile \
  --build-arg MODEL_SERVER_IMAGE=foretoken-dev-model-server \
  -t "$NSIGHT_IMAGE" deploy/inference-engines/nsight
docker push "$NSIGHT_IMAGE"
```

将以下内容保存为 `nsight-values.yaml`，用该地址替换 `YOUR_NSIGHT_IMAGE`：

```yaml
runtime:
  vllm:
    nsightImage: YOUR_NSIGHT_IMAGE
```

在此集群使用的源码安装命令后加上 `--values nsight-values.yaml`。只有选择 Nsight 的模型使用诊断镜像。

### 采集

[Nsight 示例](../../../examples/profile/nsight/README_zh.md)已选择工具和持久存储：

```bash
foretoken perf examples/profile/nsight \
  --profile --profile-engine nsight --profile-duration 15s \
  --num-prompts 2 --max-tokens 128 --output local
```

使用上面的查看器打开时间线。采集外部流量时，将 deploy 命令中的 `examples/quickstart` 换成 `examples/profile/nsight`，`pytorch` 换成 `nsight`。修改部署的 profiler 会替换模型进程，已有服务应先应用变更再采集。

## 清理

不再需要部署和采集记录时删除：

```bash
foretoken delete examples/quickstart
```

Nsight 示例使用 `examples/profile/nsight`。
