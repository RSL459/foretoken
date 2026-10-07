<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# 模型来源

[English](model-sources.md)

`ModelService` 默认从 Hugging Face Hub 下载模型：

```yaml
spec:
  model: Qwen/Qwen3-0.6B
```

如需从 ModelScope 下载，添加 `source: modelscope`，并填写模型在 ModelScope 上的标识。各模型服务可以独立选择来源。修改 `model.yaml` 后部署示例：

```bash
foretoken deploy examples/quickstart --timeout 20m
```

API 请求中的 `model` 使用配置中的同一标识。

## 使用本地模型目录

将完整 checkpoint 连同 tokenizer 和配置文件放到[模型存储](model-storage_zh.md)根目录下：

```text
data/models/checkpointA/A3/
```

在 `model.yaml` 中设置：

```yaml
spec:
  model: checkpointA/A3
  source: local
```

对外模型名称仍为 `checkpointA/A3`。也可使用前端和模型 Pod 中都已挂载的绝对目录；目录需包含引擎加载所需的全部文件。

## 使用 Hugging Face 兼容下载地址

在平台 values 文件中设置下载地址，例如 `deploy/platform-values.yaml`：

```yaml
runtime:
  vllm:
    modelSource:
      endpoint: https://your-huggingface-compatible-mirror.example
```

替换示例地址后，在原安装命令中传入 `--values deploy/platform-values.yaml`，再重新部署模型服务。同一文件中保留其他运行时设置。此地址用于 Hugging Face 下载，不影响 ModelScope 和本地模型。

需要 Hugging Face 认证时，在各工作负载命名空间创建保存 token 的 Secret，并将 `runtime.vllm.modelSource.tokenSecret` 设为 `{name: hf-token, key: token}`，名称和 key 按实际 Secret 填写。
