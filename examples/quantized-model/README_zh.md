<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# 部署量化模型

[English](README.md) | 简体中文

通过预量化 AWQ checkpoint，或加载时进行 BitsAndBytes 4-bit 量化，运行 Qwen2.5-0.5B-Instruct。每套部署申请 1 张 NVIDIA GPU、3 核 CPU 和 9 GiB 主机内存，另外需要为平台预留资源。vLLM 镜像和 GPU 需支持所选量化方式。

## 部署并调用 AWQ

使用[从源码安装的平台](../../docs/custom-deployment_zh.md)，从仓库根目录运行：

```bash
foretoken deploy examples/quantized-model/awq --timeout 20m
FRONTEND_URL="$(foretoken endpoint examples/quantized-model/awq)"
curl --fail-with-body "$FRONTEND_URL/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"Qwen/Qwen2.5-0.5B-Instruct-AWQ","messages":[{"role":"user","content":"你好"}],"max_tokens":32}'
printf '\n'
```

AWQ 使用 FP16 激活值。本地 k3d 将缓存保存在仓库根目录 `data/`，其他集群使用动态 PVC；配置见[模型存储](../../docs/model-storage_zh.md)。通过域名访问的设置见[网关模式](../../cli/README_zh.md#网关模式)。

## 改用 BitsAndBytes

```bash
foretoken deploy examples/quantized-model/bitsandbytes --timeout 20m
```

通过 `foretoken endpoint` 获取此目录对应的前端地址，请求中使用 `Qwen/Qwen2.5-0.5B-Instruct`。该部署在加载时进行 4-bit 量化，使用 BF16 计算，不生成新的 checkpoint。AWQ 与 BitsAndBytes 使用独立命名空间，可以分别运行。

## 与 BF16 比较

将 BitsAndBytes 与相同模型的非量化 BF16 参考部署比较：

```bash
foretoken eval examples/quantized-model/bitsandbytes \
  --reference examples/quantized-model/bf16 --output local,plot
```

位宽图需同时包含 BF16 自身的对照结果时，将候选目录换成 `--candidates examples/quantized-model/candidates.jsonl`。AWQ 与 BF16 比较时也包含激活值精度差异。

指标、自定义候选和恢复运行的用法见[模型概率分布对比](../../benchmarks/docs/eval/distribution-comparison_zh.md)。

## 清理

删除实际部署过的示例：

```bash
foretoken delete examples/quantized-model/awq
foretoken delete examples/quantized-model/bitsandbytes
```

目录中的模型文件保留供复用。
