# 维护沐曦 GLM-5.3 支持

[English](README.md) | 简体中文

本补丁包将 GLM-5.3 适配到沐曦源码运行时。平台源码安装会自动应用补丁，入口见[沐曦平台准备](../../../../../../docs/development/metax-platform_zh.md#从源码安装)。

## 更新源码组合

[`source-environment.json`](../../../source-environment.json) 指定 vLLM 核心、沐曦插件及各目标的补丁顺序。更新源码组合时，同步调整补丁。核心和插件补丁在 wheel 构建前应用；已安装包的补丁修改 DeepGEMM，因此在依赖安装后应用。

在具备 Docker BuildKit 的机器上，从仓库根目录构建运行时：

```bash
make image-vllm-metax VLLM_METAX_IMAGE=foretoken-vllm-metax:latest
```

构建 model-server 时使用该镜像作为推理运行时；如何在集群中选用它，见[源码部署指南](../../../../../../docs/custom-deployment_zh.md#更换运行环境)。

## 验证模型执行

在沐曦设备上运行受影响的模型与权重格式。修改量化加载时，验证 compressed-tensors 投影层及专家并行执行；修改稀疏注意力或推测解码时，覆盖长输入预填充、解码和所用草稿方法。模型参数可参考[上游 GLM-5.3 配方](https://recipes.vllm.ai/zai-org/GLM-5.3-Flash)，模型执行器仍由核心自动选择。

修改 mHC 残差混合时，保持上游的 FP32 运算、中间结果 BF16 舍入、配置指定的 Sinkhorn 迭代次数，以及一次输入归一化。图捕获仍由模型执行器负责。相关上游工作见 [vLLM #56856](https://github.com/vllm-project/vllm/pull/56856)。

KDA 重计算内核使用 8 个 warp、3 个流水线阶段。2 阶段配置可能使 W 变换计算错误，导致长输入预填充期间出现非有限递归状态；修改该配置时，同时检查数值结果和耗时。

修改数据并行草稿路径时，检查活跃与空闲成员。运行时占位批次跳过稠密 DFlash/DSpark 候选生成，但保留目标模型同步，以及性能剖析、预热和图捕获期间的草稿执行。
