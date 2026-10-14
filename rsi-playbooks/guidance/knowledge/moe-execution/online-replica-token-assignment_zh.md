<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 把当前批量分配到已有专家副本

[English](online-replica-token-assignment.md) | 简体中文

## 问题与现状

历史负载均衡的布局，当前批量仍可能很慢。小批量容易波动；同一个逻辑专家在副本间平均分配，也未必让副本所在 GPU 的总工作量相同。因此专家放置与逐批分配应使用不同时间尺度。

DeepSeek LPLB 已实现后者：统计当前逻辑专家选择，求解受约束的负载重分配，再改写物理目标。README 将其定位为研究早期实现，主要讨论训练中的逐批波动，性能仍在评估。这提供可用算法和源码依据，但不证明逐批求解能改善 decode 服务。

## 执行机制

先建立冗余拓扑：一个 GPU 的专家，也存放在另一 GPU 的冗余槽位。核对的 `Planner` 要求每 rank 冗余槽位数相同，并采用特定结构；有副本的逻辑专家恰有两个物理实例。历史 EPLB 先重排原始专家，再选取每设备热点专家用于这种拓扑。

每批依次执行 `count_workload` 统计逻辑 ID，`solve_probs` 同步负载并调用编译求解器，`weighted_select_target` 根据分配比例和逐 SM 计数元数据映射物理槽位。没有初始化其 DeepEP 通信路径时，负载通过配置的进程组同步。改变的只能是物理目标，逻辑专家与路由权重应保持不变。

可以用下式理解 token 数均衡目标；它不是源码内点法的逐项复述：

```text
minimize z
subject to sum_r x[e,r] = n_e
           sum_e x[e,r] <= z
           x[e,r] >= 0, only where replica(e,r) exists
```

`e` 是逻辑专家，`r` 是目标 GPU rank，`n_e` 是本批逻辑需求，`x[e,r]` 是分配给 rank `r` 上副本的需求，`z` 是各 rank 总行数的上界。这个 token 数模型假设专家每行的成本相近。求得比例后还要落到有限的整数行，源码映射核函数承担这一步。

例如 A、B 分别有 80、20 行专家计算，其中 A 的 40 行属于 B 也持有的专家。把其中 30 行移到 B，总量成为 50、50；没有副本的专家不能这样迁移。top-k 路由下这里计数的是专家求值，不是独立请求数。

## 适用条件与取舍

按已有权重分配，比每批加载新专家更轻，但只能沿副本图移动工作。增加拓扑边需要更多专家存储。LPLB 的双副本约束，对极端单热点的分摊能力弱于允许多副本的布局。

上游 README 报告节点内求解约 100 微秒、跨节点更高。这是来源报告，不是当前设备实测。单请求 decode 中，临界路径上的求解成本可能超过收益。实现也明确只平衡 token 数，没有纳入 grouped GEMM 的非线性耗时。

核对的 planner 使用旧 DeepEP `Buffer` 和 NVSHMEM 同步假设，当前 DeepEP 主线为 V2.5 `EPBuffer`，已移除 NVSHMEM。二者不能据此认为可直接组合。应复用算法或在其通信职责边界适配，不能默认最新版依赖兼容旧接口。

## 区分假设与服务验证

重放真实路由 ID，保持平均专家需求不变，改变批间波动。相同布局与显存预算下比较固定分配、副本均分和 LPLB。分别测统计、负载交换、求解、ID 映射、dispatch、GEMM 与 combine，同时计时完整层。

最大 token 负载下降而层时间没有下降时，应区分求解成本、拓扑流量和小 GEMM 的非线性。加入稳定单热点暴露双副本限制，加入极小批量寻找求解收支平衡区间。检查实际可行解结果，不能把每次调用都当作成功优化。

部署前确认物理 ID 指向等价专家表示，包括 scale。完整模型保持原始路由评估，再运行并发一和突发服务流量，观察客户端 TPOT、成功数、输出长度与质量。所有服务结果都应包含规划成本。

## 依据与剩余问题

核对日期：2026-10-14。[LPLB commit 0490f794](https://github.com/deepseek-ai/LPLB/tree/0490f79452f7ef277e814449600b1b1dd4c663b3) 的 README、`lplb/planner.py`、`lplb/eplb.py`及[当前 DeepEP](https://github.com/deepseek-ai/DeepEP/tree/93eb6eb238127e96c6d7a4a625a6dad158348509)。剩余问题是引擎集成、版本兼容的负载交换，以及实测延迟收支区间。较慢的布局循环见[窗口重平衡](windowed-expert-rebalancing_zh.md)。
