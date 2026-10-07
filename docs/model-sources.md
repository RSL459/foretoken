<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Model sources

[中文](model-sources_zh.md)

A `ModelService` downloads its model from Hugging Face Hub by default:

```yaml
spec:
  model: Qwen/Qwen3-0.6B
```

To download from ModelScope, add `source: modelscope` and use the model's ModelScope identifier. Each model service can choose its own source. After editing `model.yaml`, deploy the example:

```bash
foretoken deploy examples/quickstart --timeout 20m
```

Use the configured `model` value in API requests.

## Use a local model directory

Place a complete checkpoint, including its tokenizer and configuration, below the [model storage](model-storage.md) root:

```text
data/models/checkpointA/A3/
```

Set these fields in `model.yaml`:

```yaml
spec:
  model: checkpointA/A3
  source: local
```

The public model name remains `checkpointA/A3`. An absolute directory mounted in both frontend and model Pods is also supported. The directory must contain all files needed by the engine.

## Use a Hugging Face-compatible endpoint

Set the download URL in platform values, such as `deploy/platform-values.yaml`:

```yaml
runtime:
  vllm:
    modelSource:
      endpoint: https://your-huggingface-compatible-mirror.example
```

Replace the example URL, then reapply your installation command with `--values deploy/platform-values.yaml` and redeploy the model services. Keep other runtime settings in the same file. This endpoint applies to Hugging Face downloads, not ModelScope or local models.

For authenticated Hugging Face access, create a Secret containing the token in each workload namespace and set `runtime.vllm.modelSource.tokenSecret` to `{name: hf-token, key: token}`, using your Secret name and key.
