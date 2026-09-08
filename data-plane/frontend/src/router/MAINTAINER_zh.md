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

请求级共享状态放在 `RouterPipeline::with_customized_context` 中。Router 为每个请求创建一个 context，并在请求结束后释放。联合 E/P/D 实现可以在初始轮读取完整候选快照，把计划中的各阶段目标保存在 context 中，再由 Picker 在每个阶段返回对应候选项。

## 多阶段路由

算法对完整的兼容、健康候选项快照进行评分。Picker 执行前，Router 会将候选项限制到当前执行阶段和已选择的控制器定义 pipeline scope。这样既保持聚合、P/D 和 E/P/D 的执行 ownership，也允许 Scorer 考虑关联阶段的负载。

## 打分契约

各 scorer 使用以下观测和公式：

| Scorer | 输入 | 分数 |
| --- | --- | --- |
| `active_request` | 本地活跃请求数 `count`、候选项最大值 `maxCount` | `count <= idleThreshold` 时为 `1`，否则为 `(maxCount - count) / maxCount * maxBusyScore` |

`active_request` 使用传入 `score` 的全部候选项求 `maxCount`。`idleThreshold` 默认 `0`，
负值归零。`maxBusyScore` 默认 `1`，范围 `[0, 1]`；缺失、null 或超出范围时使用 `1`。
每个已选择阶段持续计数，直到阶段完成或 session 释放。

`active_request` 使用 frontend 按目标和 DP rank 维护的本地预留量，不叠加引擎调度指标或其他 frontend 的请求。
选择目标和预留共用一把锁；路由 session 负责清理，RuntimeBuilder 在 serving snapshot 替换时保留此状态。

空候选集返回空分数列表。数值通过 `RouteScore.preference` 原样传给 Picker，
其余位置和负载字段为零。原有位置策略继续使用字典序。

可选参数配置在 `FrontendService.spec.routerPipeline.scorerParameters` 中，由所选 scorer 在 frontend 启动时读取。
