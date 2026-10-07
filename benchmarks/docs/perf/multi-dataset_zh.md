# 多数据集

[English](multi-dataset.md) | 简体中文 · [性能评测示例](README_zh.md)

混合多个对话来源，测量服务同时接收不同流量时的表现。完成[准备步骤](README_zh.md#准备)后，用逗号分隔数据集：

```bash
foretoken perf examples/quickstart \
  --dataset r0b0tlab/qwen3.8-max-distillation-50k:train,ianncity/GLM-5.2-Conversation:train \
  --max-concurrency 4 --num-prompts 20 --output local
```

各数据集共用一个到达率、并发上限和请求预算。远程来源可换成本地 JSONL 文件或 JSON 对话数组；随机输入作为独立负载运行。

## 设置流量比例

默认平均分配 `--num-prompts`。添加 `--dataset-weights 3,1` 后，第一个数据集获得四分之三的请求预算，第二个获得四分之一。各数据集的轮次预算用尽后停止。

按时长运行时，将 `--num-prompts` 换成 `--duration 5min`；此时权重控制对话抽样，不再分配固定请求数。

数据行可选择模型并标记请求类别，例如：

```json
{"prompt":"Hello","model":"Qwen/Qwen3-0.6B","request_class":"interactive","output_length":32}
```

该行选择模型，将请求标记为 `interactive`，并以 32 个输出 token 为目标。可用不同标签区分交互式与批量流量。输入格式、逐行控制和输出长度规则见[对话数据](conversations_zh.md#准备自己的数据)。

## 比较流量类别

结果按数据集、模型和请求类别分组，各组吞吐量与 goodput 均以完整实验时长计算。W&B 在同一经过时间轴上展示各组曲线，并在请求表中保留标签和输出目标。

![按请求类别展示的 p95 响应延迟](../imgs/mixed-workload-wandb.png)

通过 [SLO 测量](slo_zh.md)比较各类别的达标率，或用[参数扫描](sweep_zh.md)改变负载设置。
