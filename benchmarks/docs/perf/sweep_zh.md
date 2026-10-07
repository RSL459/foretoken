# 参数扫描

[English](sweep.md) | 简体中文 · [性能评测示例](README_zh.md)

在多个负载设置或部署上运行同一负载，比较延迟与吞吐量。完成[准备步骤](README_zh.md#准备)，在仓库根目录运行。

## 比较并发设置

```bash
foretoken perf examples/quickstart \
  --dataset random --min-prompt-length 128 --max-prompt-length 256 \
  --temperature 0 --sweep benchmarks/examples/sweep.jsonl \
  --warmup-requests 16 --num-runs 3 \
  --experiment-name concurrency --output local,wandb,plot
```

[参数文件](../../examples/sweep.jsonl)扫描并发 1、2、4，每个参数点发送 384 个请求，固定输出 256 token。每点重复三次，每次先预热 16 个请求。使用 W&B 前执行 `wandb login`，或改用 `--output local,plot`。

打开 `results/concurrency/sweep_summary.csv` 和 `plots/`，比较相同负载下吞吐量与延迟的取舍。误差线表示重复运行的样本标准差，分位数先逐轮计算再汇总；`samples` 和 `failed_runs` 用于识别不完整的测量。重复使用显式 `--experiment-name` 会覆盖该实验目录；省略时创建带时间戳的新目录。

## 定义参数组合

扫描文件每行包含一个 JSON 对象，例如：

```json
{"max_concurrency":[1,2,4],"num_prompts":100,"min_output_length":128,"max_output_length":128}
```

字段采用 CLI 名称，将连字符换成下划线。列表表示扫描维度，同一行的多个列表展开为全部组合；分行可将相关设置保持在一起。文件中的值覆盖命令行设置，可用 `_benchmark_name` 给负载命名。

组合值多加一层列表。例如 `"dataset": [["first.jsonl", "second.jsonl"]]` 在每个参数点混合两个数据集，而非分别测量。带单位的时间写成字符串，如 `"duration": ["30s", "2min"]`。

输入和输出长度应在模型上下文范围内。固定输出需服务支持 `min_tokens` 和 `ignore_eos`，见[随机负载](random_zh.md)。

## 选择负载

| 参数文件 | 比较内容 |
| --- | --- |
| [fixed-length](../../scripts/common/fixed-length.jsonl) | 输入输出较均衡、长输入和长输出负载的并发 |
| [fixed-arrival](../../scripts/common/fixed-arrival.jsonl) | 固定短输入和短输出下的请求速率 |
| [fixed-capacity](../../scripts/common/fixed-capacity.jsonl) | 长输入和短输出下的并发 |
| [long-context](../../scripts/common/long-context.jsonl) | 输入长度；输出长度和并发由命令指定 |
| [conversation-rate](../../scripts/common/conversation-rate.jsonl) | 所选数据集的每秒对话启动数 |
| [studychat-conversation](../../scripts/common/studychat-conversation.jsonl) | StudyChat 负载的并发 |
| [slo-thresholds](../../scripts/common/slo-thresholds.jsonl) | 延迟阈值和对话启动速率 |
| [quantized-models](../../scripts/common/quantized-models.jsonl) | BF16 与 4-bit 部署在不同并发下的表现 |

[实验配方](../recipes_zh.md)帮助选择比较方法。运行长上下文文件前，按服务能力调整长度范围。

## 比较 SLO 阈值与请求速率

搭配对话数据集使用 `slo-thresholds` 文件：

```bash
foretoken perf examples/quickstart \
  --dataset hf://datasets/anon8231489123/ShareGPT_Vicuna_unfiltered/ShareGPT_V3_unfiltered_cleaned_split.json \
  --sweep benchmarks/scripts/common/slo-thresholds.jsonl \
  --temperature 0 --random-seed 0 --max-concurrency -1 \
  --num-prompts 100 --num-runs 1 --output local,plot
```

比较各速率和阈值下的达标率与 goodput。请求预算统计 HTTP 轮次，速率控制对话启动次数；评分规则见[固定速率 SLO 测量](slo_zh.md#固定对话启动速率测量达标率)。

一行中的 `"slo_params": [{"ttft": "<=250ms"}, {"ttft": "<=500ms"}]` 扫描两组条件。如需在一个选择中分别搜索多个并发目标，添加 `--slo-search`，并嵌套条件对象：`"slo_params": [[{"p99_ttft": "<=250ms"}, {"p99_tpot": "<=100ms"}]]`。扫描中的 `--num-runs` 重复每个参数点的完整搜索，不重复单个探测点。

## 比较多种方法

```bash
foretoken perf examples/quantized-model/bf16 examples/quantized-model/bitsandbytes \
  --dataset random --min-prompt-length 128 --max-prompt-length 256 \
  --sweep benchmarks/examples/sweep.jsonl --num-runs 3 --output local,plot
```

模型存储按[量化模型示例](../../../examples/quantized-model/README_zh.md)准备。一种方法的所有参数点完成后再测量下一种；已有部署原样复用，临时部署在方法切换时删除。需要测量已有服务的配置变更时，先用 `foretoken deploy` 应用配置。

已有服务可在 `--url` 后指定多个 URL，`--model` 可传入一个共享模型名或按 URL 逐个指定。扫描行也可通过 `"service": ["examples/quantized-model/bf16", "examples/quantized-model/bitsandbytes"]` 选择服务。命名端点使用 `name`、`url`、`model`，可选 `health_url`。相对路径以执行命令的工作目录为准。

## 查看结果与重新绘图

```bash
foretoken plot results/concurrency --columns 2
```

该命令重新绘制第一个示例，不发送请求。可重复指定 `--metric` 或 `--method` 选择指标和方法，用 `--output-dir` 将另一版排版保存到独立目录。输出位置见[结果设置](../../README_zh.md#查看和保存结果)。[视频负载](video_zh.md)沿用相同的扫描方式，使用视频生成参数。
