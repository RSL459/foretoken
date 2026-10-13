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

`--wandb-entity` 选择账号或团队。group 和运行名分别设置。扫描、多数据集在未指定 group 时自动分组，各子运行会在名称后追加标识。单次评测默认不分组。

W&B 页面会展示最终汇总指标、P50/P95/P99 百分位指标，以及按时间、累计结果和逐请求统计的曲线。预热请求不计入性能指标，也不展示为图表；预热请求记录和指标保存在 `benchmark-warmup` 附件中。混合负载另外展示共用时间轴的数据集、模型和请求类别汇总表与时间曲线，以及包含逐请求标签和目标/实际输出 token 数的请求表。Kustomize 评测还会展示副本数变化；当控制器状态覆盖完整评测窗口时，还会按设备资源名展示 GPU-seconds 和 GPU-hours。覆盖率单独展示，部分样本仅用于诊断，不会当作总成本。可在 group 的 Workspace 中对比各次运行，Summary 保留最终值。窗口定义见[结果指标](../metrics_zh.md#曲线)。

使用 Kustomize 模型服务且集群提供 Prometheus 时，猜测解码运行还会显示[接受率和阶段耗时观测](../metrics_zh.md#猜测解码观测)。参数扫描的对比运行绘制相同的测量窗口汇总值。

![逐请求耗时与 token 数](../imgs/request-order-wandb.png)

使用 `--output local,wandb,plot` 时，导出的图表保存在本地和 `benchmark-plots` 附件中，不在工作区生成图片面板。

输出位置通过通用[结果设置](../../README_zh.md#查看和保存结果)选择。显式选择 W&B 后，初始化、发布或结束运行失败会使命令失败，并保留已经生成的评测产物。
