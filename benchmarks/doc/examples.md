# Foretoken deployment

Deploy or reuse the Quick Start service, discover its model and endpoint, and clean up resources created for the benchmark:

```bash
foretoken bench examples/quickstart
```

# Random dataset

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

# HuggingFace dataset

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

# Local dataset

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

# StudyChat trace + dataset

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

# Mooncake trace + StudyChat dataset

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

# Mooncake trace + random

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

# Mooncake trace + synthetic prefix reuse

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

# Multi-dataset

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
