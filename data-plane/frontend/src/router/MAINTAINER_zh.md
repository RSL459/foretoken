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

## 打分契约

`token_load` 打分器使用以下观测和公式：

| Scorer | 输入 | 分数 |
| --- | --- | --- |
| `token_load` | 在途 token 与当前请求未缓存提示词 token 之和 `load` | `load <= 0` 时为 `1`；否则为 `1 - min(load, threshold) / threshold` |

Token Load 先进行有符号整数加法，再转换为 `f64`。`threshold` 为 `queueThresholdTokens`
（默认 `4194304`）；配置为非正值时使用默认值。请求贡献包含索引内未缓存 token 和提示词
尾部不足一块的 token；缓存观测不可用时，整个提示词都按未缓存计算。不估算输出 token。
计数由每个 Frontend 副本按目标和 DP rank 独立维护，不叠加引擎 scheduler gauge。
Aggregate、Prefill 和 Decode 在派发前为选中目标预留未缓存提示词 token；首个响应释放 token，
阶段结束或会话释放时清理剩余贡献，也覆盖派发失败的情况。

选择与预留共用一把锁，使并发请求能看到已选请求的本地负载。路由会话负责清理预留，
RuntimeBuilder 在服务快照更新之间保留这份负载状态。

`RouteScore.preference` 直接保留浮点分数，不进行整数化。Foretoken 负责指标生产、
端点可选性和同分选择。`scorerParameters` 经 CRD 和控制器环境变量传到 Frontend，
由所选 scorer 在启动时读取和校验。
