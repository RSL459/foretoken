# 评测示例

[English](examples.md) | 简体中文

# Foretoken 部署

部署或复用快速开始服务，自动发现模型和访问入口，并在评测结束后清理本次创建的资源：

```bash
foretoken bench examples/quickstart
```

以下示例连接已经运行的服务：

```bash
FRONTEND_URL=http://127.0.0.1:8008
```

# 数据集来源

`--dataset` 支持本地 JSONL、Hugging Face 数据集，以及数据集仓库中的文件：

```text
/path/to/conversation.jsonl
org/dataset:train
hf://datasets/org/dataset@main/path/to/conversation.jsonl
```

多个来源可用逗号分隔。Hub 文件 URI 必须包含 `datasets` 仓库类型。

# 随机数据集

```
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --dataset random \
  --tokenizer-path Qwen/Qwen3.6-27B \
  --random-seed 0 \
  --min-prompt-length 128 --max-prompt-length 512 \
  --parallel 4 --number 20 --max-tokens 64 \
  --rate 5 \
  --output local,wandb
```

![Random dataset benchmark output](imgs/random-dataset-benchmark-output.png)

![Random dataset W&B dashboard](imgs/random-dataset-wandb-dashboard.png)

# Hugging Face 数据集

```
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --dataset weijiezz/foretoken-trace:conversation \
  --parallel 4 \
  --number 20 \
  --output local,wandb
```

![Hugging Face dataset benchmark output](imgs/huggingface-dataset-benchmark-output.png)

![Hugging Face dataset W&B dashboard](imgs/huggingface-dataset-wandb-dashboard.png)

# 本地数据集

```
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --dataset /path/to/conversation.jsonl \
  --parallel 4 \
  --number 20 \
  --output local,wandb
```

![Local dataset benchmark output](imgs/local-dataset-benchmark-output.png)

![Local dataset W&B dashboard](imgs/local-dataset-wandb-dashboard.png)

# StudyChat trace 与数据集

```
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --trace KrisQ/StudyChat \
  --dataset KrisQ/StudyChat \
  --trace-start 18609042.663 --trace-duration 120 \
  --trace-max-concurrency 16 \
  --max-tokens 64 --temperature 0 \
  --timeout 90 --max-retries 0 \
  --output-dir results/trace-studychat \
  --output local,wandb
```

![StudyChat trace benchmark output](imgs/trace-studychat-benchmark-output.png)

![StudyChat trace W&B dashboard](imgs/trace-studychat-wandb-dashboard.png)

# Mooncake trace 与 StudyChat 数据集

```
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --trace valeriol29/mooncake-traces \
  --dataset KrisQ/StudyChat \
  --trace-start 540 --trace-duration 120 \
  --trace-max-concurrency 16 \
  --max-tokens 64 --temperature 0 \
  --timeout 90 --max-retries 0 \
  --output-dir results/trace-mooncake-dataset \
  --output local,wandb
```

![Mooncake trace with StudyChat benchmark output](imgs/trace-mooncake-studychat-benchmark-output.png)

![Mooncake trace with StudyChat W&B dashboard](imgs/trace-mooncake-studychat-wandb-dashboard.png)

# Mooncake trace 与随机数据

```
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --trace valeriol29/mooncake-traces \
  --trace-start 2620 --trace-duration 30 \
  --dataset random \
  --tokenizer-path Qwen/Qwen3.6-27B \
  --random-seed 0 \
  --trace-max-concurrency 16 \
  --max-tokens 64 --temperature 0 \
  --timeout 90 --max-retries 0 \
  --output-dir results/trace-mooncake-random \
  --output local,wandb
```

![Mooncake trace with random payload benchmark output](imgs/trace-mooncake-random-benchmark-output.png)

![Mooncake trace with random payload W&B dashboard](imgs/trace-mooncake-random-wandb-dashboard.png)

# Mooncake trace 与合成前缀复用

```
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --trace valeriol29/mooncake-traces \
  --trace-start 2620 --trace-duration 30 \
  --dataset random \
  --tokenizer-path Qwen/Qwen3.6-27B \
  --random-seed 0 \
  --trace-synthetic-prefix-reuse \
  --trace-max-concurrency 16 \
  --max-tokens 64 --temperature 0 \
  --timeout 90 --max-retries 0 \
  --output-dir results/trace-mooncake-prefix \
  --output local,wandb
```

![Mooncake synthetic prefix replay benchmark output](imgs/trace-mooncake-prefix-reuse-benchmark-output.png)

![Mooncake synthetic prefix replay W&B dashboard](imgs/trace-mooncake-prefix-reuse-wandb-dashboard.png)

# 多数据集

```
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --dataset r0b0tlab/qwen3.8-max-distillation-50k:train,ianncity/GLM-5.2-Conversation:train \
  --parallel 4 \
  --number 20 \
  --output local,wandb
```

![Multi-dataset W&B comparison](imgs/multi-dataset-wandb-comparison.png)

![Multi-dataset benchmark output](imgs/multi-dataset-benchmark-output.png)


# 参数扫描

通过 `--bench-params` 传入 JSONL 文件，每行覆盖请求执行字段。`parallel`、`number` 或 `rate` 的列表值会展开为独立负载点。

示例（`benchmarks/examples/bench_params.jsonl`）：

```jsonl
{"_benchmark_name": "n10", "parallel": [1, 2, 4, 8], "number": 10, "max_tokens": 64}
{"_benchmark_name": "n20", "parallel": [1, 2], "number": 20, "max_tokens": 128}
```

```bash
foretoken bench examples/quickstart \
  --dataset random \
  --tokenizer-path Qwen/Qwen3-0.6B \
  --min-prompt-length 128 --max-prompt-length 512 \
  --bench-params benchmarks/examples/bench_params.jsonl \
  --output local,wandb
```

实验会保存全部负载点，并生成 `pareto/PARETO.png`（Tok/s/user 对 Tok/s/GPU）。

![Pareto frontier](imgs/PARETO.png)

![Sweep benchmark output](imgs/sweep-benchmark-output.png)

![Sweep W&B comparison](imgs/sweep-wandb-comparison.png)
