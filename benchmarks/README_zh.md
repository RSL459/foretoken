# Benchmarks

[English](README.md) | 简体中文

`benchmarks/` 是 Foretoken 的评测模块。

它可通过 Kustomize 发现 Foretoken 服务，也可连接现有的 OpenAI 兼容端点，用于运行可复现的延迟和吞吐量实验。

## 适用场景

- 了解当前服务在特定并发度或到达率下的延迟和吞吐量。
- 比较不同并发度、请求数量、生成参数或服务端配置的表现。
- 在给定的延迟和吞吐要求下，确定合适的负载点或容量方案。

## 主要功能

| 功能 | 说明 |
|---|---|
| 性能压测 | 发送受控负载，测量延迟、吞吐量、首个 token 时延等指标 |
| 负载扫描 | 对多个并发度、请求数或到达率进行扫描，观察性能变化 |
| 参数扫描 | 批量比较请求参数和负载配置 |

## 会产出什么

- 控制台中的易读汇总结果
- 本地保存的配置、原始结果和指标，方便事后复查
- W&B 可用时上传实验记录与图表

默认显示控制台汇总、保存本地产物并上传 W&B。W&B 不可用时会给出提示并继续保存本地结果。使用 `--output local` 可关闭上传，加入 `quiet` 可关闭控制台输出。本地文件保存在 `--output-dir` 指定的目录中。

## 示例

评测 Foretoken 的 Kubernetes 部署。若服务已存在则直接复用；若尚未部署，CLI 会部署渲染后的资源，并在评测结束后仅清理本次创建的资源。未指定 `--prompt` 或 `--dataset` 时，使用一个简短的内置提示词：

```bash
foretoken bench examples/quickstart
```

常用采样参数可直接指定；其他与 OpenAI 兼容的请求字段或后端扩展字段可通过 `--extra-body` 传入：

```bash
foretoken bench examples/quickstart \
  --temperature 0 \
  --top-p 1 \
  --top-k 0 \
  --extra-body '{"seed":7,"min_tokens":8}'
```

使用固定提示词评测现有端点：

```bash
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --prompt "hello" \
  --parallel 2 \
  --number 20
```

本地数据集文件：

```bash
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --dataset /path/to/conversation.jsonl \
  --parallel 4 \
  --number 20
```

轨迹回放使用 `--trace` 提供到达时间，使用 `--dataset` 提供请求内容。
它支持本地 JSONL、Hugging Face 数据集和 `hf://` 文件，并自动识别 StudyChat 或 Mooncake 格式。

```bash
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --trace KrisQ/StudyChat \
  --dataset KrisQ/StudyChat \
  --trace-start 600 \
  --trace-duration 300 \
  --trace-max-concurrency 32
```

时间窗口为 `[first + start, first + start + duration)`，窗口起点是回放时间零点。
`--trace-max-concurrency` 限制活跃请求数，等待并发槽位的时间计入回放延迟。
Mooncake 可以组合随机负载或外部数据集请求内容，也可以合成共享前缀块。
完整用法和运行截图见 [trace 示例](docs/examples_zh.md)。

使用随机生成的提示词进行压测（需指定 tokenizer）：

```bash
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --dataset random \
  --tokenizer-path Qwen/Qwen3.6-27B \
  --random-seed 0 \
  --min-prompt-length 128 --max-prompt-length 512 \
  --parallel 4 --number 20 --max-tokens 64 \
  --rate 5
```

Hugging Face 数据集 ID（数据行格式：`messages` / `prompt` / `user`[+`system`]）：

```bash
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --dataset r0b0tlab/qwen3.8-max-distillation-50k:train \
  --parallel 4 \
  --number 20
```

多个 JSONL 和 Hugging Face 数据源可用逗号分隔。`--number` 由全部数据源共享并按顺序分配；不能整除时，前面的数据源各多一个请求。各数据源按顺序运行，随后合并结果。启用 W&B 输出时，一次实验对应一个 **group**，每个数据集对应一个 **run**：

```bash
foretoken bench \
  --url http://127.0.0.1:8008/v1/chat/completions \
  --model Qwen3.6-27B \
  --dataset /path/a.jsonl,org/name:train,/path/b.jsonl \
  --parallel 4 \
  --number 30
```

### 参数扫描

评测 Foretoken Kustomize 部署时，通过 `--bench-params` 传入 JSONL 文件，比较请求执行配置和负载点。运行结果会记录全部负载点，并生成“每用户输出 token/s”对“每 GPU 输出 token/s”的 Pareto 图。完整命令见[参数扫描示例](docs/examples_zh.md#参数扫描)。
