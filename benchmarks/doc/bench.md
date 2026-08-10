随机数据压测

```
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --dataset random \
  --tokenizer-path /exportr/zxcpu2/shiweijie/cache/models--Qwen--Qwen3.6-27B/snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9 \
  --min-prompt-length 128 --max-prompt-length 512 \
  --parallel 4 --number 20 --max-tokens 64 \
  --rate 5 \
  --wandb
```

![image-20260810160936224](C:\Users\朱婷\AppData\Roaming\Typora\typora-user-images\image-20260810160936224.png)

![image-20260810161639571](C:\Users\朱婷\AppData\Roaming\Typora\typora-user-images\image-20260810161639571.png)

HF数据集

```
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --dataset weijiezz/foretoken-trace:conversation \
  --parallel 4 \
  --number 20 \
  --wandb
```

![image-20260810161340097](C:\Users\朱婷\AppData\Roaming\Typora\typora-user-images\image-20260810161340097.png)

![image-20260810161813655](C:\Users\朱婷\AppData\Roaming\Typora\typora-user-images\image-20260810161813655.png)

本地数据集

```
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --dataset /home/wshiah/code/zhuting/foretoken/conversation.jsonl \
  --parallel 4 \
  --number 20 \
  --wandb
```

![image-20260810161420515](C:\Users\朱婷\AppData\Roaming\Typora\typora-user-images\image-20260810161420515.png)

![image-20260810161928838](C:\Users\朱婷\AppData\Roaming\Typora\typora-user-images\image-20260810161928838.png)

多数据集

```
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --dataset r0b0tlab/qwen3.8-max-distillation-50k:train,ianncity/GLM-5.2-Conversation:train \
  --parallel 4 \
  --number 20 \
  --wandb
```

![image-20260810162231036](C:\Users\朱婷\AppData\Roaming\Typora\typora-user-images\image-20260810162231036.png)

![image-20260810162132897](C:\Users\朱婷\AppData\Roaming\Typora\typora-user-images\image-20260810162132897.png)