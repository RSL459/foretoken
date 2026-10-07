<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# 推理参数

[English](inference-parameters.md) | 简体中文

在 `ModelService.spec.engineArgs` 中设置引擎参数，使用原生名称，不写 `--`。修改 `model.yaml` 后重新部署：

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

值可以是 YAML 布尔值、数字、字符串、列表或对象。未填写的选项沿用引擎默认值，`null` 表示不传该选项。支持的取值取决于引擎镜像、模型和硬件。Pool 的 `engineArgs` 会整体替换服务级字典，而不是与其合并。

## 选择引擎设置

`max-model-len` 限制输入和输出合计的 token 数。`gpu-memory-utilization` 设置每个引擎实例可用的显存比例。权重量化和 `kv-cache-dtype` 分别控制模型权重与 attention KV Cache 的存储精度。

调度、计算精度、计算图捕获等原生选项见 [vLLM 参数文档](https://docs.vllm.ai/en/latest/configuration/engine_args/)。模型标识、服务端点、传输连接器和性能剖析设置由 Foretoken 提供。vLLM-Omni 部署使用[独立运行时](custom-deployment_zh.md#vllm-omni-运行时)及对应引擎的参数。

## 让并行度与 GPU 资源一致

vLLM 每个模型副本的 GPU 数量需满足：

```text
nodes × resources.requests.gpu.count = TP × PP × DP × PCP
```

`nodes` 是每个副本使用的 Kubernetes 节点数，GPU 请求作用于每个成员 Pod。原生参数分别设置张量并行（`tensor-parallel-size`，TP）、流水线并行（`pipeline-parallel-size`，PP）、数据并行（`data-parallel-size`，DP）和 Prefill 上下文并行（`prefill-context-parallel-size`，PCP）。Decode 上下文并行（`decode-context-parallel-size`，DCP）复用已有 rank，不增加 GPU 数。服务的 `replicas` 与引擎内部 DP 分别配置。

专家并行使用 `enable-expert-parallel`、`all2all-backend` 和 `enable-eplb`。跨节点副本需要合适的通信设备，以及所有成员都能访问的缓存存储；安装会准备 LeaderWorkerSet 和 RDMA 分配。

P/D 或 E/P/D 各 Pool 可以分别选择支持的并行方式。PCP/DCP 是否可用取决于 attention backend。使用 [E/P/D 运行时](../examples/encoder-prefill-decode/README_zh.md)时，Prefill 与 Decode 的 PCP/DCP 缓存布局需要匹配，TP 大小需互为整数倍。

## 启用推测解码

将完整的原生字典写在一起：

```yaml
spec:
  engineArgs:
    speculative-config:
      method: ngram
      num_speculative_tokens: 2
      prompt_lookup_max: 4
```

方法和子字段沿用 vLLM。需要草稿权重的方法，其 `model` 可填写 Hub 模型标识或容器内可见的绝对目录。`spec.source: modelscope` 同时适用于主模型和草稿模型的 Hub 标识。

## 工具、思考与结构化输出

强制选择工具或严格约束工具参数时，模型需要支持对应的结构化输出格式。支持结构标签时，在 ModelService 中声明该能力：

```yaml
spec:
  features:
    structuredOutputs: [structuralTag]
```

使用 `spec.modelPools` 时，在各适用 Pool 的 `features.structuredOutputs` 中声明，不使用服务级 `features`；保留已有的其他格式。

输出 token 预算包含思考内容。Messages 必须填写 `max_tokens`，不接受独立的 `thinking.budget_tokens`；思考控制取决于模型的聊天模板。预算耗尽时，Messages 返回 `max_tokens`，Responses 返回 `incomplete`。客户端只应执行完整的工具调用。

## 选择模型服务节点

将 `NODE_NAME` 替换为实际节点名称，再添加标签：

```bash
kubectl label node NODE_NAME workload-group=group-a --overwrite
kubectl get nodes -L workload-group
```

为组内每个节点设置相同标签，然后在模型 YAML 中选择：

```yaml
spec:
  nodeSelector:
    workload-group: group-a
```

服务级选择器用于默认 Pool；如需为某个 Pool 单独选择节点，使用 `modelPools[].nodeSelector`。
