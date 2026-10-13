<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 按 SLO 选择执行批次

[English](slo-aware-batch-scheduling.md) | 简体中文

不同请求的延迟目标不同时，每轮都让所有活跃流 decode，可能把紧缺容量花在本来可以稍等的请求上。反过来，一味优先 decode 又会让等待中的 prefill 错过首 token 期限。批次选择需要同时考虑两个阶段及每个请求实际需要的服务频率。

## 现有机制与研究增量

当前 vLLM V1 已有 chunked prefill、依赖优先级的抢占，以及 `next_decode_eligible_step` 检查。这些是执行机制，不能据此认定已有完整的异构 SLO 优化器。SOLA 研究每轮排序与工作量；SCORPIO 的 2026 年 8 月修订把准入、deadline 队列和不同 decode 频率结合起来。它们处理的目标比“增加请求优先级”更具体。

SOLA 的实验集成基于历史 vLLM 0.4.2，不能把论文对其默认顺序的描述当作今天 V1 的默认行为。
## 服务频率如何改变批次

假设一类请求要求 TPOT 不超过 50 ms，另一类允许 100 ms。SCORPIO 用最严格目标除以请求自身目标得到 token requirement proportion：`TRP = min_target / request_target`。两类比例分别为 1 和 0.5。每轮 decode 增加相应 credit，credit 达到一的请求进入批次，并消耗一个 credit。因此宽松请求大约每两轮执行一次，而非每轮都执行。

这种安排还要求批次实际耗时满足目标。SCORPIO 根据各请求比例之和形成 virtual batch size，并结合序列长度估计 TPOT。若一轮本身耗时 90 ms，credit 算术无法满足 50-ms 目标；平均 TPOT 也不能保证每次 token 间隔，因为迭代耗时会波动。

对于 prefill，SCORPIO 根据首 token deadline 压力安排队列，并拒绝预测不可达的请求。SOLA 则先观察 TTFT 和 TPOT 相对各自目标的压力，选择改善其中一项、约束另一项，再调整阶段顺序、请求顺序与逐轮工作量。Decode 尚有余量时可以多安排 prefill；decode 已落后时减少插入的 prefill，保留生成机会。执行成本模型会用实际迭代时间更新。校准绑定模型、dtype、backend、拓扑和并行配置；在线修正并不意味着系数可跨部署直接复用。

Andes 把目标进一步扩展到用户体验：比较实际交付 token 进度与预期消费曲线，估计现在执行而不是稍后执行带来的体验增量。缓冲区仍有可消费 token 的流可以暂等，空缓冲区的流先追上。但应用必须确实具有这种消费语义；机器调用可能需要立即拿到每一个 token。

## 职责与取舍

引擎负责真实批次成员、decode 频率、prefill 进度、内存可执行性与取消。Foretoken 请求层负责入口身份、排队时间、deadline 传递和选实例。仅附一个 priority 整数，不能让路由器保证引擎的下一 token 期限。集群编排负责容量，但无法事后补救毫秒级的错过迭代。

跳过部分 decode 轮次可以减少竞争，却会增加 token 间隔波动，也改变 KV 驻留请求对内存的竞争。输出长度预测错误会扭曲未来内存与延迟估计。只最大化总体 SLO 达标率，还可能牺牲少数类别，因此必须明确类别目标或公平性。负载可承受且目标一致时，简单的 decode-first 预算可能已经足够。

## 有区分力的实验

重放相同到达轨迹，设置至少两类 TTFT/TPOT 目标，并在中途改变类别比例。固定模型、输出长度分布、硬件与请求速率，比较现有调度、固定分块预算、state-aware 或 credit 调度。再增加系统性低估长输出的实验。

Goodput 应按每秒完成且同时满足两项目标的请求数计算；所有到达请求的拒绝、超时和取消都要可见。还需报告逐类别达标率、最差类别排队延迟、p99 token 间隔、抢占、内存占用和调度开销。只提高“已接纳请求的成功比例”不能证明容量增加。用执行轨迹确认收益来自批次工作变化，而非缩短输出或丢弃请求。

下一步应核对引擎元数据是否能端到端表达所需 SLO 与执行频率，复用已有调度入口，再测量策略。增加字段或引用论文总收益，都不能替代这个集成闭环。

## 来源

核查日期：2026-10-14。

- [SCORPIO，arXiv 2505.23022v2，2026-08-26](https://arxiv.org/html/2505.23022v2)：TRP、virtual batch size 和准入/队列/批次联动。
- [SOLA，MLSys 2025，§§4–5](https://proceedings.mlsys.org/paper_files/paper/2025/file/bc82dbfbfa43232be85b8d9838f49c3e-Paper-Conference.pdf)：有约束的工作量控制与状态排序。
- [Andes，arXiv 2404.16283v1](https://arxiv.org/html/2404.16283v1)：交付曲线体验目标与计入抢占开销的选择。
- [vLLM scheduler，commit 6849ca69](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/v1/core/sched/scheduler.py)：当前 eligibility、预算与 priority 机制。
