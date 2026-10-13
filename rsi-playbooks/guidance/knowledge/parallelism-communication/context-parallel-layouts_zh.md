<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 上下文并行先明确张量归属

[English](context-parallel-layouts.md) | 简体中文

## 问题与现状

长上下文 prefill 分摊大量 query；decode 则让极少的新 query 访问大量历史。二者需要不同通信模式。都叫序列并行或上下文并行 CP，可能掩盖实现到底切分 query、head、KV 历史，还是只切分中间激活。

USP 已把 Ulysses all-to-all 和 ring attention 组合起来，论文主要研究训练与长序列 attention，不是持续 decode 服务。vLLM 已有 decode CP（DCP），当前源码也有 prefill-CP 缓存收集路径。部署指南仍称 prefill 方案在开发，不能用这句话证明全部 PCP 执行不存在；必须分别检查模型、后端和 worker 支持。

## 执行机制

Ulysses 从序列分片 Q/K/V 开始，用 all-to-all 把归属转成“更长序列、更少 head”，本地计算这些 head 的 attention，再做逆向 all-to-all 恢复序列归属。简单实现受到 head 整除限制，KV head 少或 TP 已切分 head 时尤其明显。

Ring attention 保留本地 query，循环交换 KV 块，用稳定的在线 softmax 累积结果。USP 建立正交的两组进程：一个维度 Ulysses，另一个维度 ring，二者 degree 相乘为总序列并行度。例如八 rank 使用 Ulysses 二、ring 四。让频繁 all-to-all 留在更快的域、ring 跨较慢边界，仍需实际计算足以掩盖传输。

因果 attention 按连续 query 块切分时工作不均：早期 query 只看到短历史，后期 query 看到更多。USP 的 zigzag 把早晚块配对。原始位置、RoPE、因果 mask 与输出还原必须遵循相同置换；重排存储并不意味着可以改变模型序列。

DCP 则让各 rank 持有 KV 历史片段，计算局部 attention，再按 softmax 归一化合并。局部归一化输出为 `o_r`、对数归一化量为 `lse_r` 时，可理解为：

```text
L = logsumexp_r(lse_r)
o = sum_r exp(lse_r - L) * o_r
```

空分片不贡献概率质量，直接平均局部输出是错误的。decode query 很少，prefill ring 用于隐藏通信的大量 query 计算不再存在。

一个 KV head、TP 八的模型，普通 TP 可能把历史复制八份。vLLM 指南描述在已有 TP 组内使用 DCP 减少复制，不增加 GPU。这改变的是缓存归属，不只是换一种更快通信。

## 适用条件与取舍

USP 原始测量是 BF16/FP16 训练和 attention 负载。当前 YunChang 有多种 attention 实现，包括仅前向的替代后端，但这不能证明已具备 paged-cache 服务集成或所有加速器原生支持。

DCP 增加缓存容量，也引入 query/输出通信。文档中的 TP/head 关系可作为起点，仍需核对后端及推测 query 支持。PCP 即使切分 query，也可能在 gather 后复制 KV。当前 vLLM `pcp.py` 中，PCP-only 的 decode 请求分片会收集其他 owner 的新增 KV，以维持完整副本；与 DCP 组合时则有保留复制 decode query 的另一条路径。应测实际内存归属，不能从 CP 名称推断。

## 实验与服务验证

固定 rank 总数，改变 Ulysses/ring degree、上下文长度、KV head 数和因果布局，比较最大 rank attention 时间、通信、临时 KV 显存和位置正确的输出。加入短序列，启动与 reshape 可能超过收益。

decode 分别扫描历史长度和并发，覆盖不均分片、空分片、缓存增长与推测 query。记录缓存容量、attention 与合并时间及 TPOT，区分“容量增大支持更多请求”与“单请求 decode 更快”。

完整服务使用长输入、前缀复用和多轮缓存增长，先验证回答质量与位置，再比较未加 profiler 的 TTFT、TPOT。
## 依据与剩余问题

核对日期：2026-10-14。[USP 论文](https://arxiv.org/abs/2405.07719)，算法 1–2、第 3–5 节；[YunChang a5f8f600](https://github.com/feifeibear/long-context-attention/tree/a5f8f600d435ced180a97c91c68e87ff3cfb8f89) README、vLLM [6849ca69 的 CP 指南](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/serving/context_parallel_deployment.md)与 [PCP 缓存操作](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/v1/attention/ops/pcp.py)。剩余问题是目标后端的职责链核对与服务验证。
