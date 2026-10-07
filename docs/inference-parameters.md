<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Inference parameters

English | [简体中文](inference-parameters_zh.md)

Set engine options in `ModelService.spec.engineArgs`. Use the engine's native names without `--`, and redeploy after editing `model.yaml`:

```yaml
spec:
  model: Qwen/Qwen2.5-0.5B-Instruct-AWQ
  backend: vllm
  engineArgs:
    quantization: awq
    dtype: half
    max-model-len: 8192
    tensor-parallel-size: 1
    gpu-memory-utilization: 0.85
```

Values can be YAML booleans, numbers, strings, lists, or objects. Omitted options keep engine defaults; `null` omits an option. Supported values depend on the engine image, model, and hardware. A Pool's `engineArgs` replaces, rather than merges with, the service-level dictionary.

## Choose engine settings

`max-model-len` limits the combined input and output token count. `gpu-memory-utilization` sets the fraction of device memory available to each engine instance. Weight quantization and `kv-cache-dtype` control different storage: model weights and attention KV cache, respectively.

For scheduler, precision, graph capture, and other native options, use the [vLLM argument reference](https://docs.vllm.ai/en/latest/configuration/engine_args/). Foretoken supplies model identity, serving endpoints, transfer connectors, and profiling settings. vLLM-Omni deployments use the [separate runtime](custom-deployment.md#vllm-omni-runtime) and that engine's options.

## Match parallelism to GPU resources

For vLLM, the GPU count per model replica must satisfy:

```text
nodes × resources.requests.gpu.count = TP × PP × DP × PCP
```

`nodes` is the number of Kubernetes nodes per replica; GPU requests apply to each member Pod. Native options select tensor parallelism (`tensor-parallel-size`, TP), pipeline parallelism (`pipeline-parallel-size`, PP), data parallelism (`data-parallel-size`, DP), and prefill context parallelism (`prefill-context-parallel-size`, PCP). Decode context parallelism (`decode-context-parallel-size`, DCP) reuses existing ranks and does not add GPUs. The service's `replicas` count is separate from engine DP.

Use `enable-expert-parallel`, `all2all-backend`, and `enable-eplb` for expert parallelism. Cross-node replicas require suitable communication devices and cache storage accessible from every member; installation prepares LeaderWorkerSet and RDMA allocation.

Each P/D or E/P/D Pool can select its own supported parallelism. PCP/DCP support depends on the attention backend. With the [E/P/D runtime](../examples/encoder-prefill-decode/README.md), Prefill and Decode need matching PCP/DCP cache layouts, and their TP sizes must divide one another.

## Enable speculative decoding

Keep the complete native dictionary together:

```yaml
spec:
  engineArgs:
    speculative-config:
      method: ngram
      num_speculative_tokens: 2
      prompt_lookup_max: 4
```

Methods and child fields follow vLLM. For a method that needs draft weights, its `model` accepts a Hub identifier or a container-visible absolute directory. `spec.source: modelscope` applies to both target and draft Hub identifiers.

## Tools, reasoning, and structured output

For forced tool selection or strict tool arguments, the model must support the required structured-output format. When it supports structural tags, add this capability to its ModelService configuration:

```yaml
spec:
  features:
    structuredOutputs: [structuralTag]
```

With `spec.modelPools`, declare `features.structuredOutputs` in each applicable Pool rather than at service level. Preserve any other formats already declared.

Output token budgets include reasoning. Messages requires `max_tokens` and does not accept a separate `thinking.budget_tokens`; thinking controls depend on the model's chat template. When the budget is exhausted, Messages reports `max_tokens` and Responses reports `incomplete`. Clients should execute only complete tool calls.

## Select serving nodes

Replace `NODE_NAME` with a node's actual name, then label it:

```bash
kubectl label node NODE_NAME workload-group=group-a --overwrite
kubectl get nodes -L workload-group
```

Apply the same label to every node in the group. Select it in the model YAML:

```yaml
spec:
  nodeSelector:
    workload-group: group-a
```

The service selector places its default Pool on those nodes. Use `modelPools[].nodeSelector` to choose nodes separately for a Pool.
