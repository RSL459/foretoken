# 到达模式与并发

[English](arrival-rate.md) | 简体中文 · [性能评测示例](README_zh.md)

用并发测量服务容量，或用请求速率模拟持续到达的流量。完成[准备步骤](README_zh.md#准备)后运行以下示例。

## 持续填满并发

```bash
foretoken perf examples/quickstart --prompt Hello \
  --max-concurrency 16 --num-prompts 100 --max-tokens 128 --output local
```

不限速时，有空位就启动新任务。`--max-concurrency` 默认为 1，设为 `-1` 可取消上限。多轮数据中，该参数限制同时进行的对话数，`--num-prompts` 则统计全部 HTTP 轮次。

## 设置到达率

```bash
foretoken perf examples/quickstart --prompt Hello \
  --request-rate 5 --max-concurrency 16 --num-prompts 100 \
  --max-tokens 128 --output local
```

该命令按泊松过程发送请求，目标平均速率为每秒 5 个请求。多轮数据的速率控制对话启动次数。先前任务尚未完成时，并发限额会延后启动；设为 `--max-concurrency -1` 可去掉这一约束。

| 到达方式 | 时间间隔 |
| --- | --- |
| `--arrival-pattern poisson`（默认） | 随机间隔，平均速率为设定值 |
| `--arrival-pattern constant` | 固定间隔 |
| `--arrival-pattern gamma --burstiness 0.5` | 突发到达；形状参数越小越突发，1 等同于泊松到达 |

`constant` 和 `gamma` 需要正数 `--request-rate`。默认的 `--request-rate -1` 表示尽快发送。按历史时间戳发送请求，见[轨迹回放](studychat_zh.md)。

## 按时长测量

```bash
foretoken perf examples/quickstart --prompt Hello \
  --max-concurrency 16 --duration 5min --max-tokens 128 --output local
```

五分钟后停止发送新请求，已发送的请求继续完成。只按时长运行时省略 `--num-prompts`；同时指定数量和时长时，到达任一边界就停止。既不限并发又不限速的负载需要请求数量预算，不能使用 `--duration`。

时间参数支持 `ms`、`s`、`m`/`min`、`h`、`d`，无单位时按秒解释。可用 `--warmup-requests` 在测量前预热，预热不计入正式汇总。

## 查看负载下的表现

比较目标速率、实际吞吐量、实测请求并发和延迟分位数。[参数扫描](sweep_zh.md)用于比较多个速率或限额，[SLO 测量](slo_zh.md)展示满足延迟目标的请求比例。

![到达率评测汇总](../imgs/arrival-rate-cli.png)
