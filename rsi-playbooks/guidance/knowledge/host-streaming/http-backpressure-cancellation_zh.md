<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# token 流的 HTTP 背压与取消传播

[English](http-backpressure-cancellation.md) | 简体中文 · [主机与流式输出](README_zh.md) · [推理知识](../README_zh.md)

## 稳定生成也可能变成突发到达

一条流经过引擎输出、解码事件、应用响应、代理缓冲、传输窗口和客户端解析等多级队列。一次 write 或 enqueue 成功，只说明本地某层接收了数据，不说明用户已经收到。因此，稳定 token 产出与客户端事件成簇到达，可以来自缓冲或慢消费者，不能单凭这一现象认定推理变慢。

SSE 是文本分帧协议，不保证一个 token 对应一个包。UTF-8 行会累积成事件，遇到空行才分发；一次网络读取既可能只有半个事件，也可能含多个事件。注释可维持连接，却不产生应用内容。TCP 包、HTTP chunk、SSE 事件和模型 token 是不同单位。

## 背压实际传到了哪里

设队列占用为 B 字节、生产速率 p、消费速率 c，在双方持续运行时，dB/dt = p − c。如果 p > c，无界队列会把不匹配藏起来，直到内存增长或进程失败；有界队列最终会挂起或拒绝生产者。初始占用 B₀、容量 K 时，恒定速率下约在 (K − B₀)/(p − c) 后饱和。这些都是局部速率，下游的另一个队列可能先吸收数据，让反馈更晚发生。

Envoy 文档通过缓冲上限和暂停读取描述流控传播。HTTP/2 同时有 stream 与 connection 级约束：单流暂停，与多个流共用受限连接，不是同一问题。Streaming filter 可以增量转发大响应，要求完整 body 的 filter 则必须缓冲。增大缓冲可平滑突发，却延后反馈并增加内存，不能修复持续的速率不匹配。

应用结构决定最后能传到的边界。若响应 body 惰性拉取生成流，下游暂停读取可能阻止上游继续被 poll；若独立任务不断接收引擎输出到无界 channel，socket 背压就不会停止生成。有界 channel 可以限制主机内存，但引擎仍可能继续占用资源。不能让设备调度无限期受每个慢 socket 阻塞，资源策略和传输流控各有职责。

## 断开连接，不等于取消完成

HTTP 连接关闭、应用停止迭代、发出 engine abort，以及释放 KV block，是不同时间点。服务需要跨这些阶段保留请求身份与 ownership。Abort 应答可能只表示控制消息已接收，不能证明在途设备计算已经停止；已提交内核或后续流水线步骤，可能在 scheduler 感知取消前完成。

若取消后仍以每秒 r 个 token 继续运行 Δ 秒，浪费工作约为 rΔ 个 token，KV 内存在清理前也持续占用。频繁断开会降低健康请求的 goodput，即使成功请求的平均延迟看起来没变。只测客户端 timeout，无法看到这一时间段。

Foretoken 已有可取消输出流的 ownership、显式 model-server abort，以及 idle timeout 清理。SSE heartbeat 维持传输连接，但不重置 backend idle 或请求 deadline。仍需研究的是具体部署能否让背压与取消及时穿过全部队列和引擎 rank。

## 有区分力的实验

比较持续读取的客户端与收到相同应用事件后暂停读取的客户端，固定输入和输出预算，观察队列占用、驻留内存、引擎 token 产出、客户端节奏，以及共享进程或 HTTP/2 连接的其他请求。内存增长但引擎节奏不变，提示解耦缓冲；内存稳定且上游 poll 暂停，说明有背压传播，但尚不能证明引擎停止生成。

随后分别在 prefill、普通 decode 和写阻塞时断开。把客户端关闭到 abort 发出、engine terminal、资源释放的时间分开测量，并检查其他请求是否停顿、资源是否恢复。正常结束时收到 terminal marker，不能证明一个永远收不到它的断开路径也正确。

最后用相同 payload 比较直连和代理。如果只有代理后到达成簇，引擎输出仍稳定，应检查 filter、flush 边界和传输窗口。Heartbeat 处理连接空闲，不能保证内容及时送达，也不能保证 backend 取消正确。

## 来源与核验

核验日期为 2026-10-14。队列式是解释模型，不是 Foretoken 实测。

- [WHATWG SSE 规范](https://html.spec.whatwg.org/multipage/server-sent-events.html)：UTF-8、逐行解析、空行分发、注释和重连。EventSource 的重连语义不能直接当成所有 LLM HTTP 客户端的自动请求重放。
- [Envoy 流控文档](https://www.envoyproxy.io/docs/envoy/latest/faq/configuration/flow_control)：listener、cluster、stream 上限及缓冲 filter，核验当日读取的官方动态文档。
- [Foretoken 共享流处理](../../../../data-plane/frontend/src/server/src/api/stream.rs)与[HTTP model facade](../../../../data-plane/frontend/src/llm-facade/src/http.rs)：在 `e6ae3df6` 核实 heartbeat、idle 清理，以及 abort 接收与最终终止的职责区别。
- [Foretoken 指标定义](../../../../benchmarks/docs/metrics_zh.md)：客户端分片间隔和成功请求计时，不暴露 backend 资源释放时间。
