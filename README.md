# AI4AI：基线代码与公共起点

当前代码集中在 **`baselines/` 和 `starter/`**，其他目录仅占位。

## 目录

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


## 传统基线

**七类都有对应代码入口，但“三层统一接入”还只是组件与配置** 

| 任务 | 传统基线 | 位置 | 当前提供内容 |
|---|---|---|---|
| KV 缓存管理 | 精确前缀缓存、LRU | `baselines/upstream/vllm`、`sglang`、`baselines/lru.py` | 官方实现、配置、独立 LRU 参考 |
| 多级缓存 | vLLM 卸载连接器、LMCache、HiCache | `baselines/upstream/` 下三个项目 | 官方实现及启动配置；**三层统一接入尚无独立完成实现** |
| 分页与内存块 | 常规分页、固定块大小 | `baselines/upstream/vllm` | 官方实现及固定块配置 |
| CPU/GPU 数据搬运 | 同步拷贝、不重叠 | `baselines/sync_transfer.py` | 已有独立基础程序，可作为搬运优化起点 |
| 计算切换与权重卸载 | 固定设备、静态权重卸载 | `baselines/upstream/vllm` | 官方实现及启动配置 |
| 请求调度 | FCFS、重算式抢占 | `baselines/upstream/vllm` | 官方调度器及启动配置 |
| 压缩与近似复用 | FP8 KV | `baselines/upstream/vllm` | 官方实现及 FP8 配置 |


多个基线共用 vLLM 中不同模块，因此官方源码只保存一份。点击 GitHub 的子模块目录会跳到官方固定版本；不是丢失源码。[具体代码入口](baselines/README.md) · [来源](baselines/SOURCES.md)。

## 获取代码与运行

```bash
git clone --recurse-submodules https://github.com/qiansen0809-droid/ai4ai-deployment-bench.git
cd ai4ai-deployment-bench
python -m pip install -e ".[test]"
python -m pytest -q
python -m starter.evaluation.run --task starter/tests/fixtures/smoke.json --output results/smoke
```
