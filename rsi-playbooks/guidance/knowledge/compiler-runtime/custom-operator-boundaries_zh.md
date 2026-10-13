<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 自定义算子边界与编译器可见性

[English](custom-operator-boundaries.md) | 简体中文

独立内核很快，但接入编译模型后没有收益，周围出现更多 graph break，或原有 pass 不再识别计算时，应检查算子的编译接口。

## 内核也是编译器接口

注册自定义算子需要参数 schema、设备分派实现和只计算元数据的 FakeTensor 实现。后者描述输出形状、dtype、device 与必要布局关系，不执行真实算术；mutation 和 alias 声明则告诉编译器哪些值可以变化。

编译器可以追踪这个调用，却把内部原生实现视为不透明操作。这样避免追踪复杂设备或主机逻辑，也隐藏了与相邻操作融合的机会。完成注册意味着能接入编译图，不代表编译器能优化其内部循环。

PyTorch 已直接支持这些契约，vLLM 也已有自定义 attention 操作与显式编译／融合 pass。新算子应融入现有边界，而不是建立另一层 tracing 或 dispatch。

## 跟随替代操作穿过编译图

以原生算子替换 `归一化 → 类型转换 → 投影` 为例。如果 FakeTensor 返回连续输出，而真实内核返回带 stride 的 view，下游布局假设就可能错误。若声明纯函数却修改输入，编译器可能错误复用或重排数据。即使元数据正确，不透明调用也可能挡住原有的转换与投影融合。

这里有三种不同设计：保留可见张量表达式，供编译器变换；用不透明内核承担适合手写调度的完整职责；或让已有编译 pass 识别支持的模式，再替换成该内核。

vLLM 的 Q/K 归一化与 RoPE 融合已采用第三种方式。关键是匹配实际模型图并保留 packed buffer 语义，不是多注册一个函数名。

## 能追踪与能捕获是两回事

不透明算子内部仍可能复制到 CPU、在主机读取设备标量，或使用不兼容的分配方式。Dynamo 追踪成功，不证明 CUDA Graph 安全。PyTorch 文档已提供 unsafe operation tag，以及把不兼容操作分离出去的 graph partition。研究选择在于边界放在哪里、代价多大，而非重建这套能力。

有状态推理内核需明确表达缓存写入和输入输出别名。缓存生命周期仍由引擎管理，局部算子不应隐式保存每请求缓冲区，形成另一套状态生命周期。

## 实验方式

适用时比较完整的原张量表达式、不透明替代和模式匹配替代三条路径，检查图分区、额外复制、生成内核及实际分派。数值对照保留真实 stride 和 mutation，并连续执行多步，加入仍持有原输入的其他消费者。

PyTorch `opcheck` 能检查注册与框架集成，不证明自定义算法的数学正确性；后者由已有模型／参考对照负责。推理专用内核只有实际消费者需要训练时，才涉及梯度支持。

预热后测完整层与服务性能，另外记录新增编译和启动成本。局部内核更快，却多一次中间张量落地或 graph break，整体可能反而变慢。

## 来源与实现状态

核对日期：2026-10-14。

- [PyTorch C++／CUDA 自定义算子教程](https://docs.pytorch.org/tutorials/advanced/cpp_custom_ops.html)：schema、FakeTensor、mutation 与注册检查。
- [vLLM v0.31.0 编译设计](https://docs.vllm.ai/en/v0.31.0/design/torch_compile/)：attention 边界与分段编译。
- [已有 QK 融合 pass](https://github.com/vllm-project/vllm/blob/db9527a46873454610df6dbedf79a36d6bf1a7f6/vllm/compilation/passes/fusion/qk_norm_rope_fusion.py)。
- [PyTorch v2.14 图分区与不安全自定义算子](https://github.com/pytorch/pytorch/blob/v2.14.0/docs/source/user_guide/torch_compiler/torch.compiler_cudagraph_trees.md)。
