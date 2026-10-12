# Qwen 吞吐与解码延迟优化

[English](qwen-decode.md) | 简体中文

```text
模型：Qwen3.5-35B-A3B
精度：固定 BF16
部署形态：聚合部署、预填充/解码分离等，不限
单服务配置：每个服务最多 8 卡；具体 GPU 数、并行方式、CPU 核数和内存由 Agent 选择
可用资源：2×8 卡 MetaX C500，每节点可用 64 核 CPU、1 TiB 内存
最小并行工作子 Agent 数：6
最大并行工作子 Agent 数：20
最小并行实验数：2
最大并行实验数：由 Agent 根据可用资源和单实验需求确定上限，并写入实验说明
评测负载：每个服务分别测量并发 1 和 16，覆盖不同输入输出长度与自然回答；使用 foretoken perf 测量性能、foretoken perf --profile 分析瓶颈
精度评测：仅在改动可能影响精度时考虑执行 foretoken eval；每完成 20 轮速度迭代最多执行一次，不要求逢 20 轮必测
优化目标：提升单并发解码速度和 16 并发总输出吞吐（token/s），降低两组的解码延迟（TPOT）
可改动范围：不限
单次迭代实验最长用时：10 分钟
工作与结束条件：从开始执行任务计时，自主持续优化 12 小时
交付结果：完整迭代过程，记录每轮动机、方案与改动、测量结果、分析、耗时和下一步决定；汇总各组收益、保留方案、代码改动与结果链接
```

执行与资源安排见[优化任务](README_zh.md#自主执行)，记录方法见[实验记录手册](../experiment-records_zh.md)。

## 评测命令

在仓库根目录执行，将部署目录和 W&B API key 占位符替换为实际值。前两条分别用 `--max-concurrency 1` 和 `16` 运行；请求数、预热量和评测样本量按单轮时间预算调整，对照时保持一致。更多负载见 [recipes](../../benchmarks/docs/recipes_zh.md)。

```bash
export WANDB_API_KEY="<your-wandb-api-key>"

# 每轮速度迭代：不同输入输出长度
foretoken perf path/to/qwen-deployment --dataset random \
  --min-prompt-length 128 --max-prompt-length 4096 \
  --min-output-length 128 --max-output-length 512 \
  --max-concurrency 1 --num-prompts 16 --warmup-requests 4 \
  --random-seed 0 --temperature 0 --output experiment,raw,plot,wandb

# 最终保留方案必跑，中间按需：自然回答
foretoken perf path/to/qwen-deployment \
  --prompt "Explain the trade-offs between tensor parallelism and pipeline parallelism." \
  --max-concurrency 1 --num-prompts 16 --max-tokens 2048 \
  --warmup-requests 4 --temperature 0 --output experiment,raw,plot,wandb

# 可不执行：仅在改动可能影响精度且满足上述频率限制时评测
foretoken eval path/to/qwen-deployment \
  --tasks piqa,arc_easy,arc_challenge,hellaswag,winogrande \
  --num_fewshot 0 --limit 100 --output experiment,plot,wandb
```
