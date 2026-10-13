<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 分布式权重存储与 Peer 加载

[English](distributed-weight-storage.md) | 简体中文

热 peer 可以提供已安装权重，共享存储则可能提供检查点文件或准备好的产物，省掉的启动工作不同。字节传输兼容还需要模型身份、rank 布局和运行时解释一致，仅能连通 peer 不够。

## 先看来源表示

文件缓存命中后仍需解析检查点、安装参数。运行时张量 peer 的名称、形状、dtype、分片与 backend 表示匹配时，可以避免重复转换。allocation artifact 提供原始字节，需要额外信息重建张量 view。三者都不自动恢复请求 KV 或执行状态。

例如一个 rank 需要 10 GiB 运行时权重，peer 有效 40 GiB/s 时仅载荷就需 250 ms，文件源 5 GiB/s 时需 2 s。元数据发现、注册、源同步、安装和预热另计。多个目标同时加载会分摊源带宽，还可能与源的推理竞争；不读取模型文件不意味着加速无成本。

完整流水要发现兼容源、取得张量 manifest、分配目标、规划并执行搬运、确认完成、补齐引擎特有状态，再发布目标可用。如果尝试已部分修改目标，重试不能混合两个不兼容来源。恢复边界由 loader 负责，不由外部 benchmark 客户端接管。

## 当前上游路径

[ModelExpress 架构](https://github.com/ai-dynamo/modelexpress/blob/db0cbce97184d9135d35c7290711f3053b220b6a/docs/ARCHITECTURE.md)和 [vLLM loader](https://github.com/ai-dynamo/modelexpress/blob/db0cbce97184d9135d35c7290711f3053b220b6a/modelexpress_client/python/modelexpress/engines/vllm/loader.py)已有策略链：peer RDMA、满足条件的 server cache、InstantTensor、ModelStreamer、GDS、引擎原生加载。是否可用取决于来源状态与配置。peer 字节通过 NIXL 搬运，不经过中央 server；没有共享存储时，文件缓存流式重建本地 snapshot。

vLLM 已有[原生 ModelExpress wrapper](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/model_executor/model_loader/modelexpress_loader.py)。实际 fallback 与兼容条件需继续读 ModelExpress，不能从薄 adapter 推断。选择实时张量时，source/runtime 身份与 worker incarnation 都有意义。

Mooncake [权重管理说明](https://github.com/kvcache-ai/Mooncake/blob/342c8aeece6b4eefb76c6b8b31ccfac8dde07aa3/docs/source/design/mooncake-reshard/weight-management.md)区分已实现的发布/修订元数据、lease 状态和 HA 恢复，与待完成的客户端/RPC 表面及 managed reader 接入。后续工作应继续检查 `weight_store_manager.cpp` 和 `weight_metadata_store.cpp`。

Dynamo [weight artifact](https://github.com/ai-dynamo/dynamo/blob/7708f041a965e35374af976ab8ad610b9537e3bc/lib/gpu_memory_service/v1/snapshot/weight_artifact.py)保存对齐 allocation 范围，并恢复到新的 GMS server；不编码张量名称、形状和 dtype。LMCache 的 KV 持久化处理另一类对象，不能作为权重检查点。各版本见[来源快照](README_zh.md#来源快照)。

## 区分瓶颈的实验

局部比较原生加载、热文件缓存、兼容 peer 和支持的 artifact restore，固定模型修订、运行时 dtype、转换与 rank 几何。记录发现、源就绪、注册、载荷、最终处理、存储流量及源 worker 延迟，确认实际选中策略；退回原生路径后成功，不能算 peer 路径验证通过。

分别测一个与多个同时加载目标。peer 时间随目标数增长但文件解析消失，说明源扇出主导；搬运很快而就绪不变，说明最终处理或预热主导。加入源离开和部分搬运，核对 loader 的真实恢复行为。

服务侧验证 logits、生成结果、就绪到可用响应，以及对正在服务的源的影响。剩余空间是兼容表示复用、源扇出和生命周期接入。

[模型加载与存储](README_zh.md)
