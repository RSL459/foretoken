<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Adapter 驻留悬崖与热切换生命周期

[English](elastic-adapter-residency.md) | 简体中文 | [多模型与适配器](README_zh.md)

## 为什么一次缓存 miss 会拖慢其他租户？

动态加载和 LRU 驱逐已经存在，但活跃 adapter 数超过 GPU slot 后，服务未必平滑退化。ICML 2026 的 CLIMB 研究驻留悬崖：必须获取的 adapter 会阻塞共享执行，连续 miss 进一步放大尾延迟，而不只是线性增加一点开销。新的问题是驻留与入口排队如何共同影响所有请求，不是能否实现热加载。

adapter 缓存还与 KV 争内存。多留几个 slot 可以减少 miss，却可能缩小并发上下文容量。rank、target module 不同，slot 数不能准确表达代价，真正要看分配的 buffer 字节。

## 一次切换和一次入口决策

当前 SGLang 内存池先使用空 slot，满后选 victim，排除当前批次需要的 adapter 与 pinned adapter。复制兼容权重、更新 UID 到 slot 的映射，并清空缺失 module 对应的数据，避免沿用旧 adapter 更新。移除 adapter 会清理 buffer；仅基础模型的 graph replay 不能读到残留低秩权重。TP 各 rank 必须保持 slot 分配一致。

CLIMB 公开 artifact 将 `gate_rr` 标为主策略。已读实现维护活跃 adapter 集合与 in-flight 工作：删除空闲项，优先用 VIP adapter 填容量，再接收 background，最后从符合条件的活跃 adapter 中选最早请求。VIP backlog 达到容量时暂停接收 background；两类 adapter 各有 round-robin 下标。实际引擎执行与确认设备驻留不在该策略文件中。

例如四个 slot 对应八个被请求的 adapter，不加选择地交给引擎可能不断触发换入。把尚未活跃的后台请求留在入口可以减少影响紧急请求的抖动，却没有消除后台等待。端到端延迟必须把入口队列算进去。

每个适配线性层的原始权重约为 b r(h+o) 字节，尚不含分片和 padding。同层 rank 128 比 rank 8 原始 A/B 字节多十六倍；按最大 rank 预留的池又可能远大于当前实际 tensor 字节。

## 可用性、精度与约束

CLIMB artifact 公开策略代码、整理后的论文数据、负载配置和 GPU rerun wrapper。wrapper 还依赖另行提供的完整 serving harness，不是可独立运行的生产实现。合成 rank-128 adapter 只复现驻留压力，没有任务训练质量。真实比较要另取兼容已训练 LoRA、基础 checkpoint、target module、scale 和 tokenizer 信息。

SGLang 已有 pinning、LRU/FIFO、CPU adapter 数量限制与 overlap loading；overlap 可以减少显露的复制时间，也可能限制多 adapter prefill 组批。vLLM 已有 runtime load/unload/replacement；TensorRT-LLM 已有 host/device cache。这些是复用设施，不是新候选。

记录实际 FP16/BF16 buffer 和 pinned-host 占用，基础模型量化不会自动把所有 adapter buffer 减半。PCIe、host pinning、设备支持决定切换成本。预取最终不用的 adapter 会挤走有用状态或争带宽。原地替换需要明确版本与生命周期边界，避免活跃请求混用新旧权重。

## 实验与后续空间

让被请求 adapter 数跨过驻留容量，同时独立改变 rank、突发与热度翻转。固定内存预算，比较普通驱逐、pinning 部分 adapter、驻留感知入口。保持 adapter 语义，不能为了命中率把租户换到另一个模型。

测冷暖 TTFT、engine-only 与端到端 TTFT、slot 占用、host/device 字节、miss、实际复制、阻塞 iteration、KV 容量、队列年龄和分流量类别 SLO goodput。保留低频 background，报告最长等待与完成数。活跃请求期间取消或替换 adapter，观察生命周期。

引擎尾延迟下降、入口尾延迟等量上涨，说明只是搬了等待；slot 增多先改善后被 KV 压力抵消，说明需要选择内存工作点。剩余研究在已有 loader 上测量入口与驻留协同、负载感知预取、rank-sensitive 内存核算。

## 来源与核对状态

核对日期：2026-10-14。

- [CLIMB，ICML 2026](https://proceedings.mlr.press/v306/zhang26dg.html)：机制与 artifact 入口；[artifact](https://github.com/maxsignalll/CLIMB_artifact/tree/a96f7f3cb65b9bb86dec3d0a1f0c511705f05360) README、`policies/gate_rr.py` 版本为 2026-06-12 的 `a96f7f3`，明确 GPU harness 与权重缺口。
- [SGLang 内存池](https://github.com/sgl-project/sglang/blob/e9400c5a8f3a0d0312a37aecef694f5edfd69341/python/sglang/srt/lora/mem_pool.py)：完整责任单元，commit `e9400c5` 日期为 2026-10-13；[运行文档](https://docs.sglang.io/advanced_features/lora.html)。
- [vLLM LoRA](https://docs.vllm.ai/en/latest/features/lora/)与 [TensorRT-LLM LoRA](https://nvidia.github.io/TensorRT-LLM/advanced/lora.html)：当前加载及缓存文档；TensorRT-LLM main 版本为 2026-10-13 的 `31c1a3f`。
