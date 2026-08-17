# Foretoken deployment

Deploy or reuse the Quick Start service, discover its model and endpoint, and clean up resources created for the benchmark:

```bash
foretoken bench --deploy examples/quickstart
```

# Dataset sources

Supported `--dataset` selectors (rows: `messages`, `prompt`, or `user`[+`system`]):

```text
# Local JSONL
/path/to/trace.jsonl

# Hugging Face dataset + split
# The namespace may be any real user or organization, such as meta-llama.
meta-llama/example-dataset:train

# A specific file in a Hugging Face dataset repository
hf://datasets/meta-llama/example-dataset@main/path/to/trace.jsonl

# Multiple sources
/path/a.jsonl,org/dataset:train,hf://datasets/org/other/path/to/trace.jsonl
```

The canonical Hub file URI must include the dataset repo type: `hf://datasets/...`, not `hf://org/dataset/...`. File URIs are cached with `hf_hub_download(repo_type="dataset")` and then read as local JSONL.

# Random dataset

```
foretoken bench \
  --url "$FRONTEND_URL/v1/chat/completions" \
  --model Qwen/Qwen3-0.6B \
  --dataset random \
  --tokenizer-path Qwen/Qwen3.6-27B \
  --min-prompt-length 128 --max-prompt-length 512 \
  --parallel 4 --number 20 --max-tokens 64 \
  --rate 5 \
  --output local,wandb
```

![Random dataset benchmark output](imgs/random-dataset-benchmark-output.png)

![Random dataset W&B dashboard](imgs/random-dataset-wandb-dashboard.png)

# HuggingFace dataset id

```
foretoken bench \
  --url "$FRONTEND_URL/v1/chat/completions" \
  --model Qwen/Qwen3-0.6B \
  --dataset weijiezz/foretoken-trace:conversation \
  --parallel 4 \
  --number 20 \
  --output local,wandb
```

![Hugging Face dataset benchmark output](imgs/huggingface-dataset-benchmark-output.png)

![Hugging Face dataset W&B dashboard](imgs/huggingface-dataset-wandb-dashboard.png)

# HuggingFace file URI

```
foretoken bench \
  --url "$FRONTEND_URL/v1/chat/completions" \
  --model Qwen/Qwen3-0.6B \
  --dataset hf://datasets/ianncity/GLM-5.2-Conversation/dataset.jsonl \
  --parallel 4 \
  --number 20 \
  --output local,wandb
```

# Local dataset

```
foretoken bench \
  --url "$FRONTEND_URL/v1/chat/completions" \
  --model Qwen/Qwen3-0.6B \
  --dataset /path/to/trace.jsonl \
  --parallel 4 \
  --number 20 \
  --output local,wandb
```

![Local dataset benchmark output](imgs/local-dataset-benchmark-output.png)

![Local dataset W&B dashboard](imgs/local-dataset-wandb-dashboard.png)

# Multi-dataset

```
foretoken bench \
  --url "$FRONTEND_URL/v1/chat/completions" \
  --model Qwen/Qwen3-0.6B \
  --dataset weijiezz/foretoken-trace:conversation,hf://datasets/ianncity/GLM-5.2-Conversation/dataset.jsonl \
  --parallel 4 \
  --number 20 \
  --output local,wandb
```

![Multi-dataset benchmark output](imgs/multi-dataset-benchmark-output.png)

![Multi-dataset W&B comparison](imgs/multi-dataset-wandb-comparison.png)

# Sweep

Pass a JSONL file via `--bench-params`. Each line overrides load / generation /
dataset fields on top of the CLI base config. List-valued `parallel` /
`number` / `rate` expand into separate load points.

Example (`examples/bench_params.jsonl`):

```jsonl
{"_benchmark_name": "n10", "parallel": [1, 2, 4, 8], "number": 10, "max_tokens": 64}
{"_benchmark_name": "n20", "parallel": [1, 2], "number": 20, "max_tokens": 128}
```

```
foretoken bench \
  --url "$FRONTEND_URL/v1/chat/completions" \
  --model Qwen/Qwen3-0.6B \
  --dataset random \
  --tokenizer-path Qwen/Qwen3.6-27B \
  --min-prompt-length 128 --max-prompt-length 512 \
  --bench-params examples/bench_params.jsonl \
  --output local,wandb
```

After all points finish, results include `pareto/PARETO.png`
(X = Tok/s/user, Y = Tok/s/GPU).

![PARETO](imgs/PARETO.png)

![Sweep benchmark output](imgs/sweep-benchmark-output.png)

![Sweep W&B comparison](imgs/sweep-wandb-comparison.png)
