<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 多模型共享 GPU 容量：按需伸缩物理内存

[English](share-gpu-capacity-through-multi-model-memory-ballooning.md) | 简体中文 | [多模型与适配器](README_zh.md)

## 共享设备不等于共享基础模型

不同完整 checkpoint 通常有不同权重与 KV 语义。多 LoRA batch 可以共享基础 GEMM，多模型共置通常不能。问题在于回收闲置预留，让另一个模型扩容，同时避免交错流量不断触发权重切换。Prism 的 OSDI 2026 终版论文通过 GPU memory ballooning 联合空间共享与时间共享；公开 kvcached driver 提供可复用的弹性 KV 设施。

Prism 终版描述完整调度与激活系统，kvcached 则提供独立版本的 driver。研究原型和当前 driver 的 graph、prefix cache 配置有所不同。

## 一个模型扩张，另一个模型空闲

engine 为 KV tensor 预留稳定虚拟地址，实际 token block 需要空间时才映射物理页。block 释放后，空页可以回到缓冲区或真正回收，让另一 engine 分配物理内存，而不改变原 tensor 逻辑地址。不同模型仍保留独立 KV 内容与布局；共享容量不等于共享 token 状态。

Prism balloon driver 还协调权重与 KV 内存。空闲模型驱逐释放权重驻留，低负载但仍驻留的模型缩小未使用 KV。可重用 engine pool 在再次激活时保留初始化和分布式 context。终版权重加载把 tensor 分块，通过本节点多 GPU 并行传输，再经 NVLink 汇聚，并采用有界流式缓冲。快速激活与 KV allocator 是两项不同职责。

容量关系可写为 sum_j(W_j+K_j+A_j)+R≤C：W 为驻留权重，K 为物理 KV，A 为 activation/workspace，R 为 runtime 预留，C 为设备容量。虚拟预留不是另一个物理 K 项。所有模型同时达到峰值时，弹性不会让总量消失，仍需要 admission 和 placement 决定可满足的目标。

论文采用需求互补的放置与本地 slack-aware 仲裁，以保留内存余量、避免无控制争用。

## 当前可用性、模型与精度

终版论文在 NVIDIA H100 上评估多种模型大小与架构。kvcached README 描述 0.1.6，测试 vLLM 至 0.30.0、SGLang 至 0.5.20，覆盖 hybrid attention 与 AMD/ROCm 路径。这不能证明任意更新引擎、布局或设备兼容。AMD 默认 non-contiguous KV，以匹配 backend 要求。

各模型独立使用自己的公开 checkpoint、tokenizer 与配置，不需要重新训练。量化权重、FP16/BF16 KV、hybrid state、TP 布局都会改变物理 block 几何。当前 driver 对不能放入普通物理页的 block 自动放大页，说明页尺寸属于真实布局条件，而非任意调参项。

ServerlessLLM 提供互补基础：优化加载的 checkpoint、pinned buffer、direct I/O，及原设计中的 token replay 迁移。replay 与直接 KV 传输具有不同成本和正确性条件。加载更快不能单独证明稳态多租户执行更好。

## 分开验证内存与调度

至少回放交替突发、部分重叠突发、同时峰值三种模式。固定模型、精度、服务限制和总设备容量，比较独占 engine、固定共置分区、仅弹性 KV、弹性 KV 加模型激活。

按模型记录 TTFT/TPOT 尾延迟、SLO goodput、物理映射与虚拟预留字节、权重/KV/workspace、页操作、激活和迁移时间、HBM 与 PCIe/NVLink 流量、preemption、失败。加入长上下文与 hybrid-state 模型，暴露布局假设。检查虚拟地址在 graph replay 后仍有效，以及 prefix cache 行为符合选定版本。

交替流量改善、同时峰值失败，说明瓶颈是容量而非 allocator；激活传输拖慢驻留 decoder，就要把干扰计入每成功请求成本。剩余研究在受支持引擎上的负载感知内存仲裁与干扰。

## 参考

- [Prism，OSDI 2026](https://www.usenix.org/conference/osdi26/presentation/yu-shan)及[终版 PDF](https://www.usenix.org/system/files/osdi26-yu-shan.pdf)：终版方法与实验，包括 ballooning、engine 复用和加载；2026 年 7 月发表。
- [kvcached `94d117c`](https://github.com/ovg-project/kvcached/tree/94d117c1e2d6e6c190223e1de35d38e1882c7acb)：README，commit 日期为 2026-10-13，保留已有插件支持和版本/布局限制。
- [Prism research prototype](https://github.com/Multi-LLM/prism-research)：执行示例与原型范围，不代替当前 driver 或终版论文。
- [ServerlessLLM 原方法，arXiv:2401.14351v1](https://arxiv.org/html/2401.14351v1)与[当前仓库](https://github.com/ServerlessLLM/ServerlessLLM)：加载和迁移机制。
