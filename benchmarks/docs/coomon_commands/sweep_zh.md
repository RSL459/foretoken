# 参数扫描

[English](sweep.md) | 简体中文 · [常用命令](../examples_zh.md)

完成[准备步骤](../examples_zh.md#准备)后，先部署服务并预热，再比较不同并发：

```bash
foretoken deploy examples/quickstart --timeout 20m
for parallel in 1 2 4; do
  foretoken bench examples/quickstart \
    --dataset random --tokenizer-path Qwen/Qwen3-0.6B \
    --min-prompt-length 128 --max-prompt-length 256 --random-seed 0 \
    --min-output-length 256 --max-output-length 256 \
    --parallel "$parallel" --number 16 --output local
done
```

使用相同输入运行[参数文件](../../examples/sweep.jsonl)：

```bash
foretoken bench examples/quickstart \
  --dataset random --tokenizer-path Qwen/Qwen3-0.6B \
  --min-prompt-length 128 --max-prompt-length 256 --random-seed 0 \
  --sweep benchmarks/examples/sweep.jsonl \
  --experiment-name quickstart-sweep \
  --output local,wandb
```

每行 JSONL 定义一组参数，`parallel`、`number` 或 `rate` 的列表会展开成负载点。同一行只能将 `parallel` 或 `rate` 中的一个设为多值列表；`number` 也是多值列表时，长度需与该轴一致。

每行可以改变负载、生成或数据集设置，包括输出长度上下界。服务身份、凭据、轨迹来源和结果去向保持不变。扫描不与轨迹回放或多数据集组合。`--num-runs` 可重复运行各参数点。

每个参数点都有结果目录。`sweep_points.json` 保存全部结果；有效点足够时，`pareto/PARETO.png` 比较每个配置用户与每张 GPU 的输出 token 吞吐量。再次实验时选择新的 `--experiment-name`，或省略它使用自动创建的目录。

使用完后，执行 `foretoken delete examples/quickstart` 删除服务。

## 输出示例

单张 A100 80GB PCIe 上的 Qwen3-0.6B：

![扫描命令的实际输出](../imgs/sweep-cli.png)

W&B 按一秒完成窗口展示 E2EL p95；帕累托图比较整组吞吐量。

![按一秒完成窗口统计的 E2EL p95 时间曲线](../imgs/sweep-wandb.png)

![实测帕累托前沿](../imgs/sweep-pareto.png)
