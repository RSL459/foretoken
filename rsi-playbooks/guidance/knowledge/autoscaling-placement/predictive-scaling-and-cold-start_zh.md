<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 预测扩容与冷启动

[English](predictive-scaling-and-cold-start.md) | 简体中文

## 问题与机制

现在请求的副本可能几分钟后才能服务。采集、平滑、决策、调度、镜像与权重加载、graph 预热、路由发布都贡献延迟。如果启动需 180 秒，而预测只覆盖下一个 15 秒采样，再复杂的模型也可能从结构上晚到。

应预测容量 ready 时的需求。简单控制器可先平滑 token 工作量：`x̂_t = α*x_t + (1−α)*x̂_(t−1)`，再把趋势外推到实测启动跨度 Δ，加入有界不确定性余量，按校准的 prefill/decode 容量换算副本。2026 年分解论文采用 `x̂_(t+Δ) = x̂_t + slope*(Δ−T/2)`，T 为采样间隔；余量为 `β*min(σ, γ*abs(x̂_(t+Δ)))`。

必须分别跟踪 requested、starting、ready、routable 和 draining。两个 ready 加两个 starting，既不是当前只有两个需求目标，也不是已有四份服务能力。Starting 可抵扣重复扩容请求，但不能算成即时吞吐。失败或 unschedulable 的启动，与仍处在正常预热中的启动，应区别处理。

例如需求 60 秒内从 10 升至 20 请求/s，每副本容量 5，启动需 120 秒。反馈控制器观测压力后才请求四个副本，容量会在爬坡结束后到达。预测只有在趋势可观测或有调度信息时才能提前；完全没有预告的跳变无法被预测，需用有实际成本的暖容量或准入策略承担。

## 硬件与公开证据

[Decomposing Predictive Kubernetes Autoscaling](https://arxiv.org/html/2609.20874v1)分别分析 token 跟踪、lookahead、不确定性和运行状态观测。模拟使用五个 seed、180 秒启动，绝对 TTFT 约为校准硬件值两倍，因此相对策略比较比绝对数字更可靠。

物理验证使用 Qwen2.5-7B-Instruct、vLLM 0.11、A100 40GB、每副本一 GPU，注入 60 秒启动 sleep，报告 delay-aware EWMA 相对 reactive KEDA 的 TTFT 失败减少。文中未指定 dtype，硬件验证规模较小，也未验证 P/D。作者表示发表时发布 artifacts，未给代码 URL。这些范围决定了机制如何复用。

Checkpoint 存储、量化、CPU 反序列化、graph size 会独立改变启动。FP8 减少权重字节，也可能增加转换或 kernel 准备。应分开测冷启动和缓存暖启动；人为 sleep 能隔离延迟机制，却不能重现全部真实加载瓶颈。

## 当前公开实现

核对日期为 2026-10-14。Dynamo 的[预测器](https://github.com/ai-dynamo/dynamo/blob/b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd/components/src/dynamo/planner/core/load/predictors.py)已有 constant、ARIMA、Prophet、Kalman，`predict_next` 是单步接口。[吞吐 scaler](https://github.com/ai-dynamo/dynamo/blob/b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd/components/src/dynamo/planner/core/throughput_scaling.py)已处理 pending 启动和性能模型未就绪。有预测器不等于已经按启动分布设计了预测跨度。

AIBrix 的[预测文档](https://github.com/vllm-project/aibrix/blob/d0500b0399cf35ad0bf95d073faa83c23308f463/docs/source/features/scaling-performance/autoscaling/predictive-autoscaling.rst)明确说明字段接受与验证已实现，controller 消费延期。[autoscaler 代码](https://github.com/vllm-project/aibrix/blob/d0500b0399cf35ad0bf95d073faa83c23308f463/pkg/controller/podautoscaler/autoscaler.go)有反馈采集／聚合／建议和 pending replica 处理，未展示预测执行。不能把规划的 Preview/Auto 语义写成已交付能力。

Foretoken 的[扩缩容架构](../../../../control-plane/internal/autoscaling/README_zh.md)保持正在转换的目标容量，稳定窗口历史由当前 controller 进程保存。[公开策略](../../../../docs/autoscaling_zh.md)未建立预测能力。运行状态准备由 controller 负责，预测器应通过现有算法边界返回 recommendation。

## 实验与剩余问题

先用 trace 驱动的延迟执行模拟，比较 reactive、token-only、仅 lookahead、lookahead 加余量。扫描启动分布、突然跳变、趋势反转、指标延迟和 GPU 不可用。按 GPU 时间与 SLO 失败权衡，不只看预测误差。

真实服务再用同一 arrival trace 比较冷／暖启动，记录生命周期时间点、pending credit、实测启动分位数、路由可见性和瞬态失败。在同一资源成本下比较 EWMA 与复杂预测。启动分布校准、取消过时启动和多模型竞争预算仍待研究。加载机制见[模型加载与存储](../model-loading-storage/README_zh.md)。

[返回扩缩容与放置](README_zh.md)
