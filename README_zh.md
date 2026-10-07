# Foretoken

[English](README.md) | 简体中文

Foretoken 在 Kubernetes 上部署和管理生成式推理服务，提供请求路由、自动扩缩容、评测与可观测性，支持 NVIDIA 和沐曦 GPU。

## 功能与进展

| 能力 | 指南 | 状态 |
| --- | --- | --- |
| 根据负载和 KV 缓存位置分配请求 | [请求路由](data-plane/frontend/src/router/README_zh.md) | 研究中 |
| 按需求调整模型容量 | [自动扩缩容](docs/autoscaling_zh.md) | 开发中 |
| 分离部署编码、预填充和解码阶段 | [E/P/D 示例](examples/encoder-prefill-decode/README_zh.md) | 研究中 |
| 测量服务性能与回答质量 | [评测](benchmarks/README_zh.md) | 开发中 |
| 查看 CPU/GPU 执行过程 | [性能剖析](benchmarks/docs/profile/README_zh.md) | 开发中 |
| 查看指标、日志与告警 | [可观测性](observability/README_zh.md) | 开发中 |

## 快速开始

下面使用 k3d，在本地 NVIDIA GPU 上运行 `Qwen/Qwen3-0.6B`。准备一台安装了 Python 3.11+、Docker、NVIDIA Container Toolkit、k3d、kubectl 和 Helm 的 Linux 主机，环境配置见 [k3d 指南](docs/k3d-deployment_zh.md)。示例模型申请一张 GPU、4 个 CPU 和 48 GiB 主机内存。

其他环境请使用 [Kubernetes](docs/kubernetes-deployment_zh.md)、[kind](docs/kind-deployment_zh.md) 或[沐曦部署指南](docs/metax-deployment_zh.md)。

### 安装并部署

```bash
git clone https://github.com/shiweijiezero/foretoken.git
cd foretoken
pip install -e .

# 选择 nvidia-smi 显示的 GPU 0。
foretoken cluster create k3d --name foretoken-dev --gpus 0
foretoken install -e .
foretoken deploy examples/quickstart --timeout 20m
```

部署会启动一个前端和一个模型副本。等待服务 Ready 后，发送请求：

```bash
FORETOKEN_FRONTEND_URL="$(foretoken endpoint examples/quickstart)"

curl --fail-with-body --no-buffer \
  "$FORETOKEN_FRONTEND_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen/Qwen3-0.6B","messages":[{"role":"user","content":"你好"}],"stream":true}'
```

回答会逐步显示在终端。其他 API 和准入配置见[前端指南](data-plane/frontend/README_zh.md)。

### 测量性能

```bash
foretoken perf examples/quickstart --num-prompts 20 --output local
```

从汇总结果查看延迟、吞吐量和请求成功情况。更多用法见[性能负载](benchmarks/docs/perf/README_zh.md)、[质量评测](benchmarks/docs/eval/README_zh.md)与[性能剖析](benchmarks/docs/profile/README_zh.md)。

### 更新服务

修改源码或部署配置后，重新执行 `foretoken deploy examples/quickstart --timeout 20m`。修改推理引擎见[源码部署](docs/custom-deployment_zh.md)，使用发布版本见[命令行指南](cli/README_zh.md)。

## 网关模式

需要按域名提供统一入口时，按[网关配置](cli/README_zh.md#网关模式)部署。

## 停止与卸载

```bash
foretoken delete examples/quickstart
foretoken uninstall
foretoken cluster delete k3d --name foretoken-dev
```

使用已有集群时，不执行最后一条命令。卸载平台会保留日志存储和复用的安装。

## 相关项目

- [vLLM](https://github.com/vllm-project/vllm)
- [NVIDIA Dynamo](https://github.com/ai-dynamo/dynamo)
- [llm-d](https://github.com/llm-d/llm-d)
- [AIBrix](https://github.com/vllm-project/aibrix)
- [vLLM Production Stack](https://github.com/vllm-project/production-stack)

## 贡献

欢迎参与代码、文档、测试和设计。开发与评审流程见[贡献指南](CONTRIBUTING_zh.md)。

感谢所有为 Foretoken 做出贡献的开发者。

<a href="https://github.com/shiweijiezero/foretoken/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=shiweijiezero/foretoken" width="256" alt="Foretoken 贡献者" />
</a>

## 许可证

[Apache License 2.0](LICENSE)。
