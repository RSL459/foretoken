<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 专家重平衡不能让迁移成为新瓶颈

[English](windowed-expert-rebalancing.md) | 简体中文

## 问题与现状

EP 层的完成时间受最慢 rank 影响。每张 GPU 存相同数量的专家，并不意味着工作量相同：路由偏好随层、语言、任务与请求组合变化。把同一个逻辑专家复制到多个物理槽位，可以分摊执行，又不改变模型选择的函数。

vLLM 已实现按窗口统计的专家负载均衡 EPLB、冗余专家、异步传输、保留 GPU 内原有槽位，以及可选的无端点冲突迁移调度。这些应作为起点。剩余问题是：服务负载变化时，均衡收益能否覆盖观测滞后、迁移流量与额外显存？

## 执行顺序

引擎从前向执行收集专家负载，形成历史窗口。在配置的间隔到达后，策略读取全局估计与原有物理到逻辑映射。

默认策略在模型分组允许分层时，先把逻辑专家组分配到节点，再为每副本估计负载较高的专家分配冗余槽位，最后把物理专家装入各 GPU。复制循环使用 `w_e/r_e`：逻辑专家估计负载为 `w_e`，已有副本数为 `r_e`。增加副本能降低这个估计，但等分只是规划假设，不是下一批的实际测量。

例如估计负载 `[100,20,20,20]`，只有一个额外槽位，复制第一个专家后，其每副本估计为 50。这是分配示例，不意味着 GEMM 时间减半；真实耗时仍由形状和通信决定。

策略尽可能保留原有槽位。异步 worker 保存当前布局快照、计算新布局，把一层需要的权重传到暂存区，确认写入完成后发布待消费结果。前向侧必须安装权重并消费结果，才能复用暂存区。映射与权重应一起生效；只切换 ID 会执行错误参数。

核对的迁移调度器把同一有向 rank 对的传输合并，再把端点互不冲突的 rank 对分为一批；每批一个 rank 最多与一个 peer 通信。仍在同一 GPU 的专家不需要远程复制。

## 适用条件与取舍

窗口式均衡更适合持续热点，而不是迅速轮换的热点。短窗口响应快，但可能追逐采样噪声；长窗口则可能在业务切换后继续保留旧布局。间隔按引擎 step 计数，墙钟时间含义会随负载改变。

冗余权重及量化 scale 占用本可用于 KV 的显存。异步迁移仍消耗网络与设备带宽，host 非阻塞不等于推理没有干扰。量化权重及其 scale 必须作为一个专家表示迁移；图执行也必须使用仍然有效的存储与映射。

## 区分原因的实验

构造稳定热点、突然切换任务域，以及切换速度快于观测窗口的热点三种路由。记录逐层逻辑与物理负载、最大 rank 耗时、副本使用情况、迁移字节数与区间、KV 容量和客户端延迟。在固定冗余预算下比较窗口和间隔。

如果负载更均衡，但迁移期间 TPOT 上升，应检查传输干扰，而不是直接认为均衡算法错误。如果布局追上热点时热点已消失，原因是观测延迟。如果 token 数相同而 GEMM 时间不同，就说明 token 数不足以表达执行成本。

完整服务流量应覆盖多轮重平衡，而不是只测迁移后的稳态。检查映射变化时的输出，并在逻辑路由不变的前提下评估质量。分别报告普通时段与迁移时段，以及整体 TTFT、TPOT 和成功数。

## 依据与研究空间

核对日期：2026-10-14。vLLM [commit 6849ca69](https://github.com/vllm-project/vllm/tree/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9) 的[默认策略](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/distributed/eplb/policy/default.py)、[异步 worker](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/distributed/eplb/async_worker.py)、`migration_scheduler.py` 及[官方 EP 部署指南](https://docs.vllm.ai/en/latest/serving/expert_parallel_deployment/)。值得研究的是负载感知的执行时机与实测成本模型。逐批波动参见[在线副本分配](online-replica-token-assignment_zh.md)。
