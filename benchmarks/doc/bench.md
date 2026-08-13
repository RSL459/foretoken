# Random dataset

```
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --dataset random \
  --tokenizer-path Qwen/Qwen3.6-27B \
  --min-prompt-length 128 --max-prompt-length 512 \
  --parallel 4 --number 20 --max-tokens 64 \
  --rate 5 \
  --wandb
```

![image-20260813171943416](imgs\image-20260813171943416.png)

![image-20260813172129573](imgs\image-20260813172129573.png)

# HuggingFace dataset

```
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --dataset weijiezz/foretoken-trace:conversation \
  --parallel 4 \
  --number 20 \
  --wandb
```

![image-20260810161340097](imgs\image-20260810161340097.png)

![image-20260810161813655](imgs\image-20260810161813655.png)

# Local dataset

```
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --dataset /home/wshiah/code/zhuting/foretoken/conversation.jsonl \
  --parallel 4 \
  --number 20 \
  --wandb
```

![image-20260810161420515](imgs\image-20260810161420515.png)

![image-20260810161928838](imgs\image-20260810161928838.png)

# Multi-dataset

```
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --dataset r0b0tlab/qwen3.8-max-distillation-50k:train,ianncity/GLM-5.2-Conversation:train \
  --parallel 4 \
  --number 20 \
  --wandb
```

![image-20260810162231036](imgs\image-20260810162231036.png)

![image-20260810162132897](imgs\image-20260810162132897.png)