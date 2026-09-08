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

## `token_load`

评分公式和默认值对应 [llm-d](https://github.com/llm-d/llm-d-router/blob/7de00e5452818546815417aee2d6c68d2c2ff323/pkg/epp/framework/plugins/scheduling/scorer/tokenload/token_load.go)。
先进行有符号 token 加法，再转换为 `f64`。总负载非正时得一分，否则为
`1 - min(load, threshold) / threshold`。请求贡献包含索引内未命中 token 和不满完整块的尾部。
输出 token 估算关闭。选择与预留共用锁；路由会话在首个响应、阶段结束或丢弃时释放贡献。
RuntimeBuilder 在运行时版本切换期间保留本地负载状态。

`RouteScore.preference` 直接保留浮点分数，不进行整数化。Foretoken 负责指标生产、
端点可选性和同分选择。`scorerParameters` 经 CRD 和控制器环境变量传到 Frontend，
由所选 scorer 在启动时读取和校验。
