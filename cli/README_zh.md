<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Foretoken 命令行工具

[English](README.md) | 简体中文

使用 `foretoken` 安装平台、部署模型服务、查看状态和运行评测。

## 安装

准备 Python 3.11+、kubectl、Helm 和可用的 Kubernetes context。GPU 节点需要厂商驱动和设备插件。需要先创建本地集群时，参阅 [k3d](../docs/k3d-deployment_zh.md) 或 [kind](../docs/kind-deployment_zh.md) 指南。

```bash
pip install foretoken
foretoken --version
foretoken install
```

命令安装已发布的平台，并配置监控和持久日志。开发时改为在源码根目录运行 `pip install -e .` 和 `foretoken install -e .`；镜像仓库与引擎设置见[源码部署](../docs/custom-deployment_zh.md)。

## 部署和管理模型服务

按[快速开始](../README_zh.md#安装并部署)获取示例，再从仓库根目录执行：

```bash
foretoken deploy examples/quickstart --timeout 20m
foretoken endpoint examples/quickstart
```

`deploy` 应用配置并等待服务就绪，同时显示进度和日志。重新部署也会将已有服务更新到当前平台提供的版本；仅更新平台时，已有服务保留原版本。

查看部署状态，或持续观察一个命名空间中的全部服务：

```bash
foretoken status examples/quickstart
foretoken status -n foretoken-demo --watch
```

按 Ctrl+C 停止观察。部署多个模型见[多模型示例](../examples/multi-model-quickstart/README_zh.md)。

## 网关模式

需要通过共享网关和域名访问服务时，执行：

```bash
foretoken install --frontend-mode gateway
```

源码安装保留 `-e .` 以及原镜像仓库和引擎选项。复用已有 Gateway 时，添加 `--gateway-name inference-gateway --gateway-namespace gateway-system`；需要指定监听器时使用 `--gateway-section-name`。

为服务选择域名，并添加到 `examples/quickstart/frontend.yaml`：

```yaml
spec:
  hostname: foretoken.example.com
```

重新部署，获取网关地址和请求域名，再发送请求：

```bash
foretoken deploy examples/quickstart --timeout 20m
FORETOKEN_FRONTEND_URL="$(foretoken endpoint examples/quickstart)"
FORETOKEN_REQUEST_HOST="$(foretoken endpoint examples/quickstart --host)"

curl --fail-with-body "$FORETOKEN_FRONTEND_URL/v1/chat/completions" \
  -H "Host: $FORETOKEN_REQUEST_HOST" \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen/Qwen3-0.6B","messages":[{"role":"user","content":"你好"}]}'
```

## 自定义安装

通过 `foretoken install --values PATH` 覆盖平台设置，具体配置按任务查阅：

| 任务 | 指南 |
| --- | --- |
| 配置镜像仓库访问、服务 IP 或共享集群环境 | [Kubernetes 部署](../docs/kubernetes-deployment_zh.md) |
| 从 Foretoken 或引擎源码构建 | [源码部署](../docs/custom-deployment_zh.md) |
| 使用沐曦硬件 | [沐曦部署](../docs/metax-deployment_zh.md) |
| 配置模型存储、Dragonfly 或 ModelExpress | [模型存储](../docs/model-storage_zh.md) |
| 配置 Grafana、日志或告警 | [可观测性](../observability/README_zh.md) |

完整安装选项见 `foretoken install --help`。

## 评测与性能剖析

| 任务 | 命令 | 指南 |
| --- | --- | --- |
| 测量延迟和吞吐量 | `foretoken perf` | [性能评测](../benchmarks/docs/perf/README_zh.md) |
| 评估回答质量 | `foretoken eval` | [质量评测](../benchmarks/docs/eval/README_zh.md) |
| 重绘已保存的结果 | `foretoken plot RESULT_DIR` | [图表与对比](../benchmarks/docs/perf/sweep_zh.md) |
| 采集 CPU/GPU 执行过程 | `foretoken perf --profile` | [性能剖析](../benchmarks/docs/profile/README_zh.md) |

各指南提供完整示例，`foretoken COMMAND --help` 列出相应选项。

## 清理

```bash
foretoken delete examples/quickstart
foretoken uninstall
```

卸载保留 CRD、日志存储和复用的集群组件。由 CLI 创建的本地集群可通过 `foretoken cluster delete k3d --name foretoken-dev` 删除；kind 集群使用对应的 `kind` 命令。
