<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# 单模型快速开始

[English](README.md) | [中文](README_zh.md)

通过 OpenAI 兼容前端调用 `Qwen/Qwen3-0.6B`。示例包含两个前端副本，合计申请 1 张 GPU、8 核 CPU 和 52 GiB 内存；还需为平台预留资源。

## 部署并调用

按仓库[快速开始](../../README_zh.md#快速开始)安装 Foretoken，再从仓库根目录运行：

```bash
foretoken deploy examples/quickstart --timeout 20m
FRONTEND_URL="$(foretoken endpoint examples/quickstart)"
curl --fail-with-body "$FRONTEND_URL/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"Qwen/Qwen3-0.6B","messages":[{"role":"user","content":"请回复：Foretoken 已就绪"}],"max_tokens":32,"temperature":0}'
printf '\n'
```

Gateway 部署还需填写请求 Host，配置方式见[网关模式](../../cli/README_zh.md#网关模式)。

## 更换模型或调整容量

在 [`model.yaml`](model.yaml) 中修改模型、副本数、资源和[引擎参数](../../docs/inference-parameters_zh.md)，在 [`frontend.yaml`](frontend.yaml) 中调整前端副本数。配置修改后重新部署同一目录。

[`cache.yaml`](cache.yaml) 在本地 k3d 使用仓库根目录的 `data/`，其他集群使用动态存储。已有目录或自定义 StorageClass 的设置见[模型存储](../../docs/model-storage_zh.md)。

运行两个模型并按队列自动扩缩容时，使用[多模型示例](../multi-model-quickstart/README_zh.md)；AWQ 和加载时量化的用法见[量化模型](../quantized-model/README_zh.md)。

## 清理

```bash
foretoken delete examples/quickstart
```

命令会删除示例命名空间及其中的服务和 PVC；目录中的模型文件保留供复用。
