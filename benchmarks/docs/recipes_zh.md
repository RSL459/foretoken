<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 实验配方

[English](recipes.md) | 简体中文 · [评测与性能剖析](../README_zh.md)

根据要回答的问题选择负载。完成[准备步骤](../README_zh.md#开始使用)，在仓库根目录运行部署示例，将 `examples/quickstart` 换成待测模型的部署目录。

## 选择比较方法

| 想回答什么 | 负载与结果 |
| --- | --- |
| 并发如何影响容量？ | [并发扫描](perf/sweep_zh.md#比较并发设置)：吞吐量与延迟的取舍 |
| 多大负载能满足延迟目标？ | [固定速率 SLO 测量](perf/slo_zh.md#固定对话启动速率测量达标率)：达标率与 goodput |
| 延迟目标变化会怎样影响容量？ | [阈值扫描](perf/sweep_zh.md#比较-slo-阈值与请求速率) |
| 真实多轮对话下表现如何？ | [StudyChat 数据](perf/huggingface_zh.md)或 [ShareGPT](perf/sharegpt_zh.md)，选择记录或生成的历史 |
| 历史流量如何影响排队和延迟？ | [StudyChat 回放](perf/studychat_zh.md)：响应延迟和发送延后 |
| 共享前缀能否改善性能？ | [Mooncake 回放](perf/mooncake-trace_zh.md)，比较重建与不重建共享前缀 |
| 量化后有什么变化？ | [方法扫描](perf/sweep_zh.md#比较多种方法)、[任务得分](eval/README_zh.md#比较多个部署的任务评分)和[概率差异](eval/distribution-comparison_zh.md) |
| 执行时间花在哪里？ | [性能剖析](profile/README_zh.md) |

## 长上下文性能

使用[长上下文文件](../scripts/common/long-context.jsonl)在并发 1 下扫描输入长度，为输出预留 512 token。复制为 `long-context.jsonl`，只保留模型上下文范围内的行。快速开始的总上下文上限为 32,768 token，因此只保留 16,384-token 输入行。

```bash
cp benchmarks/scripts/common/long-context.jsonl long-context.jsonl
```

编辑副本后运行：

```bash
foretoken perf examples/quickstart --dataset random \
  --sweep long-context.jsonl \
  --max-concurrency 1 --min-output-length 512 --max-output-length 512 \
  --num-prompts 4 --warmup-requests 1 --num-runs 1 --temperature 0 \
  --experiment-name long-context --output local,plot
```

用 TTFT 比较输入增长的影响，用 TPOT 比较生成速度。每点四个请求适合初步比较长度；测量尾延迟时增加请求量与重复次数。

## 任务准确率与困惑度

以下基于似然的任务需要[源码安装的平台](../../docs/custom-deployment_zh.md)，或能返回输入 token 对数概率的已有 Completions 服务。对每个零样本任务运行最多 100 个样本：

```bash
foretoken eval examples/quickstart \
  --tasks piqa,arc_easy,arc_challenge,hellaswag,winogrande \
  --num_fewshot 0 --limit 100 --output local,plot
```

困惑度使用 [WikiText 评测](eval/README_zh.md#候选答案似然与困惑度)。任务得分和困惑度回答不同问题，比较同一指标时保持任务配置及样本范围一致。

## 推测解码

将 `BASELINE` 和 `CANDIDATE` 设为同一目标模型关闭、开启推测解码的部署目录：

```bash
BASELINE=path/to/non-speculative-deployment
CANDIDATE=path/to/speculative-deployment

foretoken perf "$BASELINE" "$CANDIDATE" --dataset random \
  --min-prompt-length 128 --max-prompt-length 256 \
  --sweep benchmarks/examples/sweep.jsonl --num-runs 3 --temperature 0 \
  --experiment-name speculative-decoding --output local,plot

foretoken eval "$CANDIDATE" --reference "$BASELINE" \
  --greedy-compare --context-length 512 --num-windows 8 --max-tokens 128 \
  --output local,plot
```

比较服务速度及[贪心序列一致率](eval/distribution-comparison_zh.md#比较贪心生成序列)。集群有 Prometheus 时，[推测解码观测](../metrics_zh.md#猜测解码观测)可以解释草稿接受情况与阶段开销。

## 缓存、部署与扩缩容消融

将 `BASELINE` 和 `CANDIDATE` 设为仅改变待研究机制的两个部署目录：

```bash
BASELINE=path/to/baseline-deployment
CANDIDATE=path/to/ablation-deployment

foretoken perf "$BASELINE" "$CANDIDATE" \
  --trace valeriol29/mooncake-traces:conversation --dataset random \
  --trace-start 57s --trace-duration 8min --max-concurrency 16 \
  --trace-synthetic-prefix-reuse --random-seed 0 --max-tokens 64 \
  --slo-params '[{"ttft":"<=2s","tpot":"<=100ms"}]' --output local,plot
```

在同一段回放上比较延迟、达标率和 goodput。Kustomize 结果还会展示副本变化和 [GPU 分配量](../metrics_zh.md#gpu-分配量)。测量已有部署的变更前先应用配置，评测会原样复用服务。

将 `RESULT_DIR` 换成打印的实验目录，用 `foretoken plot RESULT_DIR` 重新绘图。选择指标或调整图宽，见[扫描结果](perf/sweep_zh.md#查看结果与重新绘图)。
