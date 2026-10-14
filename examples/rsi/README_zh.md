<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# RSI 起始部署

[English](README.md) | 简体中文

这些配置是[RSI 任务](../../rsi-playbooks/tasks/README_zh.md)可继续修改的探索起点。[Qwen 示例](qwen-decode/)使用 BF16，在单节点的四张 GPU 上通过张量并行部署 `Qwen/Qwen3.5-35B-A3B`。起始配置不开启推测解码，后续可在任务资源预算内探索其他方案。

## 部署 Qwen

准备好[沐曦 Foretoken 平台](../../docs/development/metax-platform_zh.md)，运行环境需支持该模型，前端采用 Gateway 访问，并提供支持 `ReadWriteOnce` 的默认 StorageClass。示例创建独立 namespace 和 128 GiB 运行缓存卷，需要时从 Hugging Face 下载模型。复用已有模型目录的方式见[模型存储](../../docs/model-storage_zh.md)。

在仓库根目录执行：

```bash
foretoken deploy examples/rsi/qwen-decode --timeout 60m
foretoken status examples/rsi/qwen-decode
```

模型与 frontend 服务均为 Ready 时，部署已就绪。初始资源分配如下：

| 工作负载 | CPU 请求 / 上限 | 内存请求 / 上限 | GPU |
| --- | --- | --- | --- |
| 模型，单副本 | 16 / 30 | 256 / 508 GiB | 4 |
| Frontend，单副本 | 1 / 2 | 2 / 4 GiB | 0 |
| 合计 | 17 / 32 | 258 / 512 GiB | 4 |

请求量为平台、构建和评测客户端留出调度空间。这些数值是起始分配，不是实测最优值，可在任务总预算内调整。[model.yaml](qwen-decode/model.yaml)设置了 131072 token 上下文上限和最多 16 个序列；所选负载连同生成输出需在上下文范围内。

## 发送请求

CLI 获取 Gateway 地址，HTTP Host 用来选择这个候选，因此以下命令不要求为示例 hostname 配置 DNS。

```bash
FRONTEND_URL="$(foretoken endpoint examples/rsi/qwen-decode)"
REQUEST_HOST="$(foretoken endpoint examples/rsi/qwen-decode --host)"

curl --fail-with-body --no-buffer "$FRONTEND_URL/v1/chat/completions" \
  -H "Host: $REQUEST_HOST" \
  -H 'Content-Type: application/json' \
  -d '{"model":"Qwen/Qwen3.5-35B-A3B","messages":[{"role":"user","content":"简要解释张量并行。"}],"max_tokens":128,"stream":true}'
```

性能对照使用 [Qwen 任务中的评测命令](../../rsi-playbooks/tasks/qwen-decode_zh.md#评测命令)。`foretoken perf` 会从部署配置中解析 Gateway Host。

## 并行独立候选

为每个候选准备独立的 [worktree 和部署](../../docs/custom-deployment_zh.md#并行运行候选方案)。各自复制本示例，在 `namespace.yaml` 和 `kustomization.yaml` 中设置唯一 namespace，在 `frontend.yaml` 中设置唯一 `spec.hostname`。每个 namespace 有自己的运行缓存 PVC；复用模型文件时，也要保持可写缓存独立。

Qwen 任务提供两台八卡节点，可通过 `ModelService.spec.nodeSelector` 在需要时明确指定节点，每节点安排两组四卡候选。四组已经占满 16 张 GPU；要增加实验数量，应把部分完整服务配额换成单卡算子验证等小实验，并核算 CPU、内存、存储和竞争负载。调大同一 ModelService 的 `replicas` 得到的是服务副本，不是独立实验。

## 清理

保存结果、确认候选不再使用后，删除该候选自己的配置：

```bash
foretoken delete examples/rsi/qwen-decode
```

这会删除示例 namespace 和缓存 PVC，卷数据按 StorageClass 的回收策略处理。其他候选仍在使用时保留共享平台。
