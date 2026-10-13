<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 冷热状态与 Sleep/Wake 恢复

[English](sleep-wake-recovery.md) | 简体中文

恢复成本取决于什么仍然存在：检查点文件、主机权重副本、活着的内存 owner，还是请求 token 历史。“热”不是单一状态，同一 GPU 上睡眠引擎与重启进程可能走完全不同的路径。

## 区分保留下来的状态

vLLM [当前 sleep 指南](https://docs.vllm.ai/en/latest/features/sleep_mode/)中，level 1 将权重备份到 CPU，丢弃 KV；wake 恢复权重，但请求仍可能需要重新 prefill。level 2 丢弃权重和 KV，将必要 buffer 保存在 CPU。仅唤醒分配并不会重新加载已丢弃权重，文档流程是唤醒 weights、重新加载、再唤醒 KV。支持部分唤醒，但调度须等待所需部分就绪。

level-1 wake 的载荷下限约为 `W/B`，W 是权重字节，B 是有效 H2D 带宽，另有分配/恢复和请求重放。level 2 还增加来源读取和转换。保留 40 GiB 主机权重可以省加载，却占用相应 RAM；名义更快的恢复若触发回收或挤掉另一进程，并非完整改善。

活着的外部内存 owner 是第三种情况。vLLM [weight-cache IPC loader](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/model_executor/model_loader/weight_cache/ipc_loader.py)可零拷贝安装 daemon 所有的 CUDA IPC 张量，也可复制到引擎自有内存。零拷贝要求 daemon 存活，且不兼容 sleep-mode 权重卸载。复制模式花费设备内存和拷贝时间，但转移所有权。复用还要求模型、并行方式、角色和 GPU 身份匹配，不是可移植进程检查点。

Dynamo [GMS artifact](https://github.com/ai-dynamo/dynamo/blob/7708f041a965e35374af976ab8ad610b9537e3bc/lib/gpu_memory_service/v1/snapshot/weight_artifact.py)保存原始 allocation 字节并恢复到新 server。映射时本地 client 与 sidecar 必须解析到同一物理 GPU；分配粒度和外部重建元数据也有意义。该格式不是张量级跨拓扑检查点，但这项本地设备检查本身，也不能证明兼容消费者无法在别处恢复产物。

## 权重恢复不等于请求恢复

[ServerlessLLM 原方法](https://arxiv.org/html/2401.14351v1)重放输入和已生成 token 来重建 KV，切换前再补第二次 token 更新，省去完整 KV 传输，但花费 prefill 计算。精确重放需要相同历史与模型状态；保留已生成 token 不等于用新采样重新生成。

LMCache 可在引擎外保留可复用 KV，Mooncake 提供搬运和权重状态元数据，但重启 worker 仍须具有兼容 key、形状与引擎接入。外部缓存存在不代表所有在途请求可恢复。Dynamo、ModelExpress 提供额外加载路径，副本恢复策略仍属服务职责。以上边界依据 [2026-10-14 快照](README_zh.md#来源快照)核对。

## 能区分状态的实验

局部比较冷进程启动、热文件系统启动、level-1 sleep/wake、level-2 明确 reload，以及支持的 daemon 复用，记录保留的主机/设备字节、搬运量、恢复阶段与 next-token 一致性。再改变内存 daemon 是否存活；daemon 活着时零拷贝重启快，不能说明整节点故障恢复快。

请求恢复固定 token 历史和权重修订，对照完整重放、外部 KV 恢复，以及权重改版后的重放。检查 next-token 分布，而非仅看 HTTP 成功。权重改变会破坏复用旧 KV 的语义前提。

服务侧测恢复后首个成功生成和后续几次请求，加入长上下文与并发流量，记录重放工作及对同机服务的影响。剩余研究是满足需求的最低成本保留状态及其生命周期。

[模型加载与存储](README_zh.md)
