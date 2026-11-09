# 公共评测组件

本模块负责执行、调度、质量判定调用和结果保存，不负责数据标准、数据读取或转换，也不负责三类优化方法的配对统计。

## 接入契约

受信任的 `module:function` 接收入口配置与配置所在目录，返回 `Task`：

- `items`：已准备好的 `WorkItem`。ID、到达时刻、deadline、dependencies 供调度使用；payload 与 reference 不透明地传给执行/校验函数。
- `execute(item, emit)`：调用候选，返回 JSON 可保存的值或 dataclass。
- `judge(item, output)`：返回 `Verdict`；此函数属于评测方，不能由候选自评。
- `setup/teardown`：运行前准备和结束清理。
- `observers`：公共或引擎专属采样，提供 start(output_dir) / finish(output_dir)。

vLLM 的便捷接入函数是 `adapters.llm.provider.create_task(items, endpoint=..., model=...)`，直接接收现成 WorkItem，不加载文件。其默认严格 token 比较可替换成可信质量判定。

```bash
python -m evaluation.run --provider PACKAGE:build --task CONFIG.json --output results/run-001
```

配置文件的位置任意；迁移目录只需调整模块导入。合成入口仅存在于 `tests/smoke_provider.py`，用于验证公共代码，不提供数据集格式。

## 结果与计时

结果含每个工作单元的输出、质量判定、失败原因与插桩测量。失败/超时按 deadline 计入分位数。RunAborted 表示整个引擎崩溃，会使该分布全部失败。setup/observer 失败也会留下失败产物并清理。

单请求计时在质量检查前冻结；整轮墙钟仍包含校验、日志和调度开销。token 到达按 chunk 记录，不代表精确 GPU 逐 token 完成时刻。没有对应事件时指标为 null。

deadline 当前用于判定与统计，不是进程级强制终止。GPU 内存是设备采样而非精确进程峰值。工具等待、KV 恢复协议及 RecoveryGuard 是接入点，不意味着真实引擎恢复流程已经完成。

`scope.example.json` 仅为 vLLM 候选代码的路径检查示例，不是统一任务规格；具体任务的允许范围由出题时冻结。
