# W&B 输出

[English](wandb.md) | 简体中文 · [性能评测示例](README_zh.md)

完成[准备步骤](README_zh.md#准备)后，指定项目、分组和运行名称：

```bash
foretoken perf examples/quickstart \
  --num-prompts 20 --output local,wandb \
  --wandb-project foretoken-bench \
  --wandb-group qwen-comparison \
  --wandb-run-name quickstart
```

打开终端打印的运行链接即可查看结果，quiet 模式也会显示链接。`--wandb-entity` 选择账号或团队。需要对比的运行使用相同的 `--wandb-group`，在该分组的 Workspace 中查看。扫描和多数据集运行在未指定 group 时自动分组，单次评测默认不分组。

## 查看进度与比较结果

HTTP 正式测量期间，请求完成后即更新逐请求曲线，累计完成数、失败数、平均延迟和吞吐量每秒采样。完成窗口曲线包含 P50/P95/P99，在窗口数据确定后上传；尚未结束的请求可能推迟较早窗口的发布。吞吐量统计已完成请求，并按正式测量已经过的时间计算。测量结束后展示最终汇总指标，Summary 保留最终值。

![逐请求耗时与 token 数](../imgs/request-order-wandb.png)

混合负载可按数据集、模型和请求类别查看细分结果。Kustomize 评测还提供副本数和 GPU 分配量观测；服务具备 Prometheus 时，可查看资源使用和猜测解码指标。定义、单位和观测覆盖范围见[性能指标](../metrics_zh.md)。

## 下载记录

在运行页面的 Artifacts 中下载 HTTP 配置、汇总指标和逐请求记录，包括失败原因。每次运行都保留 `run.log`；扫描和对比任务的共享服务准备、清理日志保存在父运行中。中断后仍可下载已完成请求的逐条记录，保存位置见[结果设置](../../README_zh.md#查看和保存结果)。

预热不计入性能指标，也不占用面板，记录保存在 `benchmark-warmup` 附件中。在 `--output local,wandb` 中加上 `plot`，即可将导出的图表保存在本地和 `benchmark-plots` 附件中。

其他输出位置见[结果设置](../../README_zh.md#查看和保存结果)。W&B 发布失败会使命令失败，并保留本地执行文件供排查。
