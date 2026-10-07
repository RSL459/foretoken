# 视频生成评测

[English](video.md) | 简体中文 · [性能评测示例](README_zh.md)

评测已有的同步视频生成服务，并保存生成的视频。将下面的 URL 换成服务端点，在仓库根目录运行：

```bash
foretoken perf video --url http://127.0.0.1:8091/v1/videos/sync \
  --dataset VideoArgusBench/TI2V --num-prompts 10 --output local
```

数据集及参考媒体会自动下载。开始前检查服务的 `/health`；健康端点位于其他地址时，用 `--health-url` 指定。此命令使用服务的 multipart 视频 API，不使用快速开始的 Chat Completions 模型。

## 查看结果

命令打印的 `results/video/` 下结果目录包含生成的 MP4、`metrics.json`、`raw_results.json` 和 `config.json`。`--output-dir` 修改父目录。汇总展示成功情况及成功请求的平均耗时，逐请求记录保留错误、生成参数和输出路径。

E2E 优先采用服务报告的推理时间，没有时使用客户端耗时；`client_e2e_s` 始终记录客户端计时。阶段耗时和 GPU 峰值显存取自服务报告。安装 `ffprobe` 后，会检查输出分辨率和帧数。

![视频评测汇总](../imgs/video-ti2v-benchmark-summary.png)

## 选择数据集

| 选择器 | 输入 | 服务任务 |
| --- | --- | --- |
| `VideoArgusBench/T2V` | 文本 | `t2va` |
| `VideoArgusBench/TI2V` | 文本和图片 | `fl2va` |
| `VideoArgusBench/TS2V` | 文本和参考媒体 | `ref2va` |
| `VideoArgusBench/TV2V` | 文本和视频 | `ref2va` |
| `VideoArgusBench/TSV2V` | 文本和参考媒体 | `ref2va` |

`--dataset-offset` 跳过开头的数据行。省略 `--num-prompts` 或设为零时使用全部选中记录。

原生 JSONL 数据每行提供自己的生成设置，例如：

```json
{"id":"sample-1","task":"t2va","prompt":"A boat crossing a quiet lake.","width":1024,"height":576,"num_frames":124,"fps":24,"num_inference_steps":50}
```

参考媒体通过 `files` 列表指定，每项含 `field`、`path` 和可选 `content_type`；路径相对于数据文件，multipart 字段名称需与服务 API 一致。

## 调整生成参数和负载

VideoArgusBench 默认使用 1024×576、124 帧、24 fps 和 50 个推理步骤。可通过 `--width`、`--height`、`--num-frames`、`--fps`、`--num-inference-steps` 覆盖。`--flow-shift`、`--audio-flow-shift`、`--aspect-ratio`、`--seed` 设置服务支持的生成控制；基础 seed 会加上数据行索引。TI2V 按图片尺寸确定比例，不使用 `--aspect-ratio`。

默认并发为 1，请求超时为一小时。`--warmup-requests N` 先完成 N 个选中请求，再正式测量选中的负载。`--duration 5min` 在五分钟后停止启动新请求，已发送请求继续完成。

比较生成设置和负载：

```bash
foretoken perf video --url http://127.0.0.1:8091/v1/videos/sync \
  --dataset VideoArgusBench/TI2V --num-prompts 10 \
  --sweep benchmarks/examples/video-sweep.jsonl --num-runs 2 --output local,plot
```

执行 `wandb login` 后，可将 `wandb` 加入 `--output`，在线查看逐请求指标。全部参数见 `foretoken perf video --help`。
