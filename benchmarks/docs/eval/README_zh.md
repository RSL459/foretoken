<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 评测模型质量

[English](README.md) | 简体中文 · [评测与性能剖析](../../README_zh.md)

使用 lm-evaluation-harness 或 EvalScope 对模型答案评分。完成[准备步骤](../../README_zh.md#开始使用)，在仓库根目录运行 100 道 GSM8K 数学题：

```bash
foretoken eval examples/quickstart --tasks gsm8k --limit 100 --output local
```

默认使用 lm-evaluation-harness（`lm-eval`）。去掉 `--limit` 可运行完整任务。

## 查看评分

汇总结果列出任务得分、答案提取方式（filter）、样本数和框架提供的标准误差。比较分数时，选择相同指标和 filter，并保持任务设置及样本范围一致。

打开命令打印的结果目录：

| 文件或目录 | 内容 |
| --- | --- |
| `metrics.json` | 得分、子集、filter、样本数，以及框架提供的不确定性或执行状态 |
| `native/` | 框架报告与生成的逐样本记录 |
| `evaluator.log` | 评测进度和诊断日志 |

添加 `--log_samples` 可保存 lm-eval 的逐题输入和回答。[输出设置](../../README_zh.md#查看和保存结果)支持 W&B 和图表，W&B 的 `Evaluation/Scores` 表保留详细得分。

## 选择 lm-evaluation-harness 任务

任务名称和选项采用[上游接口](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/docs/interface.md)。多个任务在 `--tasks` 中以逗号分隔，`--num_fewshot 0` 使用零样本提示，`--model_args num_concurrent=4` 同时发送四个 API 请求。提示构造和评分规则由所选任务决定。

### 候选答案似然与困惑度

PIQA 比较候选答案的概率来选择答案。WikiText 测量困惑度：数值越低，原文越容易被模型预测。这些任务需要[源码安装的 Foretoken 平台](../../../docs/custom-deployment_zh.md)，或能返回输入 token 对数概率的已有 Completions 服务：

```bash
foretoken eval examples/quickstart --tasks piqa --limit 100 --output local

foretoken eval examples/quickstart --tasks wikitext --limit 100 --output local
```

tokenizer 从部署配置推导，URL 模式则使用 `--model`。模型采用服务别名或 tokenizer 文件在客户端本地时，可用 `--model_args tokenizer=MODEL_OR_LOCAL_DIRECTORY` 指定。候选答案评分默认使用原始文本；任务要求指令模型模板时加上 `--apply_chat_template`。困惑度使用原始语料，不套聊天模板。

## 使用 EvalScope

```bash
foretoken eval examples/quickstart --evaluator evalscope \
  --datasets gsm8k --limit 100 --output local
```

保存的报告包含类别和子集得分。用 [EvalScope 原生选项](https://evalscope.readthedocs.io/zh-cn/latest/get_started/basic_usage.html)配置任务，例如 `--dataset-args` 和 `--generation-config`。

已安装版本的选项分别见 `foretoken eval --evaluator lm-eval --help` 和 `foretoken eval --evaluator evalscope --help`。

## 比较多个部署的任务评分

准备好[量化模型示例](../../../examples/quantized-model/README_zh.md)，将部署目录写在任务参数之前：

```bash
foretoken eval examples/quantized-model/bf16 examples/quantized-model/bitsandbytes \
  --tasks piqa --limit 100 --output local,plot
```

各部署依次运行。`evaluation_comparison.csv` 对齐任务得分及框架提供的标准误差，各次运行保留框架报告。需要比较概率分布或生成 token 序列而非任务得分时，使用[参考与候选模型对比](distribution-comparison_zh.md)。

## 评测已有服务

将下方 URL 和模型名换成服务的 Chat Completions 地址及公开模型 ID：

```bash
foretoken eval --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen/Qwen3-0.6B --tasks gsm8k --limit 100 --output local
```

此模式不使用 Kubernetes；认证通过 `--api-key` 提供。Foretoken Gateway 部署传入 Kustomize 目录，自动查找路由信息。

## 恢复中断的评测

单部署评测保留本地输出即可保存进度。中断后，在原命令中加上 `--resume`，指向打印的结果目录。替换下面的 `results/previous-run`：

```bash
foretoken eval examples/quickstart --tasks gsm8k --limit 100 \
  --resume results/previous-run --output local
```

lm-eval 复用已完成的生成或似然评分窗口，EvalScope 复用已完成的预测和评分。恢复会把完整结果写入新目录，原目录保持不变。再次中断时从最新目录恢复，保持权重、任务设置和样本范围一致；EvalScope 还要求服务 URL 不变。此流程使用 `--resume`，不同时指定原生 `--use_cache` 或 `--use-cache`。

[概率分布对比](distribution-comparison_zh.md#恢复概率分布对比)也可复用已完成的评分窗口。
