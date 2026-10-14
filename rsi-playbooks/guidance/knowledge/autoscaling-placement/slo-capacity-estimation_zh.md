<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# SLO 容量估计

[English](slo-capacity-estimation.md) | 简体中文

## 问题与机制

峰值 token/s 不能告诉 autoscaler：同时满足首 token 延迟 TTFT 和 token 间延迟时，一个副本能服务多少请求。容量必须以模型、设备、批处理、长度、缓存复用及目标分位数为条件。只按 decode 吞吐配置副本，可能完全没有保护 prefill 排队。

扫描以请求数/秒计的到达率 λ，测量单副本服务曲线。对指定负载定义 `μ_SLO = sup{λ: 所需延迟和成功约束成立}`；λ_demand 为总到达请求率，初始副本目标为 `ceil(λ_demand/μ_SLO)`。但真实负载分配、缓存碎片和启动过程使它不能成为保证。分离服务需分别估计 P/D，并把传输计入首 token 预算。

例如孤立 prompt 处理需 20 ms，TTFT 目标 100 ms。若把剩下 80 ms 全分给排队，路由、传输和波动就没有余量。平均解码更快不能修复这项预算。把分位数目标替换成平均 TTFT，也会隐藏少数超长请求。

2026 年排队模型论文用 `T(i)=α+iδ` 描述迭代时间：i 是活跃批次请求数，α 是固定迭代开销，δ 是每个活跃请求增加的时间，包含输入／输出长度上的计算与 KV 访问。Birth–death 状态计入活跃与等待请求；超过批次上限 B 时，只按 B 个活跃请求提供服务。再用状态相关 birth–death chain 估计占用、队列和平均 TTFT/ITL。这是简洁的校准方法，不是尾延迟预测器：Poisson 到达、平均长度和轻／中负载验证，限制了接近饱和时的外推。

## 硬件、dtype 与证据

[An Approximate Queueing Model](https://arxiv.org/html/2609.20957v1)在 H100、vLLM 上评估 BF16 Llama-3.1-8B 和 Qwen2.5-14B，batch 上限 256、token budget 8192。报告平均 ITL 误差约 5%／8%，平均 TTFT 误差约 14%／16%。其控制器以更多副本换取更少目标失败周期。

显存可能比校准的计算曲线更先成为瓶颈。KV dtype、全注意力或混合 cache group、TP 复制、长输出都会改变驻留容量。不能把 FP8 权重 GEMM 加速直接带入 BF16 KV 的延迟模型。Profile 成本按有实质差异的模型／设备／runtime 配置支付，不只是按模型名称支付。

## 公开实现与当前范围

核对日期为 2026-10-14。Dynamo 的[planner README](https://github.com/ai-dynamo/dynamo/blob/b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd/components/src/dynamo/planner/README.md)和[吞吐实现](https://github.com/ai-dynamo/dynamo/blob/b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd/components/src/dynamo/planner/core/throughput_scaling.py)已有针对 TTFT/ITL 的引擎容量模型，prefill 使用命中率，decode 使用 acceptance length。模型未就绪时保持容量，而非虚构服务速率。

llm-d 的[SLO 指南](https://github.com/llm-d/llm-d/blob/277b34d062ff954435cf8b1b05efbd75090cf788/guides/workload-autoscaling/slo-aware/README.md)与[recording rules](https://github.com/llm-d/llm-d/blob/277b34d062ff954435cf8b1b05efbd75090cf788/guides/workload-autoscaling/slo-aware/prometheus-rule.yaml)用 `max(P90_TTFT/S_TTFT, P90_TPOT/S_TPOT)` 表示压力，S_TTFT、S_TPOT 为延迟目标。Recording rules 优先使用预测延迟直方图，缺失时回退到实测值，以一分钟速率窗口计算 P90；压力先截到 2，再做 45 秒平滑，通过 dead band 和 pending-capacity credit 驱动 KEDA。该指南明确只支持单 variant／单 SLO 对，其 P/D 适配属于后续工作。

Foretoken 的[扩缩容指南](../../../../docs/autoscaling_zh.md)与[token-load 决策](../../../../control-plane/internal/autoscaling/algorithm/decision/token_load.go)提供 queue/token 策略，不是上述 SLO 校准容量估计器。现有架构已把 recommendation 与 controller 生命周期分开；未来估计器应进入决策边界，而不是增加第二个控制器。

## 实验与剩余问题

用部分实测点拟合小模型，留出其他长度、命中率和速率验证。分别统计均值误差和目标分位数误差，覆盖饱和拐点与重尾混合；轻负载准确的模型，可能在扩容真正必要时失效。

真实服务加入稳态、爬坡和突发，同一预算上下界内比较 queue scaling、校准容量分配与延迟反馈。以全部到达请求为分母记录 SLO 达标率，同时记录有效完成请求数/秒、错误、ready 容量、GPU 时间和预测残差。在线回归能否在尾延迟失败前适应缓存／长度漂移，以及如何联合估计 P/D／传输容量，仍是研究问题。模拟方法见[测量与仿真](../measurement-simulation/README_zh.md)。

[返回扩缩容与放置](README_zh.md)
