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

结果保存在本地，测量结束后自动在后台上传。打开终端打印的发布日志，从其中的运行链接查看结果；quiet 模式也会显示日志位置。

用 `--wandb-entity` 选择账号或团队。需要对比的运行使用相同的 `--wandb-group`，在该分组的 Workspace 中查看。扫描和多数据集运行在未指定 group 时自动分组，单次评测默认不分组。

## 查看进度与比较结果

用逐请求曲线检查单次请求，用累计曲线回顾整体进度，用一秒完成窗口比较吞吐量及 P50/P95/P99 延迟随时间的变化。曲线数据在测量期间采集，发布后按原始测量坐标展示在 W&B 中。Summary 保留最终汇总指标。

![逐请求耗时与 token 数](../imgs/request-order-wandb.png)

混合负载可按数据集、模型和请求类别查看细分结果。Kustomize 评测还提供副本数和 GPU 分配量观测；服务具备 Prometheus 时，可查看资源使用和猜测解码指标。定义、单位和观测覆盖范围见[性能指标](../metrics_zh.md)。

## 下载记录

在运行页面的 Artifacts 中下载配置、指标、请求记录和日志。扫描或对比任务的共享服务准备、清理日志保存在父运行中。各类文件的用途和输出选项见[结果设置](../../README_zh.md#查看和保存结果)。

预热不计入性能指标，也不占用面板，记录保存在 `benchmark-warmup` 附件中。在 `--output local,wandb` 中加上 `plot`，即可将导出的图表保存在本地和 `benchmark-plots` 附件中。

## 发布已有结果

发布启用 `wandb` 输出时保存的待上传结果，无需重新测量：

```bash
foretoken publish results
```

也可传入某次运行、扫描或实验的目录，只发布其中的结果。命令会等待正在进行的上传，跳过已完成的上传。默认总时限为十分钟，结果较大时可添加 `--timeout 1h`。

命令会打印运行链接，自动上传的链接保存在 `publication.log` 中。上传失败的详细原因见对应运行的 `wandb-publish.log`。发布完成前，请保留结果目录及其引用的文件。
