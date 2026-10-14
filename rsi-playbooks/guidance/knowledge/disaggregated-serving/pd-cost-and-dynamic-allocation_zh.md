<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# P/D 成本与动态分配

[English](pd-cost-and-dynamic-allocation.md) | 简体中文

## 问题与机制

长预填充会拖慢同一引擎中的解码请求。把预填充 P 与解码 D 分开，可以消除这种干扰，并分别选择批处理和并行方式，但也增加排队、KV 传输和模型权重副本。应判断隔离节省的延迟与容量是否超过这些新增成本。

对同一请求，可按首 token 路径记账：

`T_aggregate = Q_A + P_A + first_decode_A`

`T_split = Q_P + P_P + Q_X + transfer + Q_D + first_decode_D`。

这些项并非相互独立：路由、KV 预留和批处理会把它们耦合起来。基本临界条件是消除的干扰超过新增的传输和排队。如果 D 已有大量可复用前缀，即使原始输入很长，本地执行也可能更划算。

例如，32K 输入在选中的 D 上命中 31K，有效预填充只剩 1K。让它经过 P，可能只为少量计算节省付出远端传输成本。冷的 32K 输入则可能长期占用混合引擎，值得分离。判断要使用具体目标的缓存状态和解码余量，不能只看原始输入长度。

容量分配是较慢的决策。若到达率为 λ，经过 SLO 校准的单实例容量为 μ_P、μ_D，可从 `n_P = ceil(λ/μ_P)`、`n_D = ceil(λ/μ_D)` 起步，再随长度、命中率和批占用变化重估。按请求选择是否分离、改变角色副本数、把正在运行的 worker 从一种角色转换为另一种，是三件不同的事；前两项不能证明第三项已实现。

## 硬件与成本条件

必须固定模型、权重与 KV 的 dtype、TP 布局和链路。BF16 的 dense/GQA 模型中，prefill 通常更依赖算力，decode 更依赖 HBM 带宽和 KV 容量；MoE 与混合注意力会改变这个比例。FP8 权重不代表 FP8 KV，传输字节数应按实际缓存表示计算。

额外 P worker 的 GPU 时间、重复模型驻留、连接建立和退役时间，都应计入成本。短输入、低并发、通过主机中转的慢 TCP、很长的已缓存前缀，都可能让调优后的 chunked-prefill 聚合引擎更合适。固定 P:D 比例不能直接跨负载复用。

## 公开实现与集成范围

核对日期为 2026-10-14。Dynamo 的[条件分离文档](https://github.com/ai-dynamo/dynamo/blob/b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd/docs/fern/pages/developer-guide/advanced-customizations/conditional-disaggregation.md)已有基于有效输入长度／负载的决策和 decode-busy 覆盖条件，支持 vLLM 与 TensorRT-LLM，不支持 SGLang。[吞吐规划代码](https://github.com/ai-dynamo/dynamo/blob/b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd/components/src/dynamo/planner/core/throughput_scaling.py)已分别估计 P/D 容量，处理模型未就绪与 pending 启动，并可给反馈扩缩容提供容量下界。

llm-d 的[前缀决策器](https://github.com/llm-d/llm-d-inference-scheduler/blob/5253f55516f496129248766d1e4b745daba68887/pkg/epp/framework/plugins/scheduling/profilehandler/disagg/prefix_based_pd_decider.go)处理 `if-available` 偏好，未命中后缀足够长时可返回 HTTP 412，触发远端预填充。Production Stack 的[路由实现](https://github.com/vllm-project/production-stack/blob/4e076e8de3698a3729b575e3a5ade65ffbb929cf/src/vllm_router/routers/routing_logic.py)包含编排式 P/D endpoint 选择。

Foretoken 的[阶段执行](../../../../data-plane/frontend/src/server/src/runtime/workflow.rs)已经在 P 完成后刷新选择 D，并保留跨阶段清理职责；[扩缩容 owner](../../../../control-plane/internal/autoscaling/README_zh.md)分别评估角色 Pool。

## 有区分力的实验与剩余问题

先用排队模型重放相同到达时间、输入／输出联合长度、命中率和传输成本。在相同 GPU 预算下比较固定比例、独立角色扩缩容和条件分离。单独改变热前缀所在位置，避免把缓存预热误算为调度收益。

真实服务比较 aggregate chunked-prefill 与 P/D，使用相同 checkpoint 和输出设置。覆盖短冷、长冷、长热请求，并加入扩缩容期间的突发。记录 TTFT、TPOT 分布、成功且满足 SLO 的有效吞吐、传输延迟、ready／requested 容量和 GPU 总时间。检查 D 饱和或传输是否替代了 P 干扰，成为新瓶颈。缓存／负载信息滞后时的联合决策和昂贵角色切换仍值得研究。

[返回分离式推理服务](README_zh.md)
