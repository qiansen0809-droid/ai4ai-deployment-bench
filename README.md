# AI4AI：基线代码与公共起点

项目目的是把基础代码交给 AI 优化，再用固定的公共评测和插桩检查结果。当前代码集中在 **`baselines/` 和 `starter/`**，其他协作目录仅占位，不实现其他负责人的工作。

## 哪些目录有内容，哪些是空的

```text
项目仓库/
├── baselines/                   # 【有内容】所有传统基线集中在这里
│   ├── upstream/                # 【有内容】固定版本的官方方法源码（Git 子模块）
│   │   ├── vllm/                # 缓存、分页、卸载、调度、FP8 KV
│   │   ├── sglang/              # 前缀缓存、LRU、HiCache
│   │   └── lmcache/             # 多级 KV 缓存
│   ├── configs/                 # 【有内容】11 个基线启动配置
│   ├── lru.py                   # 简单 LRU 策略参考
│   ├── sync_transfer.py         # 同步、不重叠的 CPU/GPU 搬运基础程序
│   ├── launch.py                # 共用启动器
│   ├── versions.json            # 官方源码版本锁
│   └── SOURCES.md               # 方法来源及对应关系
├── starter/                     # 【有内容】我们的公共起点代码
│   ├── adapters/llm/            # 首个具体引擎接入：vLLM
│   ├── evaluation/              # 公共评测入口、依赖调度、校验、结果汇总
│   ├── instrumentation/         # 公共计时、日志、资源与引擎指标采集
│   └── tests/                   # 起点及基线的代码测试；合成夹具只在这里
├── tasks/                       # 【空位】未实现任务配置或数据转换
│   ├── llm/                     # 空位
│   ├── vlm/                     # 空位
│   └── vla/                     # 空位
├── adapters/                    # 【空位】留给后续统一目录安排
│   ├── llm/                     # 空位；已有 vLLM 接入在 starter/adapters/llm
│   ├── vlm/                     # 空位
│   └── vla/                     # 空位
├── evaluation/                  # 【空位】已有公共实现集中在 starter/evaluation
├── instrumentation/             # 【空位】已有公共实现集中在 starter/instrumentation
├── environments/                # 【空位】当前代码环境说明在 starter/ENVIRONMENT.md
├── engine_refs/                 # 【空位】现有基线来源及版本已移至 baselines
└── .github/workflows/            # 【测试配置】自动测试，不是其他方向的业务实现
```

Git 不保存真正的空目录，因此“空位”目录仅含 `.gitkeep`，没有实现代码。根目录的 `pyproject.toml`、`.gitignore`、`.gitmodules` 是安装与版本管理文件。目录以后可以调整，这次不规定团队最终布局。

## 表里的传统基线是否覆盖

**七类都有对应代码入口，但“三层统一接入”还只是组件与配置，不能说表内所有条目都已独立实现。** 下表区分基础代码与接入状态；不要求我们先替 AI 完成优化。

| 任务 | 传统基线 | 放在哪里 | 当前提供内容 |
|---|---|---|---|
| KV 缓存管理 | 精确前缀缓存、LRU | `baselines/upstream/vllm`、`sglang`、`baselines/lru.py` | 官方实现、配置、独立 LRU 参考 |
| 多级缓存 | vLLM 卸载连接器、LMCache、HiCache | `baselines/upstream/` 下三个项目 | 官方实现及启动配置；**三层统一接入尚无独立完成实现** |
| 分页与内存块 | 常规分页、固定块大小 | `baselines/upstream/vllm` | 官方实现及固定块配置 |
| CPU/GPU 数据搬运 | 同步拷贝、不重叠 | `baselines/sync_transfer.py` | 已有独立基础程序，可作为搬运优化起点 |
| 计算切换与权重卸载 | 固定设备、静态权重卸载 | `baselines/upstream/vllm` | 官方实现及启动配置 |
| 请求调度 | FCFS、重算式抢占 | `baselines/upstream/vllm` | 官方调度器及启动配置 |
| 压缩与近似复用 | FP8 KV | `baselines/upstream/vllm` | 官方实现及 FP8 配置 |

“允许的操作”是 AI 可以探索的修改空间，不要求起点先实现其中的全部优化。例如同步搬运就是普通起点，异步、合批、预取和重叠可以留给 AI 优化。

多个基线共用 vLLM 中不同模块，因此官方源码只保存一份。点击 GitHub 的子模块目录会跳到官方固定版本；不是丢失源码。[具体代码入口](baselines/README.md) · [来源](baselines/SOURCES.md)。

## 获取代码与运行

```bash
git clone --recurse-submodules https://github.com/qiansen0809-droid/ai4ai-deployment-bench.git
cd ai4ai-deployment-bench
python -m pip install -e ".[test]"
python -m pytest -q
python -m starter.evaluation.run --task starter/tests/fixtures/smoke.json --output results/smoke
```

已有旧版克隆在拉取目录迁移后，先执行 `git submodule sync --recursive`，再执行 `git submodule update --init --recursive`。

选定模型和环境后启动基线：

```bash
python -m baselines.launch baselines/configs/prefix_exact.json --model MODEL --revision REVISION --execute
python -m baselines.sync_transfer --mib 64 --repeats 10
```

公共评测接收已准备好的请求，不承担数据加载/转换：

```bash
python -m starter.evaluation.run --provider PACKAGE:build --task CONFIG.json --output results/run-001
```

[公共接入说明](starter/evaluation/README.md)。候选基线是优化对象，评测、质量判定与插桩保持固定。模拟运行只检验代码；同步搬运程序测的是搬运性能，真实 GPU/模型性能尚无实验结论。
