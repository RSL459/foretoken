# 在 W&B 中比较性能

[English](wandb.md) | 简体中文 · [性能评测示例](README_zh.md)

用 W&B 对比运行，并查看性能随时间的变化。首次执行 `wandb login`，再选择项目和分组：

```bash
foretoken perf examples/quickstart \
  --num-prompts 20 --max-tokens 128 --output local,wandb \
  --wandb-project foretoken-bench --wandb-group qwen-comparison \
  --wandb-run-name quickstart
```

`--wandb-entity` 选择账号或团队。同组运行可在 group 的 Workspace 中对比。扫描和多数据集运行未指定 group 时自动分组，单次运行默认不分组；子运行在指定名称前缀后追加标识。

## 选择视图

| 视图 | 查看什么 |
| --- | --- |
| Time | 按一秒完成窗口展示吞吐量、并发、失败率和延迟分位数 |
| Cumulative | 按经过时间平均的吞吐量 |
| Request index | 按发送顺序查看逐请求耗时、token 数和输出目标 |
| Summary | 最终汇总值，包括 P50/P95/P99 |
| Warmup | 启用预热时的预热曲线及其与正式测量的对比 |

预热不计入正式指标。混合负载在同一时间轴上展示数据集、模型和请求类别的分组结果，请求表保留对应标签。窗口和单位见[指标定义](../../metrics_zh.md#曲线)。

![按请求顺序查看耗时和 token 数](../imgs/request-order-wandb.png)

## 比较部署

Kustomize 运行还展示副本变化和 GPU 分配量。观测覆盖整次运行时，按设备资源名报告 GPU-seconds 和 GPU-hours；部分覆盖单独展示，见 [GPU 分配量](../../metrics_zh.md#gpu-分配量)。

集群提供 Prometheus 时，推测解码运行会展示[接受率和阶段耗时](../../metrics_zh.md#猜测解码观测)。扫描的对比运行汇总各参数点与重复测量的结果。

通过[输出设置](../../README_zh.md#查看和保存结果)同时保留本地文件或导出图表。W&B 发布失败时命令报错，已生成的产物会保留。
