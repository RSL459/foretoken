<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# 开发准入规则

[English](admission-rules.md) | 简体中文

准入规则决定请求能否进入预处理与执行。框架统一提供请求摘要、可信服务约束和当前运行观测，规则不需要自行解析 HTTP、加载 tokenizer 或寻找后端客户端。

## 实现规则

在 Router 的 `algorithm/admission` 目录实现 `RouteAdmission`，请求级入口为：

```rust
async fn admit(
    &self,
    request: &AdmissionRequest,
    context: &AdmissionContext<'_>,
) -> Result<AdmissionPermit, AdmissionError>;
```

接受整个请求后才返回许可。无条件放行可直接返回 `AdmissionPermit::default()`；需要占用资源的规则返回持有预留资源的许可，拒绝则返回 `AdmissionError`。等待由这个 future 负责；future 被丢弃时，应移除等待者并归还排队占用。

实现 `from_parameters(Value) -> Result<Self, String>`，再加入阶段的 `declare_router_algorithms!` 列表。统一注册机制按名称选取规则，并在启动时完成构造。必填容量在状态交给运行时之前校验，不自行补一个默认值。新增公开配置字段还需更新控制面 API 的明确映射并重新生成 CRD。

`allow_all` 是默认规则；`concurrency` 展示了加权 FIFO、有限驻留请求和许可生命周期的实现。

## 使用统一请求摘要

`AdmissionRequest` 只携带轻量事实，不保留请求正文、token ID 数组、tokenizer 或执行用的运行时快照。

| 输入 | 含义与当前来源 |
| --- | --- |
| `model`、`operation`、`api` | 请求的逻辑模型、操作和协议适配器。内部调用可不提供 `api`。 |
| `request_id` | 可用时填写前端生成的标识。补全批次与首个子请求共用标识；CPU 操作可不提供。 |
| `inputs` | 每个 prompt 或聊天会话一份摘要，尚未按输出候选展开。 |
| `candidates_per_input`、`units()` | 实际生成的候选数，包括 `best_of` 中不会全部返回的候选。`units()` 返回整批权重，溢出时为 `None`。 |
| `inputs[].text_bytes` | 消息内容的 UTF-8 字节数，包含 reasoning 和已有工具调用参数字符串；不含工具 schema、模板展开和编码媒体。只有 token IDs 时不提供。 |
| `inputs[].tokens` | 明确区分 `Exact`、`Estimated`、`Unknown`。已提供的 token IDs 可准确计数；普通文字和聊天在预处理前仍为未知。字节数不是 token 估计。 |
| `inputs[].messages`、`media` | 实际消息及媒体项数量，不根据模型能力推断请求是否带图。 |
| `output.requested_max_tokens` | 客户端要求的每个候选的生成上限。 |
| `output.execution_max_tokens` | 协议转换已确定的执行上限；尚未解析的模型默认值仍为空。仅回显的补全可能请求零输出，而执行层使用一个 token。 |
| `output.expected_tokens` | 可选的每候选预计工作量，不是停止上限。当前没有预测器，保持为空。 |
| `requested_priority`、`stream` | 客户端调度偏好和响应模式，不代表获得了可信服务等级。 |
| `received_at` | 前端处理的单调时钟起点，同批候选共用。 |

Tokenization 和 detokenization 没有生成输出预算，不能把处理器内部用于复用流程的 `max_tokens` 当成用户请求的生成量。已知 token 数应表示完整输入成本；多模态输入中，部分文字 token 数不能冒充完整成本。

生成和 tokenization 协议由 server 的准入适配器统一转换。新增协议时补充这层映射，不让每种规则再认识一遍原始请求格式。

## 读取服务约束与运行观测

`context.deadline` 由原始处理起点和配置的请求超时确定。运行时用它限制整个准入过程，无入口资源预留的规则也受此约束。排队策略可以缩短等待时限，但不能重新开始请求预算。

`context.service` 单独容纳可信身份、配置解析的服务类别、优先级和延迟目标。规则使用优先级时，配置值越大越优先；客户端 priority 仍只是原始偏好。TTFT 和完成延迟从 `received_at` 起算，TPOT 表示首 token 之后的平均解码耗时目标。当前还没有可信身份传递或服务目标解析器，这些可选值保持为空。不要用客户端 header、`service_tier`、cache salt、虚构的匿名租户或零值 SLO 替代。后续由运行时边界的可信解析器填入，规则接口不必跟着改变。

通过统一入口查询模型和目标状态：

```rust
let state = context.state.model_state(
    &request.model,
    std::time::Duration::from_secs(30),
);
```

每次调用读取当前 serving generation 和本地遥测缓存，不在请求路径发起网络查询。结果区分尚未发布运行时，以及模型未知、准备中、就绪、不可用等状态，并提供上下文长度上限、目标信息与健康状态、已有统计、当前前端的逐 rank 路由预留。引擎遥测和前端预留分别表达，不相加冒充同一种负载。

返回的是轻量观测值，不是执行绑定。等待后应重新查询，不在队列中保留后端或 tokenizer。`observed_at` 是读取这份视图的时间；目标统计保留自己的采集时间和观测窗口。缺失遥测仍为空，观测到容量不等于已经预留了后端容量。

## 转移许可所有权

HTTP 和运行时只持有不透明的 `AdmissionPermit`。规则用自己的 `AdmissionReservation` 承载资源，丢弃时释放剩余占用。`split_one()` 将已经预留的一个单位转给子请求，不重新申请容量或再次增加计数；父许可继续负责尚未转出的部分。

子请求许可覆盖预处理和完整 P/D、E/P/D 执行，不在返回 HTTP 响应头、首 token 或单个阶段完成时提前释放。客户端断开后，不可取消的预处理仍须持有许可直到实际结束。

需要限制入口驻留请求时，实现非阻塞的 `try_reserve_request()`。许可跟随响应体，包含慢客户端造成的背压；无资源许可保持原有无限流 HTTP 行为。

规则若要求模型先准备好再进入准入等待，设置 `requires_ready_runtime()`。校验和就绪监听仍由运行时负责，规则不将模型状态留在自己的队列。关闭时，`close()` 唤醒等待者，但不撤销运行中请求已经持有的许可。

## 与目标选择阶段的关系

| 阶段 | 主要输入 | 输出 |
| --- | --- | --- |
| Admission | 预处理前的请求事实和实时 context | 持有资源的许可，或明确的拒绝原因 |
| Filter | 预处理后的请求、候选目标、KV 查询和路由进度 | 保留的候选索引 |
| Scorer | 过滤后的候选及观测 | 分数和可选的选中后状态更新 |
| Picker | 带分数的候选及路由进度 | 一个候选索引 |

Admission 复用算法注册方式，不复用已经分词的 `RouterRequest`。目标选择仍归后续阶段，HTTP 状态码仍由现有协议适配器转换。

许可所有权参考 [Tokio owned permit](https://docs.rs/tokio/latest/tokio/sync/struct.OwnedSemaphorePermit.html) 和 [Tower 并发 readiness](https://github.com/tower-rs/tower/blob/tower-0.5.2/tower/src/limit/concurrency/service.rs)；未处理请求与 token 预算的区分也可参考 [llm-d 请求接口](https://github.com/llm-d/llm-d-router/blob/v0.11.0/pkg/epp/framework/interface/requesthandling/types.go)。这些是设计参考，不是新增运行依赖。
