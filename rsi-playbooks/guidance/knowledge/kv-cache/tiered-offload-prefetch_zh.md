<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 分层卸载与异步预取

[English](tiered-offload-prefetch.md) | 简体中文

只有读取缓存暴露在关键路径上的时间小于被省掉的计算，命中才有价值。主机内存、SSD 和远端存储扩大了容量，却可能因为暂存、排队和等待完成，让高命中率服务的首 token 延迟反而更差。

## 搬运与计算的临界点

普通稠密注意力每个 rank 的 KV 字节量可近似为 `D = 2 L N Hkv d b`：`L` 是层数，`N` 是 token 数，`Hkv` 是本 rank 实际保存的 KV 头数，`d` 是头维度，`b` 是每元素字节数。复制 KV 头、MLA 和混合模型应按真实缓存形状计算。32 层、8 个 KV 头、头维度 128、BF16、8,192 token 的未分片缓存约为 1 GiB。假设有效带宽为 20 GiB/s，单纯传输就需要 50 ms，尚未包括查找、缺页、打包和接纳。

可以先用下式拆解：

`T_hit = T_lookup + T_queue + T_stage + max(0, T_copy - T_overlap) + T_remaining`。

比较对象是相同 token 的完整 prefill，而不是一个孤立 attention kernel。有效带宽应在并发加载和解码时实测，不能用链路标称值代替。异步提交不等于重叠执行；`T_overlap` 只计真正与搬运同时进行的有用计算。

逐层流水先加载第 0 层，在该层执行剩余计算时加载第 1 层，下一层尚未就绪才等待。稳定阶段接近 `max(T_layer_copy, T_layer_compute)`，仍有启动与排空成本。先完整加载前缀再执行，重叠条件不同；SSD 经主机内存暂存又增加一层流水，主机内存带宽饱和还会让名义上独立的搬运串行化。

预取同时改变数据寿命：查找并保护源对象，预留目标缓冲区，提交读取，接纳完成数据，再释放相应锁。过早预留会占用原本能保存热点数据的容量。取消请求也不能在搬运仍持有目标时将其重新分配；修改生命周期前，必须确认 adapter 的实际完成语义。

## 当前已有实现

[2026-10-14 快照](README_zh.md#来源快照)中的 LMCache 已有多层查找与预取。[controller 实现](https://github.com/LMCache/LMCache/blob/4d69cdc43ac9bab9c0c1cd5cac380c480cb32224/lmcache/v1/distributed/storage_controllers/prefetch_controller.py)及[设计说明](https://github.com/LMCache/LMCache/blob/4d69cdc43ac9bab9c0c1cd5cac380c480cb32224/docs/design/v1/distributed/storage_controllers/prefetch_controller.md)覆盖 L1 读取锁、L2 查找加锁任务、策略规划、目标预留和结果接纳。当前实现将位置选择解析到一个 L1 manager，不能据此声称支持任意多 L1 放置。

Dynamo KVBM 的[onboarding](https://github.com/ai-dynamo/dynamo/blob/7708f041a965e35374af976ab8ad610b9537e3bc/lib/kvbm-engine/docs/onboarding.md)包含 HBM、固定页主机内存、SSD 和对象存储，以及远端搬运前的 SSD 到主机暂存。[offload 流水](https://github.com/ai-dynamo/dynamo/blob/7708f041a965e35374af976ab8ad610b9537e3bc/lib/kvbm-engine/src/offload/pipeline.rs)区分策略、组批、前置条件与传输。Mooncake 提供注册内存上的异步搬运，但不证明某个引擎具有逐层预取；vLLM connector 还需沿调度器分配与 worker 消费路径确认。

## 适用条件与可区分实验

重复长上下文、重算昂贵、带宽和主机容量充足时值得研究。短输入、低复用、共享 PCIe 争用和主机内存紧张可能让结果反转。保存完成 KV 本身也消耗带宽，测量必须包含卸载、淘汰与加载流量。

局部实验用相同大小的真实缓存张量，对照同步加载、无计算的异步提交、带代表性计算的逐层加载，扫描大小、存储层和预取距离。记录提交、就绪、逐层等待、队列停留、RSS、固定页字节与实际重叠。只有第三组变快，说明收益来自重叠，而不是拷贝本身更快。并发升高后命中延迟变差、有效载荷带宽却不变，优先解释为排队，而非原始带宽不足。

服务验证保持请求一致，对照冷 prefill、GPU 命中和各低层命中，并改变复用间隔。查看 TTFT 分位数、无关解码请求的延迟、驻留量及搬运字节。剩余空间是争用条件下的预取距离和接纳选择。

[KV 缓存](README_zh.md)
