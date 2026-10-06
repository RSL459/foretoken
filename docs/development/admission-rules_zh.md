<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# 开发准入规则

[English](admission-rules.md) | 简体中文

准入规则控制请求何时进入预处理与执行。框架通过统一接口提供请求信息和当前运行观测。

## 实现并注册规则

实现 `RouteAdmission`，入口为：

```rust
async fn admit(
    &self,
    request: &AdmissionRequest,
    context: &AdmissionContext<'_>,
) -> Result<AdmissionPermit, AdmissionError>;
```

接受请求时返回 `AdmissionPermit`，拒绝时返回 `AdmissionError`。规则可以在这个 future 中等待，框架负责请求总超时和调用方断开后的取消。

提供 `from_parameters(Value) -> Result<Self, String>`，再加入 `algorithm/admission/mod.rs` 的 `declare_router_algorithms!` 列表。规则在启动时完成构造和参数校验。新增公开参数还需更新 FrontendService API 并重新生成 CRD。

最简实现可参考 [allow_all](../../data-plane/frontend/src/router/src/algorithm/admission/allow_all.rs)；需要加权等待和资源预留时，可参考 [concurrency](../../data-plane/frontend/src/router/src/algorithm/admission/concurrency.rs)。

## 使用框架提供的输入

- 请求信息：`AdmissionRequest` 提供模型、操作、候选数、输入与媒体摘要、输出预算、客户端偏好和处理起点。
- 服务上下文：`context.deadline` 是请求总截止时间；`context.service` 承载解析后的身份、服务类别、优先级和延迟目标。当前身份及服务策略值尚未填充。
- 运行观测：通过 `context.state` 查询当前模型可用性、目标健康、负载和容量统计：

```rust
let state = context.state.model_state(
    &request.model,
    std::time::Duration::from_secs(30),
);
```

输入 token 数区分精确、估计和未知；输出上限与预计生成量分别表达。等待后重新查询运行观测，即可使用当前值。

完整字段和单位见 [AdmissionRequest](../../data-plane/frontend/src/router/src/algorithm/admission/request.rs) 与 [AdmissionContext](../../data-plane/frontend/src/router/src/algorithm/admission/context.rs) 的类型说明。

## 返回与释放资源

直接放行时返回 `AdmissionPermit::default()`。需要预留资源时，实现 `AdmissionReservation`，并用 `AdmissionPermit::new(...)` 包装。

`split_one()` 将一个已预留单位转交给批次子请求，reservation 被丢弃时释放剩余资源。框架让执行许可覆盖预处理和请求完成；规则的等待资源随 admission future 持有，从而在取消时释放。

排队期间持有 `context.queue.begin_wait()` 返回的 guard，等待结束时释放。框架会将等待时长与最终准入结果一起记录。

资源上报、入口和模型就绪要求可通过以下方法实现：

| 方法 | 用途 |
| --- | --- |
| `capacity()` | 为准入看板提供有限的工作并发、队列和驻留上限。 |
| `try_reserve_request()` | 在读取请求体前预留一个 HTTP 驻留名额，许可随响应体持有。 |
| `requires_ready_runtime()` | 要求模型准备好后再准入生成请求。 |
| `close()` | 关闭时唤醒等待中的请求。 |
