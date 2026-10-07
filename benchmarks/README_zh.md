# 评测与性能剖析

[English](README.md) | 简体中文

用 `foretoken perf` 测量服务延迟和吞吐量，用 `foretoken eval` 评估回答质量，通过 CPU/GPU 执行时间线定位瓶颈。

## 开始使用

使用 Python 3.11 或更高版本安装 Foretoken：

```bash
pip install foretoken
```

以下部署示例在[快速开始](../README_zh.md#快速开始)准备的仓库目录中运行。评测原样复用已有部署；尚未部署时会临时创建服务，结束后删除本次创建的资源。单模型部署自动选择模型，多模型部署用 `--model` 指定。

## 测量性能

```bash
foretoken perf examples/quickstart \
  --prompt "用一句话解释什么是 token。" \
  --max-concurrency 4 --num-prompts 20 --max-tokens 128 --output local
```

汇总结果展示成功与失败请求数、响应延迟和吞吐量。默认启用流式响应，因此还会报告首 token 耗时（TTFT）和每输出 token 耗时（TPOT）。

[性能评测指南](docs/perf/README_zh.md)提供真实对话、固定 token 长度和历史流量等负载。[参数扫描](docs/perf/sweep_zh.md)用于比较负载设置和部署方案。

## 评测模型质量

```bash
foretoken eval examples/quickstart --tasks gsm8k --limit 100 --output local
```

该命令使用默认的 lm-evaluation-harness，对 100 道 GSM8K 数学题评分。汇总结果展示任务得分和样本数。其他任务、EvalScope 和中断恢复见[质量评测](docs/eval/README_zh.md)；与参考模型的差异可通过[模型对比](docs/eval/distribution-comparison_zh.md)测量。

## 剖析执行过程

[性能剖析指南](docs/profile/README_zh.md)介绍如何采集负载，并用 `foretoken profile view` 打开时间线，支持 PyTorch Profiler、NVIDIA Nsight Systems 和沐曦 mcTracer。

## 查看和保存结果

每次本地运行会打印 `results/` 下的结果目录，`--output-dir` 可修改父目录。性能评测的汇总保存在 `metrics.json`，逐请求记录保存在 `raw_output.json`；质量评测的框架报告保存在 `native/`。

| 要做什么 | 输出选项 |
| --- | --- |
| 保存到本地 | `--output local` |
| 保存到本地，并在 W&B 中对比 | `--output local,wandb`（`perf` 和 `eval` 的默认值） |
| 同时导出 PDF、SVG、PNG 和 CSV 图表 | `--output local,wandb,plot` |
| 保存结果，不打印进度和汇总 | `--output local,quiet` |

首次使用 W&B 前执行 `wandb login`。`quiet` 将日志保存到 `run.log`，错误仍会显示。输出选项可以组合，`plot` 会保留重新绘图所需的数据。

将 `RESULT_DIR` 换成命令打印的结果目录，即可重新绘图：

```bash
foretoken plot RESULT_DIR --columns 2
```

结果解读见[性能图表](docs/perf/wandb_zh.md)、[指标定义](metrics_zh.md)和[质量评分](docs/eval/README_zh.md#查看评分)。容量、质量与部署对比见[实验配方](docs/recipes_zh.md)。
