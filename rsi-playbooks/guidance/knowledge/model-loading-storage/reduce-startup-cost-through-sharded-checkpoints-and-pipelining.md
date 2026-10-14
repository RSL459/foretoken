<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Reduce Startup Cost Through Sharded Checkpoints and Pipelining

English | [简体中文](reduce-startup-cost-through-sharded-checkpoints-and-pipelining_zh.md)

A downloaded model is not a ready model. Startup still resolves checkpoint files, allocates tensors, reads and installs weights, transforms them for the runtime, and prepares execution. Optimizing file reads cannot remove every later stage, and a cached checkpoint is not necessarily a cached runtime representation.

## Follow the loading stages

vLLM's cited [DefaultModelLoader](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/model_executor/model_loader/default_loader.py) prepares local or remote files, filters duplicates using index information, constructs weight iterators, applies model-specific `load_weights`, and checks parameter coverage where applicable. Model construction and post-load processing surround this path. The model's installation code owns fused parameter mapping, tensor-parallel slicing and quantization-specific transformations; a generic file reader does not.

For a checkpoint of size W, a sequential estimate is `T_read = W/B_storage`; startup additionally pays installation, H2D copies, transformation and runtime preparation. In a genuinely overlapped pipeline, steady-state chunk time approaches the slowest stage rather than their sum. Startup, final drain and model-dependent work remain. Measure whether chunks actually overlap before using this estimate.

Consider TP4 loading a globally stored 40 GiB checkpoint. Reading and slicing all weights on every rank may produce much more aggregate I/O than reading one roughly 10 GiB rank-local representation. This is only an illustrative balanced case: replicated tensors, expert assignment, padding and runtime quantization change the numbers. Skipping irrelevant tensor reads and converting once into a rank-local checkpoint address different costs.

[ServerlessLLM, January 2024](https://arxiv.org/html/2401.14351v1) describes a loading-optimized checkpoint with aligned GPU-specific binary tensor data and an offset index, plus chunked storage/host/GPU pipelines. The reusable idea is to move repeated interpretation and layout work out of the critical loading path, not to assume its reported startup times apply to another engine.

## What is already available

In the [cited implementations](README.md#references), vLLM's [ShardedStateLoader](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/model_executor/model_loader/sharded_state_loader.py) already reads rank-specific safetensors and copies directly into prepared parameters. Default filenames identify TP rank and, when PP is enabled, PP rank—not the parallel sizes. Alias/view filtering avoids duplicated storage. It does not perform arbitrary runtime quantization or resharding. A topology-specific checkpoint is unsuitable for a different topology unless an explicit conversion supports it.

The default loader also has local-expert filtering and specialized fastsafetensors/instanttensor paths. Filtering has conditions, including expert-load-balancing needs. vLLM additionally integrates [ModelExpress](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/model_executor/model_loader/modelexpress_loader.py). These are existing alternatives to a new custom loading subsystem.

Dynamo's [weight artifact code](https://github.com/ai-dynamo/dynamo/blob/7708f041a965e35374af976ab8ad610b9537e3bc/lib/gpu_memory_service/v1/snapshot/weight_artifact.py) saves allocation bytes, a different representation from named checkpoint tensors. Mooncake's current weight management supplies publication metadata but has pending reader integration. LMCache's KV cache does not eliminate weight installation. Distinguish each representation's consumer before claiming one cache replaces another.

## Experiments and remaining work

Locally compare standard checkpoint loading, supported tensor filtering and a topology-matched sharded checkpoint. Fix model revision, dtype, rank geometry and transformations. Instrument file resolution, bytes actually read per rank, CPU materialization, H2D, parameter installation and post-load time. Check logits and parameter coverage. A drop in I/O with unchanged startup identifies a later bottleneck; unchanged I/O with less installation time identifies avoided conversion.

Repeat cold filesystem, warm page-cache and repeated process-start cases. At service level, measure process launch to readiness and first successful generation, then the first several requests. Separate compilation/warmup from weight loading and retain peak host/device memory. Remaining research concerns reproducible runtime representations across real topology changes and avoiding repeated transformations.

[Model loading and storage](README.md)
