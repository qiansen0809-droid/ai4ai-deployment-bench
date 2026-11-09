# AI4AI 部署优化基准：公共起点、评测入口与插桩

本仓库当前实现的是 **LLM、VLM、VLA 可以共用的起点组件、评测入口和插桩层，以及传统基线的代码接入**。vLLM 是首个具体引擎接入，不限定公共组件只服务 LLM。

统一数据格式与转换、接口本身的研究性评测、智能体提示词和三类方法的对比统计由对应负责人完成。本仓库中的单元测试只验证所实现代码的行为，不代替他们的接口评测研究。真实模型/GPU 验收尚未完成。

## 目录未定，不影响先实现公共组件

以下是当前代码位置，不是要求团队采用的最终目录。接入点使用 Python 可导入的 `module:function`；以后移动目录只需调整包路径和配置，无需让每个方向重写调度、日志和结果输出。

```text
项目仓库/
├── evaluation/                  # 共用评测入口、执行契约、依赖调度、失败记录与结果汇总
├── instrumentation/             # 共用计时、事件日志、资源采样；引擎指标通过 observer 接入
├── adapters/
│   └── llm/                     # 首个具体接入示例：vLLM 客户端及 provider
├── tasks/
│   └── llm/                     # 暂存 vLLM 示例配置；不是团队统一数据标准
├── baselines/                   # 传统基线启动器、LRU 参考、同步搬运微基准
│   └── configs/                 # 官方基线的启动配置
├── engine_refs/
│   └── upstream/               # 固定提交的 vLLM / SGLang / LMCache 官方源码
├── environments/                # 环境说明，待硬件确定后锁定实测依赖
├── tests/                       # 本项目实现的单元测试与本地 HTTP 集成测试
└── .github/workflows/            # 自动测试
```

不创建其他负责人的数据转换器或 VLM/VLA 专用实现，也不要求他们采用本示例 JSONL 格式。原 `tasks/schema.py` 已移除，公共评测器不依赖 dataset、split、媒体字段或 token 格式。

## 公共起点的实际接入方式

每个方向提供一个受信任的 provider 函数，返回 `evaluation.contracts.Task`：

- `items`：该方向的数据加载器产生内部 `WorkItem`；只有请求 ID、计划到达、截止时间和依赖是调度信息。`payload` 和 `reference` 原样透传，不规定格式或做转换。
- `execute(item, emit)`：调用该方向适配器，返回可保存的输出。可以是文本、动作或其他 JSON 可表达结果；公共层不解释其语义。
- `judge(item, output)`：由可信评测方提供的质量判定，返回 `Verdict`。不能交给被优化的候选代码自报成绩。
- `setup/teardown`：准备、检查服务、重置、预热与清理。
- `observers`：引擎专属指标或公共资源采样；提供 `start(output_dir)` 和 `finish(output_dir)`。

这是一组程序调用契约，不是统一数据文件格式。数据负责人之后只需将自己的加载器接到 provider，公共评测器无需修改。VLA 闭环环境由其负责人在 execute 中推进；同一 episode 的控制步可通过 dependencies 排序，公共层不虚构机器人环境或把动作当 token。

最小接入示意：

```python
from evaluation.contracts import Task, WorkItem, Verdict

def build(config, config_dir):
    records = your_existing_loader(config, config_dir)
    items = [
        WorkItem(record.id, payload=record,
                 arrival_ms=record.arrival_ms,
                 deadline_ms=record.deadline_ms)
        for record in records
    ]

    def execute(item, emit):
        return your_adapter.run(item.payload, emit)

    def judge(item, output):
        return Verdict(your_quality_check(item.payload, output))

    return Task(items, execute, judge, concurrency=config["concurrency"])
```

其中 your_* 是由对应负责人提供的实现；不是可直接运行的假模型代码。

```bash
python -m evaluation.run --provider your_package.integration:build --task path/to/config.json --output results/run-001
```

命令行不假定任务配置位于 tasks，也不假定输入数据是 JSONL。配置 JSON 只负责选择接入函数及其参数，数据内容由 provider 读取。provider、judge、插桩均属于可信评测代码，应与候选引擎隔离。

## 已实现的公共行为与边界

- 按计划到达时间回放；检查重复 ID、缺失/循环依赖；依赖完成后才提交下一工作单元；失败依赖不继续提交。
- 请求内容不限定为 LLM。公共结果保存输出、质量判定、客户端时刻和失败原因；一次 work item 可以是请求或控制步。
- 独立计时记录 TTFT、动作就绪、端到端时延、实际派发偏差。token 事件必须与返回 token 序列对应；没有 token 时指标保持 null。
- 失败与超时不删除，按 deadline 进入时延分位数；显式 `RunAborted` 表示引擎整体崩溃，使该分布全部失败。
- 质量判定不计入单请求推理计时，但当前 Python 调度及整轮墙钟仍包含校验与日志开销，不是零开销生产级压测器。
- setup、observer 启动或请求失败时会保存失败结果并清理；普通请求错误与引擎整体崩溃由适配器区分。
- `GPUObserver` 可供任意引擎接入；vLLM 的 `/metrics` 是首个具体 observer。采样缺失不填零，设备显存采样不能当精确进程峰值；CPU 峰值尚未实现。
- `RecoveryGuard` 与 resumable 协议提供恢复校验接入点，但真实工具暂停、KV 下沉、取回和恢复尚未完整接通，不宣称支持了文档中的完整工具场景。
- deadline 是质量/时延判定，当前线程执行器不强制杀掉挂死的引擎；正式实验须配独立进程和资源限制。
- 原计划的 1 万请求重放精度、跨框架复现、额外开销阈值仍由接口评测负责人验证；本项目单元测试不证明这些研究指标达标。

## 第一个 vLLM 接入示例

`adapters/llm/provider.py` 包含一个临时示例读取函数，仅为了演示现有 vLLM 客户端如何接入公共入口；不承担统一格式/转换任务。最终加载器接入后可替换这个 provider。

```bash
python -m pip install -e ".[test]"
python -m pytest -q
python -m evaluation.run --task tasks/llm/mock.json --output results/demo
```

模拟产物标记 `simulated: true`，不能作为性能实验结果。输出目录必须全新。公共契约已测试不透明输入、动作输出、依赖顺序、deadline、崩溃和清理路径；不代表真实 VLM/VLA 已运行。

真实 vLLM 接入先填写 `tasks/llm/template.json` 的模型、模型 revision、引擎 commit、候选 commit、硬件和请求文件：

```bash
python -m baselines.launch baselines/configs/prefix_exact.json --model MODEL --revision REVISION --execute
python -m evaluation.run --task tasks/llm/local_task.json --output results/real-001
```

严格 token 判定只是该 provider 的策略，公共入口不固定质量规则。FP8 需另提供质量阈值与评分回调。当前示例仅支持文本 completion；启动服务不等于已经完成模型验证。

## 文档中的传统基线，究竟完成到哪一步

| 基线 | 仓库已有内容 | 尚缺内容 |
|---|---|---|
| 精确前缀缓存 / LRU | vLLM、SGLang 官方源码与启动配置；独立 LRU 参考 | 固定模型上的运行验证 |
| 分页 / 固定块大小 | vLLM 官方实现与配置 | 真实内存/碎片测量 |
| 固定设备 / 静态权重卸载 | vLLM 官方实现与配置 | 硬件及模型验证；不能当作 CPU 注意力执行 |
| FCFS / 重算抢占 | vLLM 调度器源码与配置 | 验证负载下实际触发与结果 |
| FP8 KV | vLLM 官方实现与配置 | GPU 支持、独立质量判定 |
| 多级缓存 | vLLM OffloadingConnector、LMCache、HiCache 官方源码；两层/三层启动配置 | 三层缓存的公共适配、真实端到端运行与兼容性验收 |
| 同步搬运、不重叠 | PyTorch H2D/D2H 同步搬运微基准代码、往返校验 | 接入真实模型/引擎执行路径，CUDA 实测 |

**因此，基线方法的上游源码已经有了，但不能说七类基线都已实现并接通。** `baselines/configs` 是配置，不冒充方法实现；方法实现位于 `engine_refs/upstream`，需 `git submodule update --init --recursive` 获取。详见 [来源表](engine_refs/BASELINES.md)、[版本锁](engine_refs/versions.json)。

vLLM 官方起点固定为 v0.32.0 / `5df63a7203cdb9328d824a27b682e77c7b9928be`。本机 `codex/deployment-start` 是该提交的起点分支，没有修改推理代码。三种优化方法应从相同冻结起点分叉；共享评测和插桩不可被候选修改。路径检查示例在 `evaluation/check_scope.py`，不是沙箱或语义证明。
