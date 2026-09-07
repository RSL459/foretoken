<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Router 维护指南

[English](MAINTAINER.md) | 中文

Router 算法编译在 Frontend 二进制中，不是运行时插件，也不是公共扩展接口。

## Pipeline 契约

每个请求依次经过：

```text
兼容且健康的候选项
→ Filter 返回的下标
→ Scorer 返回与保留候选项一一对应的分数
→ Picker 返回的下标
→ RouteDecision
```

- `RouteFilter` 返回需要保留的候选项下标。
- `RouteScorer` 按相同顺序为每个保留候选项返回一个 `RouteScore`。
- `RoutePicker` 返回 scored candidates 中的一个下标。

Router 负责候选项身份，并校验重复或越界的下标以及分数数量不一致。算法不能维护第二份路由目录，也不能在请求路径查询 model-server；算法接收的是当前选择轮次中不可变的观测快照。

## 添加算法

在 `src/algorithm/filter/`、`src/algorithm/scorer/` 或 `src/algorithm/picker/` 下实现对应接口，然后在对应 stage 的 `mod.rs` 中为 `declare_router_algorithms!` 列表增加一项，填写模块名、类型名和用户配置名称。该宏会生成模块声明、公开导出和编译期 descriptor 注册；不需要修改 Controller enum 或 CRD。只有可观察行为发生变化时，才同步维护中的示例、面向用户的 Router README 和 contract tests。

请求级共享状态放在 `RouterPipeline::with_customized_context` 中。Router 为每个请求创建一个 context，并在请求结束后释放。

## 多阶段路由

算法对完整的兼容、健康候选项快照进行评分。Picker 执行前，Router 会将候选项限制到当前执行阶段和已选择的控制器定义 pipeline scope。这样既保持聚合、P/D 和 E/P/D 的执行 ownership，也允许 Scorer 考虑关联阶段的负载。

## 指标打分契约

`running_request` 打分器对应 llm-d-router 的 `d8d22ea8f7d412f2a7e61ec415d11b24322a7938` 版本：

| Foretoken scorer | llm-d 源码 | 输入 | 分数 |
| --- | --- | --- | --- |
| `running_request` | [running-requests-size-scorer](https://github.com/llm-d/llm-d-router/blob/d8d22ea8f7d412f2a7e61ec415d11b24322a7938/pkg/epp/framework/plugins/scheduling/scorer/runningrequests/runningrequest.go) | `scheduler_running_requests` | `(max - running) / (max - min)` |

给定相同的指标和候选集，返回数值与上游的单端点打分器一致。
使用传入 `score` 的全部候选项求最小值和最大值；计数全部相等时得 `1`，空候选集返回空分数列表。
计数先相减再转为 `f64`，避免大整数提前转换丢失差值。
数值通过 `RouteScore.preference` 原样传给 Picker，其余位置和负载字段为零。
原有位置策略继续使用字典序。

Registry 负责指标历史：立即发布 gauge，某项缺失时保留之前的实测值，速率与直方图在
计数器窗口足够前保持不可用。指标打分器将从未观测到的值映射为零，与 llm-d 的
[端点指标初始值](https://github.com/llm-d/llm-d-router/blob/d8d22ea8f7d412f2a7e61ec415d11b24322a7938/pkg/epp/framework/interface/datalayer/metrics.go) 一致。

Foretoken 继续负责遥测传输、健康检查、DP 展开及 E/P/D 阶段资格判断。
Model Server 端点报告各引擎 scheduler 计数之和及 KV 使用率均值，因此同一端点的所有 rank
得到相同分数。该 scorer 不使用 `RoutingProgress`，Router 仍传入该参数并负责后续阶段选择。
复现范围是打分器本身，不包含 llm-d 的端点发现、指标抓取及完整调度器。
