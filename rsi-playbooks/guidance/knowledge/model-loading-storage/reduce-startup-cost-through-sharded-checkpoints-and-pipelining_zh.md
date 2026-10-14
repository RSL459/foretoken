<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 通过 Rank 本地检查点与加载流水降低启动成本

[English](reduce-startup-cost-through-sharded-checkpoints-and-pipelining.md) | 简体中文

下载完成不等于模型就绪。启动还要解析文件、分配张量、读取并安装权重、转换成运行时表示，再准备执行。加快文件读取消除不了所有后续阶段，缓存检查点也不一定缓存了运行时表示。

## 沿加载阶段分析

vLLM [DefaultModelLoader](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/model_executor/model_loader/default_loader.py)先准备本地或远端文件，根据 index 过滤重复，构造权重迭代器，调用模型的 `load_weights`，再在适用条件下检查参数覆盖。模型构造与加载后处理围绕这条路径。融合参数映射、TP 切分和量化转换属于模型安装代码，而不是通用文件 reader。

检查点大小 W 时，顺序读取约为 `T_read = W/B_storage`；启动还包括安装、H2D、转换与运行时准备。真正流水化后，稳定阶段由最慢阶段决定，而非各阶段之和，但启动、排空和模型特有工作仍存在。使用这一估计前应确认实际按块重叠。

以 TP4 加载全局 40 GiB 权重为例，各 rank 读取全部权重再切片，聚合 I/O 可能远大于各自读约 10 GiB 本地表示。这只是均衡示例，复制张量、expert 分配、padding 与运行时量化都会改变数字。跳过无关张量读取与一次转换成 rank 本地检查点，解决的是不同成本。

[ServerlessLLM，2024 年 1 月](https://arxiv.org/html/2401.14351v1)采用面向加载的检查点：对齐的 GPU 专属二进制张量数据、偏移索引，以及存储/主机/GPU 分块流水。值得借鉴的是把反复解释和布局转换移出关键加载路径，不是将其启动时间直接套到其他引擎。

## 已有能力

[实现来源](README_zh.md#参考)中的 vLLM [ShardedStateLoader](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/model_executor/model_loader/sharded_state_loader.py)已读取 rank 专属 safetensors，直接复制到准备好的参数中。默认文件名记录 TP rank，启用 PP 时还记录 PP rank，而非并行大小。别名和重叠 view 过滤避免重复存储。它不负责任意运行时量化或重新分片；拓扑特定检查点不能未经明确转换就用于其他拓扑。

默认 loader 已有本地 expert 过滤和 fastsafetensors/instanttensor 专用路径，过滤还受 expert 负载均衡等条件约束。vLLM 也已接入 [ModelExpress](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/model_executor/model_loader/modelexpress_loader.py)，都是新建自定义加载系统之前应检查的现有选择。

Dynamo [weight artifact](https://github.com/ai-dynamo/dynamo/blob/7708f041a965e35374af976ab8ad610b9537e3bc/lib/gpu_memory_service/v1/snapshot/weight_artifact.py)保存 allocation 字节，与按名字描述的检查点不同。Mooncake 当前权重管理提供发布元数据，但 reader 接入仍有未完成部分。LMCache 的 KV 缓存不消除权重安装。判断某种缓存是否能替代另一种前，应先确认表示的消费者。

## 实验与剩余问题

局部对照标准检查点、已有张量过滤和拓扑匹配的 sharded checkpoint，固定模型修订、dtype、rank 几何和转换。记录文件解析、每 rank 实际读取字节、CPU 实体化、H2D、参数安装和加载后处理，核对 logits 与参数覆盖。I/O 减少而启动不变，说明瓶颈在后续；I/O 不变而安装减少，说明省下了转换。

分别测试冷文件系统、热页缓存和重复启动进程。服务侧测进程启动到就绪、首个成功生成及前几次请求，将编译/预热与权重加载分开，保存主机和设备峰值内存。剩余研究是跨真实拓扑变化复现运行时表示、避免重复转换。

[模型加载与存储](README_zh.md)
