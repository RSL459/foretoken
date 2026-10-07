<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Deploy a quantized model

English | [简体中文](README_zh.md)

Serve Qwen2.5-0.5B-Instruct using a prequantized AWQ checkpoint or 4-bit BitsAndBytes quantization during loading. Each deployment requests one NVIDIA GPU, 3 CPU cores, and 9 GiB of host memory, plus platform capacity. The vLLM image and GPU must support the selected quantization method.

## Deploy and request AWQ

Use a [source-installed platform](../../docs/custom-deployment.md) and run from the repository root:

```bash
foretoken deploy examples/quantized-model/awq --timeout 20m
FRONTEND_URL="$(foretoken endpoint examples/quantized-model/awq)"
curl --fail-with-body "$FRONTEND_URL/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"Qwen/Qwen2.5-0.5B-Instruct-AWQ","messages":[{"role":"user","content":"Hello"}],"max_tokens":32}'
printf '\n'
```

AWQ uses FP16 activations. Cache files use the repository-root `data/` on local k3d and a dynamic PVC on other clusters; see [model storage](../../docs/model-storage.md). For hostname-based access, follow [Gateway mode](../../cli/README.md#gateway-mode).

## Use BitsAndBytes instead

```bash
foretoken deploy examples/quantized-model/bitsandbytes --timeout 20m
```

Resolve this directory's frontend with `foretoken endpoint` and use `Qwen/Qwen2.5-0.5B-Instruct` in the request. This deployment applies 4-bit quantization while loading and uses BF16 computation; it does not create a new checkpoint. The AWQ and BitsAndBytes deployments have separate namespaces and can run independently.

## Compare with BF16

Compare BitsAndBytes against the same model's unquantized BF16 reference:

```bash
foretoken eval examples/quantized-model/bitsandbytes \
  --reference examples/quantized-model/bf16 --output local,plot
```

For bit-width plots that also include BF16 self-comparison, replace the candidate directory with `--candidates examples/quantized-model/candidates.jsonl`. Comparing AWQ against BF16 also includes the activation-precision difference.

Metrics, custom candidates, and resuming runs are covered by [model distribution comparison](../../benchmarks/docs/eval/distribution-comparison.md).

## Clean up

Delete the examples you deployed:

```bash
foretoken delete examples/quantized-model/awq
foretoken delete examples/quantized-model/bitsandbytes
```

Directory-backed model files remain for reuse.
