<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 减少设备空闲间隙：重叠主机准备与设备执行

[English](reduce-device-idle-gaps-through-host-device-execution-overlap.md) | 简体中文 · [主机与流式输出](README_zh.md) · [推理知识](../README_zh.md)

## 内核很快，设备为什么仍在等待

一次解码的设备计算可能很短，主机却仍要选择请求、分配元数据、构造输入、提交内核、接收结果并准备下一步。加快内核会暴露这些成本，不会自动消除它们。同样，HTTP handler 写成 `async`，也可能在下一次挂起之前同步执行分词或解析。此时，即使其他 CPU 核空闲，同一事件循环中的连接仍会一起等待。

这里有三种不同的约束。普通 Python 字节码线程受 GIL 约束；asyncio 事件循环采用协作式调度，同步操作即使在底层释放 GIL，也会占住当前循环；设备的下一步输入还可能依赖刚生成的 token。把工作放到线程池只能改变前两种执行边界，不能消除第三种数据依赖。

## 重叠执行首先要改变依赖关系

设主机准备耗时 H、设备执行耗时 D，完全串行的稳态步骤间隔是 H + D。若下一步准备可以与当前设备计算重叠，理想间隔接近 max(H, D)，还要加上未被覆盖的同步和结果处理成本。这描述的是流水线节奏，不是新请求的完整延迟；流水线填充、排队和结果交付仍计入请求耗时。

例如 H = 2 ms、D = 3 ms，串行间隔为 5 ms，理想重叠间隔为 3 ms。但如果元数据需要当前输出，就必须通过设备侧接力、延迟结算或不同调度决策解决依赖，才能接近这个下界。增加线程池本身做不到这一点。

引用版本的 vLLM 源码中，`AsyncScheduler` 已经用 output placeholder 记录在途步骤，收到输出后再结算，并处理抢占后的过期结果。SGLang 的 overlap 工具按请求索引发布设备状态，记录事件，再由后续输入在正确的同步点消费；仅在消费者需要 CPU 元数据时做主机拷贝。事件顺序与 tensor 生命周期属于这一实现边界，不能仅因一次等待昂贵就删除它，否则下一批可能读到旧状态。

## 转移 CPU 工作，不等于减少 CPU 工作

把阻塞操作移出事件循环，可以恢复 HTTP 响应性，却未必降低 CPU 总需求，还可能增加执行器排队、序列化和唤醒成本。释放 GIL 的原生 tokenizer 可能利用线程并行；以 Python 为主的解析器，主要收益可能只是让事件循环不再被占住。独立进程可以分别运行 Python，但增加 IPC 和状态归属成本。

自由线程 CPython 也不是可直接替换的推理优化。Python 3.14 文档区分构建是否支持与运行时 GIL 是否启用；不兼容扩展可能重新开启 GIL。即使去掉 GIL，也不会让事件循环抢占同步 callback，更不会去掉原生库自己的锁。需要核对真实引擎依赖及单线程执行成本。

引用版本的 vLLM renderer 中，非流式 derender、普通流式 detokenization 和带解析的流式路径都已有执行器包装。仍值得研究的是执行器饱和、parser replay 成本，以及输入分词与输出渲染之间的竞争。

## 如何区分这些原因

固定模型、实际输出 token 数、batch 组成和 graph 模式，先关联设备步骤间隔、主机提交时间和结果可用时间。GPU 空隙若跟随 scheduler 工作，应检查主机与设备依赖；若引擎节奏稳定而多个 HTTP 流同时卡住，应检查事件循环和执行器。

随后只改变一种资源：隔离主机核心、改变执行器并发，或分开请求输入与输出处理。把执行器等待时间与操作本身耗时分开，并记录循环延迟。循环更响应、输出吞吐却不变，说明是隔离收益，不是工作量减少。更多线程只增加 runnable 等待而不减少 GPU 空隙，则更像资源竞争或 GIL 限制。最后用不带 profiler 的普通运行比较：流水线改动可能提高吞吐，也可能增加首响应或取消延迟。

## 参考

- [Python 3.14 asyncio 开发文档](https://docs.python.org/3.14/library/asyncio-dev.html)与[自由线程文档](https://docs.python.org/3.14/howto/free-threading-python.html)：协作式调度、执行器与扩展兼容性。
- [vLLM AsyncScheduler](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/v1/core/sched/async_scheduler.py)与[online renderer](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/renderers/online_derenderer.py)：源码版本日期为 2026-10-13。
- [PR #49396](https://github.com/vllm-project/vllm/pull/49396)：2026-07-22 合并。[Issue #57350](https://github.com/vllm-project/vllm/issues/57350)：状态为 closed，上述源码包含流式执行器路径。
- [SGLang overlap 工具](https://github.com/sgl-project/sglang/blob/e9400c5a8f3a0d0312a37aecef694f5edfd69341/python/sglang/srt/managers/overlap_utils.py)：版本日期为 2026-10-13，不同 backend 的同步方式并不相同。
