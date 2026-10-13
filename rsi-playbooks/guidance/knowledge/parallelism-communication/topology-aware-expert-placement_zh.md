<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 专家副本放置同时考虑计算与链路负载

[English](topology-aware-expert-placement.md) | 简体中文

## 问题与现状

专家布局能让 token 数均衡，却可能把大量流量送过较慢边界；优先本地性也可能留下热点 rank。合理目标应同时考虑专家执行和 token、输出、迁移权重所经过的链路。

DeepSeek EPLB 衍生算法已有拓扑感知布局：把兼容的逻辑专家组装到节点，在节点内创建副本，再分配到本地 GPU。LPLB 还有 cube、hypercube、torus 副本图；当前 DeepEP 主线也已有冗余专家 NVLink 权重预取。剩余问题是如何根据真实路由与网络竞争选择、评估这些结构。

## 执行机制

从模型逻辑专家组、真实路由和 rank 连通性测量开始。核对的 vLLM 默认策略先按组汇总需求，把组放到节点，节点内复制专家，再按每副本负载装入 GPU。专家组与节点数整除关系不满足时，实现退回全局 packing；这并不证明退回路径仍保留本地性。

复制改变物理目标图，不改变逻辑路由。附近 GPU 的副本可以分摊工作且不增加网络域跨越，但前提是实际 dispatch 分配选择了它。远端副本则可能平衡计算，却增加输入与返回流量。

LPLB 的 `r2o` 显式表达副本关系。cube 支持八 GPU 子组内均衡；torus 可以同时连接本地邻居和邻节点。这些是已有算法结构，不证明 torus 在全局一定更好。它们约束哪些热点能共享工作，以及副本数量。

例如 hidden 宽度 `H=4096`、BF16 激活，有 1000 行专家计算跨节点，单向原始行 payload 为 `1000*4096*2=8,192,000` 字节。这不包含元数据、scale、头部、对齐，也没有考虑去重；多个选中专家同属一个目标时，通信可能复用输入行。输出返回又是另一段流量。应记录后端实际字节数，不要直接按 top-k 放大。

新选副本还需要权重。DeepEP 主线 `lb_prefetch_weights` 在专家计算前通过 NVLink 传权重和量化 scale，使用调用方给定映射及预留存储。域内所有 rank 都参与，没有冗余槽位的也要调用。通信原语负责传输完成，调用方仍负责规划、token 重路由和专家计算；它不是完整的服务副本策略。

## 适用条件与取舍

模型路由组不等于可任意切分的硬件组。修改模型选择来强制本地性，会改变行为；映射同一专家不会。物理布局实验应保持逻辑选择与权重。

拓扑由实际 GPU/NIC 映射、peer 可达性和竞争流量决定，节点数相同不意味着通信域相同。节点内副本用权重显存交换本地性，占用本可用于 KV 的空间；频繁复制移动的权重字节数，也可能超过节省的 token 流量。

副本应保持数值与表示等价，包括全部 scale。训练路由 bias 更新属于模型变化，不应与物理负载均衡混同。

## 实验与服务验证

固定副本数，比较分层布局、全局 packing 和可实现的自定义副本图。输入覆盖均匀路由、节点本地组、远端热点与任务突然切换。记录各链路 dispatch/combine 字节数、最大链路负载、逐 rank GEMM、权重迁移字节数和 KV 容量。

token 均衡但层变慢，检查远端通信与 GEMM 非线性；本地性改善但 rank 倾斜加大，明确取舍，不能平均后掩盖。加入代表性的共享网络流量，判断布局是否经得住链路竞争。

完整模型部署到真实拓扑，比较未加 profiler 的 TTFT、TPOT、成功吞吐、质量，以及布局变化期间延迟。核对取消和空 rank 参与。
## 依据与状态

核对日期：2026-10-14。实际阅读 vLLM [6849ca69 的默认 EPLB 策略](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/distributed/eplb/policy/default.py)、[LPLB 0490f794](https://github.com/deepseek-ai/LPLB/tree/0490f79452f7ef277e814449600b1b1dd4c663b3) README 与映射代码，以及 [DeepEP 主线 93eb6eb2](https://github.com/deepseek-ai/DeepEP/tree/93eb6eb238127e96c6d7a4a625a6dad158348509) 的冗余专家交换接口。[#500](https://github.com/deepseek-ai/DeepEP/pull/500) 已合入 `antgroup-opt` 而非主线，本条目不凭其标题推断算法。剩余研究是实测计算与网络联合布局。快循环见[在线分配](../moe-execution/online-replica-token-assignment_zh.md)，迁移时机见[窗口均衡](../moe-execution/windowed-expert-rebalancing_zh.md)。
