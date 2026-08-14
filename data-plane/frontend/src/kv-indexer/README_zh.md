<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# KV 本地性索引

该 crate 根据模型服务器发送的标准化生命周期事件跟踪 KV 前缀本地性。

记录按事件源、ModelGroup、epoch、DP rank、partition 和存储位置隔离。路由绑定解析精确的事件源和 rank，只返回该路由能够读取的存储位置。HostPinned、Disk 和 External 存储位置还要求路由具备相应的恢复或传输能力。

## 事件处理

- `BlockStored` 提供可信的父链。
- `BlockRemoved` 只携带 hash。索引通过保留的反向元数据解析这些 hash，遇到未知 hash 时采用保守失败处理。
- `AllBlocksCleared` 清除匹配的事件源和 rank stream。

索引和查询全过程分别处理 Device、HostPinned、Disk 和 External 记录。

## vLLM 标准化

请求侧 hash contract 为 `normalized_keyed_blake3_v1`。model-server adapter 将 vLLM Store hash 和父链转换为该格式，并保留 Remove 事件所需的反向映射。Foretoken 不会将原始 vLLM hash 视为标准化 hash。

存储映射如下：

- `GPU` 和 `DEVICE` → Device
- `CPU` 和 `CPU_PINNED` → HostPinned
- `STORAGE`、`DISK` 和 `NVME` → Disk
- `REMOTE`、`EXTERNAL`、`NETWORK` 和 `SHARED` → External

## 同步

synchronizer 在将事件源标记为健康之前，会验证从零开始的 sequence 连续性。重复、缺失、乱序事件和 epoch 变化均不会导致发布部分状态。

两种索引实现共享该生命周期 contract。radix 实现使用 `patricia_tree` 提供压缩前缀存储；Foretoken 在其上增加事件、ownership、rank 和存储位置语义。
