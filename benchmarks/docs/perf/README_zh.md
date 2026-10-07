# 测量服务性能

[English](README.md) | 简体中文 · [评测与性能剖析](../../README_zh.md)

用 `foretoken perf` 模拟服务实际接收的负载，测量响应延迟和吞吐量。

## 准备

完成[通用准备](../../README_zh.md#开始使用)，在仓库根目录运行部署示例。先以并发 4 发送 20 个请求：

```bash
foretoken perf examples/quickstart --num-prompts 20 --max-concurrency 4 \
  --max-tokens 128 --output local
```

命令使用内置提示词 `Hello`。汇总结果报告请求成功率、延迟、TTFT、TPOT 和吞吐量，本地结果保存在打印的目录中。默认负载的并发为 1，不限制到达率，使用流式响应。

## 选择负载

| 想测量什么 | 指南 |
| --- | --- |
| 重复发送一个提示词 | [固定提示词](fixed-prompt_zh.md) |
| 指定输入和输出 token 长度 | [随机负载](random_zh.md) |
| 真实对话历史 | [本地对话](conversations_zh.md)、[Hugging Face](huggingface_zh.md)、[ShareGPT](sharegpt_zh.md) |
| 工具调用请求 | [工具数据](tools_zh.md) |
| 混合数据集或模型的流量 | [多数据集](multi-dataset_zh.md) |
| 历史请求到达时间 | [StudyChat](studychat_zh.md)、[Mooncake trace](mooncake-trace_zh.md) |
| 一次返回完整回答 | [非流式请求](non-streaming_zh.md) |
| 视频生成 | [视频负载](video_zh.md) |

通过[请求速率与并发](arrival-rate_zh.md)控制负载，通过[参数扫描](sweep_zh.md)比较设置或部署，用 [SLO 测量](slo_zh.md)寻找满足延迟目标的负载水平。

## 评测已有服务

将以下 URL 和模型名换成服务的 Chat Completions 地址及公开模型 ID：

```bash
foretoken perf --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen/Qwen3-0.6B --prompt Hello \
  --num-prompts 20 --max-tokens 128 --output local
```

此模式不使用 Kubernetes；需要认证时添加 `--api-key`。Foretoken Gateway 部署直接传入 Kustomize 目录，自动查找路由地址和请求头。

## 查看结果

先查看成功率，再比较相同负载下的延迟分位数与吞吐量。[性能指标](../../metrics_zh.md)说明单位和统计口径。[W&B 图表](wandb_zh.md)用于查看随时间及逐请求变化的性能，[输出设置](../../README_zh.md#查看和保存结果)也支持导出本地图表。

全部参数见 `foretoken perf --help`。需要分析执行瓶颈时，另开一轮[性能剖析](../profile/README_zh.md)。
