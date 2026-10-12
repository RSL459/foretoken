# Qwen 吞吐与解码延迟优化

[English](qwen-decode.md) | 简体中文

```text
模型：Qwen3.5-35B-A3B
优化目标：提升单并发解码速度和 16 并发总输出吞吐（token/s），降低两组的解码延迟（TPOT）
精度：固定 BF16
部署形态：聚合部署、预填充/解码分离等，不限
单服务配置：每个服务最多 8 卡；具体 GPU 数、并行方式、CPU 核数和内存由 Agent 选择
可用资源：2×8 卡 MetaX C500，每节点可用 64 核 CPU、1 TiB 内存
最小并行工作子 Agent 数：6
最大并行工作子 Agent 数：20
最小并行实验数：2
最大并行实验数：由 Agent 根据可用资源和单实验需求确定上限，并写入实验说明
评测负载：每个服务分别测量并发 1 和 16，覆盖随机长度负载和 StudyChat 对话；具体命令见下方“评测命令”
精度评测：仅在改动可能影响精度时考虑执行 foretoken eval；每完成 20 轮速度迭代最多执行一次，不要求逢 20 轮必测
可改动范围：在上述精度与资源约束内不限，包括部署配置、并发与批处理、并行策略、预填充/解码分离、推理引擎与调度、算子优化与融合、编译与图执行、通信、显存管理、KV 缓存与卸载、推测解码、采样、Router 与负载均衡、准入与排队、扩缩容、CPU 与 I/O 优化
单次迭代实验最长用时：10 分钟
工作时间：从开始执行任务计时，最多自主优化 12 小时
预期／结束条件：不设固定指标阈值，持续最大化吞吐、最小化 TPOT，直至无进一步优化空间或工作时间用尽
交付结果（<iteration> 为 --iteration 指定的方案名）：
  - 改动与命令：每轮的代码／配置改动和完整 foretoken perf 命令，写入 results/qwen-decode/iterations/<iteration>/notes/iteration.md 的“改动与命令”部分。
  - 性能指标：各负载在并发 1／16 下的输出吞吐（token/s）与平均 TPOT（ms/token），写入同一 iteration.md 的“性能指标”表。
  - 对照分析：相同负载下，与初始方案和上一轮的数值对照、变化百分比及原因分析，写入同一 iteration.md 的“对照分析”部分。
  - 结果证据：W&B 链接、图表和原始结果路径，写入同一 iteration.md 的“结果证据”部分；命令自动保存的原始产物保留在 results/qwen-decode/iterations/<iteration>/runs/ 下。
  - 最终方案：保留方案、对应代码／配置、各负载实测结果及逐轮对照汇总，写入 results/qwen-decode/notes/experiment.md。
  - 用户汇总：按实验名创建 rsi-playbooks/tasks/qwen-decode/<experiment>/，将 experiment.md 中的主要结论、逐轮性能对照和 W&B 链接整理到该目录的 report.md，关键图表放入 figures/ 并用相对路径引用；交付汇总文件路径。
```

执行与资源安排见[优化任务](README_zh.md#自主执行)，记录方法见[实验记录手册](../experiment-records_zh.md)。

## 评测命令

在仓库根目录执行，将部署目录和 W&B API key 占位符替换为实际值。结果统一保存到执行机器上的 `results/qwen-decode/`；`baseline` 是初始方案名，新方案更名，同一方案补测沿用名称。上述笔记由 Agent 填写，指标与图表由命令生成。

随机负载需分别用 `--max-concurrency 1` 和 `16` 运行两次；两次运行的请求数、预热量和评测样本量保持一致。StudyChat 命令是最终保留方案的必需项，其余迭代可选。更多负载见 [recipes](../../benchmarks/docs/recipes_zh.md)。

```bash
export WANDB_API_KEY="<your-wandb-api-key>"

# 每轮速度迭代：不同输入输出长度
foretoken perf path/to/qwen-deployment --dataset random \
  --min-prompt-length 128 --max-prompt-length 4096 \
  --min-output-length 128 --max-output-length 512 \
  --max-concurrency 16 --num-prompts 160 --warmup-requests 4 \
  --random-seed 0 --temperature 0 --output experiment,raw,plot,wandb \
  --output-dir results/qwen-decode --iteration baseline

# 最终保留方案必跑，中间按需：StudyChat 对话
foretoken perf path/to/qwen-deployment \
  --dataset hf://datasets/KrisQ/StudyChat/data.jsonl \
  --max-concurrency 16 --num-prompts 128 --max-tokens 2048 \
  --warmup-requests 4 --temperature 0 --output experiment,raw,plot,wandb \
  --output-dir results/qwen-decode --iteration baseline

# 可不执行：仅在改动可能影响精度且满足上述频率限制时评测
foretoken eval path/to/qwen-deployment \
  --tasks gsm8k --num_fewshot 0 --limit 20 --output experiment,plot,wandb \
  --output-dir results/qwen-decode --iteration baseline
```
