<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# 多模型快速开始

[English](README.md) | [中文](README_zh.md)

通过同一个前端调用两个模型：`Qwen/Qwen3-0.6B` 按队列负载在 1 到 3 个副本之间扩缩容，`unsloth/Llama-3.2-1B-Instruct` 固定运行 1 个副本。

初始部署申请 2 张 GPU、12 核 CPU 和 100 GiB 内存；满容量时，包含前端共申请 4 张 GPU、20 核 CPU 和 196 GiB 内存。还需为平台预留资源。

## 部署并调用

按仓库[快速开始](../../README_zh.md#快速开始)安装 Foretoken，再从仓库根目录运行：

```bash
foretoken deploy examples/multi-model-quickstart --timeout 20m
export FRONTEND_URL="$(foretoken endpoint examples/multi-model-quickstart)"
for MODEL in Qwen/Qwen3-0.6B unsloth/Llama-3.2-1B-Instruct; do
  curl --fail-with-body "$FRONTEND_URL/v1/chat/completions" \
    -H 'Content-Type: application/json' \
    -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"你好\"}],\"max_tokens\":32}"
  printf '\n'
done
```

请求的 `model` 字段决定调用哪个模型。示例与单模型快速开始共享模型存储，集群存储设置见[模型存储](../../docs/model-storage_zh.md)。Gateway 访问设置见[网关模式](../../cli/README_zh.md#网关模式)。

## 观察队列自动扩缩容

Qwen 每 5 秒评估一次负载，每次最多增减 1 个副本，缩容稳定窗口为 5 分钟。

另开一个终端观察容量：

```bash
kubectl get modelpool,modelgroup -n foretoken-multi-model-demo --watch
```

回到部署时使用的终端，发送 32 个请求，同时最多运行 8 个：

```bash
seq 1 32 | xargs -P8 -I{} sh -c '
  curl --fail --silent --show-error \
    "$FRONTEND_URL/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"Qwen/Qwen3-0.6B\",\"messages\":[{\"role\":\"user\",\"content\":\"详细解释 Kubernetes 请求路由。\"}],\"max_tokens\":512}"
'
```

GPU 容量和请求持续时间允许时，队列压力可触发扩容。查看建议与实际应用容量：

```bash
kubectl get modelservice multi-model-qwen3-0.6b \
  -n foretoken-multi-model-demo -o json | jq '.status.autoscaling'
```

队列目标、评估间隔和稳定窗口的设置见[自动扩缩容](../../docs/autoscaling_zh.md)。

## 清理

```bash
foretoken delete examples/multi-model-quickstart
```
