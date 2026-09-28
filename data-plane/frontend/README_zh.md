<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Foretoken 前端

[English](README.md) | 简体中文

前端为已部署的模型提供统一的文本和视频生成入口。文本请求可以返回完整回答或逐步输出，视频请求可以直接将生成结果保存为文件。

## 连接服务

按仓库[快速开始](../../README_zh.md#快速开始)完成部署，再从仓库根目录执行以下命令，获取前端地址：

```bash
DEPLOYMENT=examples/quickstart
FRONTEND_URL="$(foretoken endpoint "$DEPLOYMENT")"
REQUEST_HOST="$(foretoken endpoint "$DEPLOYMENT" --host)"
```

下方请求携带 `Host` 请求头，可通过负载均衡地址或[网关](../../README_zh.md#网关模式)访问。TLS 加密和身份认证由集群入口配置。

## 文本生成

通过 `model` 指定模型标识。以下请求使用快速开始中部署的 `Qwen/Qwen3-0.6B`：

```bash
curl --fail-with-body "$FRONTEND_URL/v1/chat/completions" \
  -H "Host: $REQUEST_HOST" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Qwen/Qwen3-0.6B",
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 512
  }'
```

默认返回 JSON。在请求中添加 `"stream": true`，并为 `curl` 添加 `--no-buffer`，可实时接收生成内容。

### 选择接口

| 接口 | 路径 | 请求内容 |
| --- | --- | --- |
| OpenAI Chat Completions | `POST /v1/chat/completions` | `model`、`messages` |
| OpenAI Responses | `POST /v1/responses` | `model`、`input`；设置 `store: false`，每轮携带对话历史 |
| Anthropic Messages | `POST /v1/messages` | `model`、`messages`、必填的 `max_tokens` |
| Anthropic token 计数 | `POST /v1/messages/count_tokens` | 与生成请求一致的模型、消息、系统提示和工具定义 |
| 文本补全 | `POST /v1/completions` | `model`、`prompt` |

`GET /v1/models` 列出模型标识；`/tokenize` 和 `/detokenize` 用于文本与 token ID 之间的转换。

工具由客户端执行，再将结果传入下一轮请求。Responses 接口支持函数工具、带命名空间的函数和无语法约束的自定义文本工具，不支持服务端托管工具或该接口的后台执行模式。强制选择工具、严格约束工具参数时，模型服务需要支持结构化输出。

思考控制取决于模型的聊天模板。输出 token 预算包含思考内容；Messages 接口使用 `max_tokens`，不接受独立的 `thinking.budget_tokens`。预算耗尽时，Messages 返回 `max_tokens`，Responses 返回 `incomplete`。工具调用可能因此不完整，客户端只应执行完整的调用。

支持图片的文本模型接受 base64 编码的图片 `data:` URL，而非远程图片 URL。

## 视频生成

按 [MiniMax H3 配方](../../examples/recipes/minimax-h3/a100-bf16-tp2/README_zh.md)部署模型后，可以发送本地参考图片，等待生成完成并直接保存为 MP4 文件。

将 `REFERENCE_IMAGE` 改为本机 PNG 文件的路径，在仓库根目录执行：

```bash
DEPLOYMENT=examples/recipes/minimax-h3/a100-bf16-tp2
REFERENCE_IMAGE=/path/to/reference.png
FRONTEND_URL="$(foretoken endpoint "$DEPLOYMENT")"
REQUEST_HOST="$(foretoken endpoint "$DEPLOYMENT" --host)"
curl --fail --max-time 4000 \
  "$FRONTEND_URL/v1/videos/sync" \
  -H "Host: $REQUEST_HOST" \
  -F model=MiniMaxAI/MiniMax-H3 \
  -F 'prompt=A sailboat crossing a calm bay at sunrise' \
  -F "input_reference=@${REFERENCE_IMAGE};type=image/png" \
  -F width=1024 -F height=576 -F num_frames=124 -F fps=24 \
  -F num_inference_steps=50 -F aspect_ratio=16:9 -F flow_shift=12 -F seed=1 \
  -F 'extra_params={"task":"fl2va","audio_flow_shift":3}' \
  --output video.mp4
```

生成的视频保存为当前目录下的 `video.mp4`。根据参考视频生成的用法见 H3 配方。

### 提交后稍后获取结果

需要在提交成功后断开连接时，可使用 `/v1/videos`。这种方式将任务和结果保存在服务端，需先在部署的 `frontend.yaml` 中启用：

```yaml
spec:
  videoTasks:
    claimName: video-results
    retentionSeconds: 86400
```

`video-results` 是同一命名空间内已准备好的持久化存储卷声明（PVC），与模型缓存分开。前端和任务执行进程都需要访问该卷；跨节点部署时使用 ReadWriteMany 共享存储。将参考图片放入卷的 `inputs/reference.png`，再应用配置：

```bash
foretoken deploy "$DEPLOYMENT" --timeout 1h
```

此处的输入路径相对于存储卷根目录，不是本机路径。提交时使用 ModelService 名称 `h3`，而不是模型仓库 ID：

```bash
curl --fail-with-body "$FRONTEND_URL/v1/videos" \
  -H "Host: $REQUEST_HOST" \
  -H 'Content-Type: application/json' \
  -d '{
    "modelServiceRef": {"name": "h3"},
    "request": {
      "task": "fl2va",
      "prompt": "A sailboat crossing a calm bay at sunrise",
      "width": 1024, "height": 576,
      "numFrames": 124, "fps": 24, "numInferenceSteps": 50,
      "inputFiles": [{
        "field": "input_reference",
        "path": "inputs/reference.png",
        "contentType": "image/png"
      }]
    }
  }'
```

提交成功返回 HTTP `202`，响应包含 `id`、`status_url` 和 `content_url`。后续操作使用同一个前端地址，将 `{id}` 替换为返回的任务 ID：

| 操作 | 接口 | 使用时机 |
| --- | --- | --- |
| 查询状态 | `GET /v1/videos/{id}` | `Pending`、`Starting`、`Running` 表示尚未完成；`Failed` 时查看 `reason` 和 `message` |
| 保存视频 | `GET /v1/videos/{id}/content` | `phase` 为 `Succeeded` 后，用 `curl --output video.mp4` 保存响应 |
| 取消任务 | `POST /v1/videos/{id}/cancel` | 返回 `202` 后继续查询，直到任务进入终态；后端计算可能仍在结束中 |
| 删除任务 | `DELETE /v1/videos/{id}` | 返回 `202` 后，服务清理任务及其文件 |

以上配置从任务结束起保留结果一天，到期后自动清理；`inputs/` 中的原始参考文件保留。

## 运维

| 接口 | 用途 |
| --- | --- |
| `/healthz` | 前端进程存活状态 |
| `/readyz` | 接收生成请求的就绪状态 |
| `/statusz` | 服务和缓存索引状态 |
| `/metrics` | Prometheus 指标 |

运维接口的访问范围由集群网络策略控制；网关对外提供 `/v1`、`/tokenize` 和 `/detokenize` 客户端路径。

使用 `foretoken status` 查看部署状态，使用 `foretoken delete` 删除部署，均传入对应配置目录。
