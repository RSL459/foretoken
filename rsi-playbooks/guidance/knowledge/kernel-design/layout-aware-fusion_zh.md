<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 面向数据布局的跨算子融合

[English](layout-aware-fusion.md) | 简体中文

## 从真实上下游开始

一个归一化或激活算子单独看很快，但分配、启动和全张量遍历串起来仍有明显开销。若中间张量有 `N` 个元素，每个 `s` 字节，省去一次独立写回与随后读取，逻辑访存量约减少 `2Ns` 字节。实际 HBM 节省取决于缓存命中。

生产者布局与消费者读取方式相容时，融合才能兑现这部分收益。矩阵累加结果按矩阵指令分布在各线程中，并不天然适合合并写回。CUTLASS epilogue 会显式交换数据、转换类型再存储；加入归约或第二个消费者，可能延长数据存活时间并增加共享内存流量。

## 用已有融合看清边界

vLLM v0.31.0 提供 Q/K 归一化与旋转位置编码融合。该 pass 匹配拆分 packed QKV、对 Q 和 K 逐 head 执行 RMSNorm、再执行 RoPE 的序列，V 保持不变。替代路径通过 `auto_functionalized` 调用融合算子，再拆分返回的更新后 packed 张量。原生算子的 mutation 契约因此在图中呈现为函数式返回值，不意味着调用方的原始 QKV 一定被原地改写。

核对的实现接受 FP16/BF16，依赖已发现的 attention 几何信息，head dimension 限于 64、128、256，并注册 `1e-5`、`1e-6` 两种 epsilon 及 NeoX、交错式两种旋转布局。它还统一 view/reshape 的图表示，提高等价计算的匹配机会。因此，上游存在某个融合，不代表当前模型一定执行了它。

调查应先看图中命中位置和实际内核。如果已经生效，再写一个等价替代通常没有价值；如果未命中，要区分只是图模式差异，还是布局、dtype、别名或数学语义确实不同。

## 继续设计的空间

可以研究直接写入下游所需布局、把归一化与输出转换结合，或在 epilogue 中保留寄存器数据。每项设计都要考虑原张量的全部消费者；另一分支仍需原值时，原地转换就不合适。

融合也用寄存器压力、驻留度及库内核的专门化机会，交换启动和访存节省。高效独立 GEMM 加一个小 epilogue，有时比大型融合内核更快。解码和预填充的矩阵大小、启动与计算比例不同，合理的融合边界也可以不同。

## 实验方式

提取候选序列前的真实张量，保留 stride、别名、head 结构和消费者关系。测量整个序列，包括替代实现新增的分配与复制。比较尾部形状和归约顺序变化的数值影响，并连续执行多个模型步，暴露残差或缓存被意外修改的问题。

检查编译图与设备 trace，确认预期融合实际运行。先判断被消除操作是否减少完整层时间，再观察服务性能。如果编译器本来就已融合，应继续研究生成内核的布局和调度，而不是按源码算子数量推算收益。

## 来源与实现状态

核对日期：2026-10-14。

- [vLLM v0.31.0 QK norm/RoPE 融合](https://github.com/vllm-project/vllm/blob/db9527a46873454610df6dbedf79a36d6bf1a7f6/vllm/compilation/passes/fusion/qk_norm_rope_fusion.py)：现有实现与匹配条件。
- [vLLM 已有融合 pass](https://github.com/vllm-project/vllm/tree/db9527a46873454610df6dbedf79a36d6bf1a7f6/vllm/compilation/passes/fusion)：提出替代前核对对应实现。
- [CUTLASS epilogue 与访存结构](https://github.com/NVIDIA/cutlass/blob/main/media/docs/cpp/efficient_gemm.md)。
- [PyTorch 自定义算子集成](https://docs.pytorch.org/tutorials/advanced/cpp_custom_ops.html)：融合内核接入编译器所需的 mutation 和元数据语义。
