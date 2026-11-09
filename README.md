# AI4AI：待优化基线与公共评测组件

**把基础代码交给 AI，让 AI 在固定模型与质量要求下优化部署性能。**

本仓库只提供两部分：

1. **待优化的起点与基线代码**：官方引擎中的基础实现，以及简单的参考实现。AI 可以修改任务允许的缓存、分页、搬运、卸载和调度代码。
2. **公共评测入口与插桩**：运行候选、检查输出、记录时延和资源指标，判断改动是否有效。评测和插桩不属于 AI 可修改的优化对象。

不需要我们先把所有优化功能做完，才把代码交给 AI。模型、硬件和负载选定后，再运行起点与候选进行比较。当前没有真实 GPU 性能结论。

## 当前目录

目录可以随团队工程安排迁移，公共接口不绑定任务目录或数据文件格式。

```text
项目仓库/
├── baselines/                   # 交给 AI 优化的基础实现与启动入口
│   ├── configs/                 # 官方基线的启动配置
│   ├── lru.py                   # 简单 LRU 策略参考
│   └── sync_transfer.py         # 同步、不重叠的 CPU/GPU 搬运起点
├── engine_refs/                 # 上游版本锁与基线来源
│   └── upstream/               # 固定提交的官方方法源码
│       ├── vllm/                # 缓存、分页、调度、卸载、FP8 KV 等实现
│       ├── sglang/              # 前缀缓存、LRU、HiCache 等实现
│       └── lmcache/             # 多级 KV 缓存实现
├── evaluation/                  # 公共评测入口、依赖调度、校验与结果汇总
├── instrumentation/             # 公共事件日志、计时、资源与引擎指标采集
├── adapters/
│   └── llm/                     # vLLM 接入公共评测的实现，不含数据加载器
├── environments/                # 本项目与基线代码的环境说明
├── tests/                       # 本项目单元测试，fixtures 仅用于测试
└── .github/workflows/           # 自动测试
```

仓库不实现统一数据格式、数据转换、VLM/VLA 专用任务、智能体提示词或跨方法对比统计。

## 交给 AI 的代码在哪里

方法源码通过 submodule 固定版本，配置文件只是启动入口。克隆时同时取得源码：

```bash
git clone --recurse-submodules https://github.com/qiansen0809-droid/ai4ai-deployment-bench.git
cd ai4ai-deployment-bench
```

| 待优化基线 | 代码入口 |
|---|---|
| 精确前缀缓存 / LRU | vLLM KV cache manager、SGLang radix cache、`baselines/lru.py` |
| 多级缓存 | vLLM OffloadingConnector、LMCache CPU/磁盘 backend、SGLang HiCache |
| 分页 / 固定块大小 | vLLM `vllm/v1/core/block_pool.py` |
| 同步搬运 / 不重叠 | `baselines/sync_transfer.py` |
| 固定设备 / 静态权重卸载 | vLLM `vllm/model_executor/offloader/` |
| FCFS / 重算抢占 | vLLM `vllm/v1/core/sched/scheduler.py` |
| FP8 KV | vLLM KV 量化实现及 `baselines/configs/fp8_kv.json` |

[基线使用说明](baselines/README.md) 列出了具体文件、启动方法和优化对象；[版本与来源](engine_refs/BASELINES.md) 用于追溯原始实现。

## 最小工作流程

1. 选一个基线，保存原始提交和配置，作为共同起点。
2. 将允许修改的代码交给 AI；不要求事先实现预取、重叠等优化。
3. 起点和 AI 候选使用相同模型、负载、硬件及公共评测入口。
4. 检查正确性，再看速度与资源变化；保留失败结果。

例如，启动官方精确前缀缓存基线：

```bash
python -m baselines.launch baselines/configs/prefix_exact.json --model MODEL --revision REVISION --execute
```

同步搬运起点可独立运行：

```bash
python -m baselines.sync_transfer --mib 64 --repeats 10
```

它是搬运优化题的基础程序，含 H2D/D2H 往返校验；该结果表示搬运性能，不表示完整模型性能。

## 公共评测与插桩

公共入口通过受信任的 provider 接收已准备好的请求、候选执行函数和质量校验函数，不读取或转换数据集：

```bash
python -m evaluation.run --provider PACKAGE:build --task CONFIG.json --output results/run-001
```

[接入说明](evaluation/README.md) 给出调用接口。vLLM 是一个具体接入；公共入口本身不限定模型方向。当前支持到达时间与依赖调度、deadline 判定、输出校验、事件记录和结果保存；CPU 内存峰值、强制终止挂死引擎和真实工具迁移/恢复尚未接入。

代码测试：

```bash
python -m pip install -e ".[test]"
python -m pytest -q
python -m evaluation.run --task tests/fixtures/smoke.json --output results/smoke
```

smoke 是纯合成测试，不是数据规范或性能基准。引擎依赖及真实性能需要在选定环境运行；这与当前交付基础代码是两件事。
