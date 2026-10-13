<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 排空与状态迁移

[English](drain-and-state-migration.md) | 简体中文

## 问题与机制

移除 decode worker 可能打断数分钟生成，并丢失暖 KV。缩容要区分停止新工作、完成已接受工作、移动活跃请求和退役可复用缓存。减慢副本递减不等于 drain 协议，持久化前缀也不等于可以续跑请求的 checkpoint。

自然排空按以下顺序执行：关闭准入，撤回路由，确认路由观察者安装了撤回状态，等待已接受请求完成，再释放资源。先关闭准入可保护滞后 router。有限 deadline 避免永远无法退役，但过期代表排空未完成，不是零损失成功。

在线迁移还有更多要求：预留兼容 destination，复制已有 KV，传输已生成 token 位置与引擎请求状态，追赶复制期间新增的状态，在一致边界短暂停顿，转移 ownership，收到确认后释放 source。Sampling RNG、speculative 状态、混合 cache、在途 collective 都可能影响续跑。用相同 prompt 发起新请求属于 replay，不是透明迁移。

例如一条生成还需 120 秒，自然 drain 保留请求，但继续占 GPU 120 秒。4 GiB 通过 25 GB/s 有效路径，payload 下界约 172 ms，尚未计同步与增量追赶。只有 destination 余量与暂停 SLO 允许时，迁移才可能更快释放容量，否则保留 source 更合适。

## 硬件、模型状态与成本

必须使用真实 checkpoint、KV dtype、TP/DP 配置。BF16 GQA KV 与 MLA／recurrent state 不同，权重兼容也不证明内部 cache layout 兼容。跨加速器需要受支持的 connector 和数值／runtime 语义。迁移流量会争用推理链路，可能恰在合并负载时拖慢剩余 worker。

存储 owner 持续存在时，共享 prefix entry 可以在 worker 消失后保留，但 active decode 还需要当前进度和生命周期。当前请求全部完成后，本地 cache 丢失仍会降低未来命中。应统计保留 GPU 时间、搬运字节、重复 prefill、排空后的尾延迟，不只看 Pod 多快消失。

## 当前实现与证据

核对日期为 2026-10-14。Foretoken 的[Group drain owner](../../../../control-plane/controllers/modelgroup_drain.go)关闭 model-server 准入，检查每个存活 frontend 的 snapshot generation，观察 running request，在完成或记录 timeout 后释放 finalizer。[请求工作流](../../../../data-plane/frontend/src/server/src/runtime/workflow.rs)保留 P/D、E/P/D 跨阶段清理。这是已有退役／取消机制，不是在线 KV 迁移。

Dynamo 的[graceful-shutdown 工具](https://github.com/ai-dynamo/dynamo/blob/b2078c3127bd2ad3a70a6d39beeb06ff2d0a67fd/components/src/dynamo/common/utils/graceful_shutdown.py)先注销 endpoint，等待传播，再调用可选 drain／cleanup callback，各自有限 timeout。工具本身不跟踪或迁移 active request，取决于 worker callback。

AIBrix 的[drain helper](https://github.com/vllm-project/aibrix/blob/d0500b0399cf35ad0bf95d073faa83c23308f463/pkg/controller/drain/drain.go)给调用者指定的 Pod 添加注解，在 timeout 后删除，也支持取消。在此 helper 中完成条件是 timeout，不验证引擎请求归零。Production Stack 的[router 代码](https://github.com/vllm-project/production-stack/blob/4e076e8de3698a3729b575e3a5ade65ffbb929cf/src/vllm_router/routers/routing_logic.py)刷新 endpoint／路由资源，该文件未提供在线迁移。结论应限定到实际核对的实现。

2026 年 [TRE 论文](https://arxiv.org/html/2609.29160v1)使用 A100 40GB、7B/8B/14B hot-switch 原型，未指定 dtype。报告秒级 sleep/wake，但 drain 失败时重发工作而非迁移 KV；这些时间不证明活跃生成的透明交接。

## 实验与剩余问题

先模拟缩容时剩余生成时间和 destination 显存，以实测复制速度比较自然排空、deadline 终止和迁移。加入长尾输出与相关缩容；平均剩余时间会低估保留容量。

真实服务在持续流量与长 streaming response 中退役 worker，记录准入关闭、路由确认、最后接受请求、最终完成、资源释放。加入取消、timeout、滞后 frontend snapshot，检查客户端连续性和后端清理。只在确实支持的 backend 上评估迁移，同时验证输出状态与 source/destination ownership。尾延迟感知 victim 选择、迁移感知合并、失败后的共享状态清理仍待研究。缓存状态见[KV 缓存](../kv-cache/README_zh.md)。

[返回扩缩容与放置](README_zh.md)
