<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 关键路径、重叠与容易误读的 Trace 总量

[English](trace-critical-path.md) | 简体中文 · [测量与模拟](README_zh.md) · [推理知识](../README_zh.md)

## 时长相加不等于经过的时间

CPU 算子可以异步提交设备内核后提前返回，两个 stream 可以同时执行，父 span 包含子 span，collective 内还可能在等待其他 rank。不清楚依赖就把时长相加，既不能得到请求延迟，也不能得到可实现的加速空间。

两个区间的忙碌墙钟时间是 `|A∪B|=|A|+|B|−|A∩B|`。求并集能排除交叠，却仍不能解释因果。较长的旁路任务可能占用资源但不延迟目标请求；很短的启动或同步也可能因所有后续都依赖它而处于关键路径。

## 从目标事件逆向还原依赖

将操作作为带时长的节点、依赖作为边，资源充足时，节点 v 的完成时间为 `c_v = d_v + max_{u→v} c_u`，其中 d_v 是自身时长，c_u 是前驱完成时间；无前驱节点的完成时间为就绪时间加 d_v。此时最长的必要因果路径决定目标完成事件。共享设备争用会引入简单依赖图未表达的调度条件，因此还要保留实际竞争的 stream 与资源信息。

例如 4 ms 计算与 3 ms 通信重叠，随后执行依赖同步的 1 ms 阶段，理想总时长是 5 ms，不是 8 ms。把通信缩为 2 ms 不改变总时长；把计算缩为 2 ms 则变成 4 ms。这是示意依赖图；真实交叠还可能通过 HBM 或 SM 争用同时拉长两项。

目标事件也重要：首个引擎 token、首个可见文本、最后 HTTP 事件，以及取消后的 KV 释放，各有不同关键路径。设备完成后的 CPU 调度会影响可见文本，却不影响模型内核。只抓模型进程可能完全漏掉前端解析、网络队列和客户端调度。

## 区分等待与执行

设备开始可能晚于主机 launch，因为其他 stream 占用设备或事件依赖尚未满足。较长 CUDA API 调用可能意味着同步、争用或剖析开销，不是内核慢；短 launch 后出现设备空白，也可能是主机管道别处延迟了提交。

跨 rank 分析需要 collective 身份、进入时间与前序工作。早到 rank 可能一直等晚到 rank；累加所有 rank 的通信时长会重复统计同一次会合，把主机失调度误判为网络搬运。跨节点区间相减前，需时钟同步或共同的因果参照。

嵌套 span 还应区分 inclusive time 与 self time，后者排除子工作，但仍可能包含阻塞等待。CPU 栈采样估计被采样时耗时的位置，不直接指出哪个操作延迟设备。保留进程、线程、rank、stream 和 correlation 身份，才能连接这些观察。

## 检验依赖解释的实验

选择重复的稳态 step，标记最早能释放后继的事件。比较算子时长总量、设备忙碌区间并集和 step 实际时长。总量大而并集小，说明有重叠或嵌套；并集小而 step 长，说明有未覆盖的主机工作、等待或 trace 缺口。

保持形状和负载，单独改变一个阶段。若缩短表面热点却不提前后继或端到端完成，它可能被隐藏、位于旁路，或收益被争用抵消。若改变主机 core 提前了提交而不改变内核时长，暴露的是调度成本。这类干预比单纯按累计耗时排序更能区分假设。

图级 capture 跟踪开销低，却看不见内部依赖；节点级跟踪更细，但可能扰动很短的 decode step。先比较剖析与普通运行的节奏，再相信细小间隙；启动、编译、图捕获也应与稳态分窗。

Foretoken 的 PyTorch、Nsight 和 mcTracer 捕获范围不同，不能视为可互换的时间账本。使用实际进程／设备信息和工具后端，不能用累加现有事件补出未支持的关联。SQL 区间分析能让交叠计算可重复，但时间接近不自动构成依赖。

## 来源与实现状态

核对日期：2026-10-14；数值例子为示意调度。

- [Nsight Systems 指南](https://docs.nvidia.com/nsight-systems/UserGuide/index.html)：CPU／CUDA 关联、进程范围、图粒度、开销及跨节点时钟。
- [Perfetto Trace Processor](https://perfetto.dev/docs/analysis/trace-processor)：slice 的时间戳、时长与查询；区间查询本身不识别因果边。
- [SGLang overlap utilities](https://github.com/sgl-project/sglang/blob/e9400c5a8f3a0d0312a37aecef694f5edfd69341/python/sglang/srt/managers/overlap_utils.py)：2026-10-13 revision 的发布、设备事件、异步复制和消费者 fence。
- [Foretoken 剖析指南](../../../../benchmarks/docs/profile/README_zh.md)：以 `e6ae3df6` 核对捕获准备、产物保存和独立测速。
