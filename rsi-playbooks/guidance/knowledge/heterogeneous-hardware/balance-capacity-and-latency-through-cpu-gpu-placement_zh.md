<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 通过 CPU/GPU 放置与卸载平衡容量和延迟

[English](balance-capacity-and-latency-through-cpu-gpu-placement.md) | 简体中文

增加内存容量可以让模型运行，却不保证更快。CPU/GPU offload 和不同性能设备的组合，需要同时计算执行与传输预算。按层顺序执行、每层同步 tensor shard、每次前向搬运权重，是三种不同机制。

## 容量与延迟是不同约束

设备 j 上至少要满足：

```text
weights_j + state_j + workspace_j + graph_memory_j ≤ usable_memory_j。
```

这不说明请求耗时。顺序层划分的延迟近似为各分区计算之和，加边界激活传输。TP 层则受最慢 shard 和归约／通信约束。因此按内存比例分配，只是容量启发式，不保证计算均衡。

假设两设备可用内存相同，一个在目标 GEMM 上快一倍。均分 tensor 会让快设备等待。按吞吐分配可能给快设备更多工作，但仍受对齐、架构、kernel 和反复归约约束。顺序层放置则可能把更多层交给快设备，即使两种划分都能放下模型。

权重 offload 又有不同成本。每 token 需要搬运 S byte、实际带宽为 B 时，仅传输下界就是 `S/B`。以示意的 32 GiB/s 搬 4 GiB，至少 125 ms，还没包含计算和同步。这里是量纲示例，不是实测链路。仅搬分区边界激活通常小得多；CPU 常驻层则支付 CPU 读取权重和矩阵计算。不能不解释执行方式，就将这些都泛称 offload。

## 上游已有放置机制

引用版本的 llama.cpp 多 GPU 指南包含按层放置、GPU layer 数和 split 比例。layer 模式分配连续层，减少设备间传输；experimental tensor 模式切分权重和状态，每层反复跨设备归约。指南的性能建议主要针对 NVIDIA CUDA。tensor 模式要求支持的架构与 flash attention，当前不接受量化 cache，也没有自动 fitting。

该指南还明确区分 backend：找到 NCCL 时默认在构建中启用，而 HIP RCCL 默认关闭，因为上游测量并非普遍获益。这反映不同执行交换条件，不能推广成其他引擎都应关 RCCL。

CPU 方面，当前 vLLM 指南建议每 rank 的线程和内存在 NUMA 本地，给服务保留 host core，避免超线程过度并行。BF16/FP16/FP32 与指令支持随 CPU 架构变化。CPU backend 有矩阵指令，不代表它也提供 GPU offload 或统一量化格式。

## 尚需判断的选择与实验

剩余空间是依据实测计算、内存带宽、NUMA 与链路做放置。量化权重可减少传输，但转换和混合 backend 不支持的算子可能抵消收益。

相同模型和 dtype 下比较已有单设备、layer 分区与受支持 tensor split。记录实际设备归属、分区时间、传输量、归约时间、CPU 带宽和 NUMA。加载与稳态推理分开；搬权重的路径必须包含每次重复传输，不能只测缓存后的 warmup。

服务侧观察单请求 TPOT、prefill TTFT、batch 吞吐及目标上下文下成功输出；多请求共享 CPU 带宽时还看 host 内存压力与尾延迟。慢一些但能跑更大模型仍可能有价值，不过应报告为容量交换，不是速度提升。

## 参考

- [llama.cpp 多 GPU 执行，commit 77c4540](https://github.com/ggml-org/llama.cpp/blob/77c4540ce4667f4577753fe034a3a8042f510b8f/docs/multi-gpu.md)。
- [vLLM CPU 指令、dtype、NUMA 和线程指南](https://docs.vllm.ai/en/latest/getting_started/installation/cpu/)。
- [llama.cpp token generation 性能入口](https://github.com/ggml-org/llama.cpp/blob/77c4540ce4667f4577753fe034a3a8042f510b8f/docs/development/token_generation_performance_tips.md)；其中示例数字是历史结果，不是当前硬件对比。

[异构执行](README_zh.md) · [并行与通信](../parallelism-communication/README_zh.md) · [知识索引](../README_zh.md)
