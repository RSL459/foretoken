<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 主机与流式链路

[English](README.md) | 简体中文

沿请求到达、设备提交、token 解码和客户端交付跟踪工作。模型内核加速后，这些边界中的开销会更加明显。

- [主机与设备调度](host-device-scheduling_zh.md)：区分 GIL 争用、事件循环阻塞、executor 排队与下一步真实依赖。
- [增量文本解码](incremental-text-streaming_zh.md)：理解 Unicode、stop 缓冲、历史保留及大 chunk 的延迟代价。
- [HTTP 背压与取消](http-backpressure-cancellation_zh.md)：沿队列追踪压力和 abort，直到引擎执行与资源释放。
- [NUMA 与多 rank 主机管道](numa-rank-host-pipelines_zh.md)：分开 CPU quota、affinity、分配局部性与 collective 到达偏斜。

图执行见[编译与运行时](../compiler-runtime/README_zh.md)，接收 chunk 与 trace 的解释见[测量与模拟](../measurement-simulation/README_zh.md)。

[全部推理知识](../README_zh.md)
