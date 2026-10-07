# Maintain GLM-5.3 support on MetaX

English | [简体中文](README_zh.md)

This bundle adapts GLM-5.3 to the MetaX source runtime. Platform source installation applies it automatically; see [MetaX platform setup](../../../../../../docs/development/metax-platform.md#install-from-source).

## Update the source pair

[`source-environment.json`](../../../source-environment.json) selects the vLLM core, MetaX plugin, and ordered patch targets. Update the source pair and patches together. Core and plugin patches run before wheel construction; the installed-package patch runs after dependency installation because it changes DeepGEMM.

Build the runtime from the repository root on a Docker BuildKit host:

```bash
make image-vllm-metax VLLM_METAX_IMAGE=foretoken-vllm-metax:latest
```

Use the resulting image as the inference runtime when building model-server; the [source deployment guide](../../../../../../docs/custom-deployment.md#select-a-different-runtime-environment) describes how to select it for a cluster.

## Check model execution

Exercise the affected model and checkpoint format on MetaX devices. For changes to quantized loading, verify the compressed-tensors projections and expert-parallel execution. For sparse attention or speculative decoding, include long prefills, decode, and the enabled draft method. The [GLM-5.3 upstream recipe](https://recipes.vllm.ai/zai-org/GLM-5.3-Flash) supplies model settings; the core retains automatic model-runner selection.

When changing mHC residual mixing, preserve the upstream FP32 arithmetic, intermediate BF16 rounding, configured Sinkhorn iterations, and single input normalization. Graph capture remains with the model runner. Related upstream work: [vLLM #56856](https://github.com/vllm-project/vllm/pull/56856).

The KDA recompute kernel uses eight warps and three stages. A two-stage launch can corrupt the W transform and produce non-finite recurrent state during long prefills, so changing this configuration requires a numerical check as well as timing.

For data-parallel draft changes, check both active and idle members. Runtime dummy batches omit dense DFlash/DSpark proposals, while target synchronization and draft execution during profiling, warmup, and graph capture remain active.
