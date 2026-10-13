<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 图与 stream 的跨 backend 约束

[English](graph-stream-portability.md) | 简体中文

图重放减少重复 host launch，辅助 stream 让独立设备工作重叠。两者依赖的不只是算子签名。CUDA、ROCm、MACA 之间迁移，需要核对 capture 能力、communicator 顺序、stream 绑定和临时内存生命周期，而非简单开启同名图模式。

## 重放以形状与内存换 launch 开销

一次前向发射 `n` 个小 kernel 时，host launch 成本约为 `n t_launch`。capture 可以减少重复提交，却不会自动减少 kernel 算术。重放还需保留 buffer，可能把真实 token 数 M 补到捕获大小 G，增加 `(G−M)` 行计算。

例如九个 token 的 decode batch 重用十六 token 图，多算七行是否值得，取决于减少了多少 launch，以及额外 GEMM/专家工作有多贵。speculative decode 每请求有多个 query token，只用请求数作为图 key 不够。

当前 vLLM 已将编译与 capture 分开，提供 full/piecewise 模式，按 batch 描述和 backend 能力 dispatch。`FULL_DECODE_ONLY` 不捕获 prefill，`FULL_AND_PIECEWISE` 对 uniform decode 用 full、其他走 piecewise；没有相容 key 时执行 eager。它们是已有设施。设计文档保留部分历史背景，其中旧的未来默认值说明不能替代目标版本配置。

## Stream 与 collective 共同构成依赖图

主流生成输入，辅助流算共享专家，主流最后合并结果：输入消费前需要 main→aux 依赖，输出使用前需要 aux→main 依赖，workspace 与输出也必须存活到完成。capture 还增加重放生命周期：地址和依赖应在以后 replay 时合法，而不只是 warmup 成功。

NCCL 当前文档要求各 rank capture 参与一致，描述了捕获和普通操作混合，并说明同一线程启动多个 communicator 图可能 deadlock。这不能证明 RCCL 或 MCCL 语义完全相同；一个库支持的设置不能只按名称移到另一库。

算子绑定当前 stream 是必要条件，但不足以证明并发安全，库内静态 workspace 仍可能被同时复用。反过来，wrapper 缺少某个 allocator 注记也不等于已经证明提前释放；应读真实输入输出事件和 ownership 后再判断。

## 当前集成与剩余空间

AMD vLLM 指南已有各 attention backend 的图模式选择。MetaX 用 hardware plugin、版本相关原生库和 communicator override；已核对实现明确让 MACA all-gather 走基础 process-group 路径。图支持结论必须覆盖实际调用链，不能只测一个直接通信 wrapper。

可继续优化的是依据真实形状选择 capture size 与受支持 overlap，同时保持持续进展。BF16、量化模型、hybrid attention、共享专家和 speculative decode 都可能受影响。更多 capture 不一定更好：图占用可能降低可服务容量，某段 eager 也可能仍主导延迟。

## 有区分力的实验

使用既有 graph dispatcher 和相同算子/backend，比较 eager、decode-only capture 与支持的 mixed mode。局部检查 warmup/replay 差异、launch 间隙、padding、内存、当前 stream 和完成事件。应包含 rank 间 token 数不等和混合 prefill/decode，不只重复同一 batch。

服务性能使用无 profiling 开销的运行，观察 TTFT、TPOT、成功输出、长期进展与内存余量。overlap 失败时，先保留 communicator 身份和设备完成边界，再改同步。每轮全局 synchronize 的微基准，可能掩盖它本来要复现的顺序问题。
## 来源

核对日期：2026-10-14。

- [已核对 commit 的 vLLM 图设计](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/design/cuda_graphs.md)。
- [NCCL 图执行契约](https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/usage/cudagraph.html)。
- [AMD 图模式选择](https://rocm.docs.amd.com/projects/ai-ecosystem/en/latest/optimization/vllm-v1-optimization.html)。
- [MetaX communicator 实现](https://github.com/MetaX-MACA/vLLM-metax/blob/cec91763dbe968fe4478fc066f57ecf5877c3965/vllm_metax/distributed/device_communicators/cuda_communicator.py)。

[异构执行](README_zh.md) · [编译与 runtime](../compiler-runtime/README_zh.md) · [知识索引](../README_zh.md)
