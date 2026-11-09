# AI4AI 部署评测：LLM 起点、评测与插桩

本仓库当前只负责四件事：**vLLM 起点分支、LLM 评测入口、插桩层、传统基线代码接入**。数据集转换、VLM/VLA 接入、智能体提示词和跨方法统计由其他同学负责，不在本次交付中。

当前已完成 CPU 可验证实现与官方源码接入，**尚未做真实 GPU/模型验收**。模型与硬件按约定留空，正式任务缺配置就报错；mock 结果不能作为性能结果。

## 文件结构

```text
项目仓库/
├── tasks/                       # 任务规格与评测所需的最小请求格式
│   ├── llm/                     # LLM 模型、负载、约束、允许修改范围及模拟请求示例
│   ├── vlm/                     # 预留：VLM 任务规格，由 VLM 负责人接入
│   └── vla/                     # 预留：VLA 任务规格，由 VLA 负责人接入
├── adapters/                    # 将各推理框架接到统一评测接口
│   ├── llm/                     # 已实现：vLLM 流式 completion 客户端
│   ├── vlm/                     # 预留：视觉语言模型运行框架适配
│   └── vla/                     # 预留：动作模型与环境适配
├── baselines/                   # 传统基线启动器、LRU 参考策略、同步搬运微基准
│   └── configs/                 # 11 个基线配置：前缀缓存、分页、卸载、调度、FP8 等
├── evaluation/                  # 评测入口、请求回放、token 校验、结果汇总及修改范围检查
├── instrumentation/             # 公共事件日志、GPU 采样、vLLM 内部指标采集、恢复校验参考
├── environments/                # 环境安装与版本冻结说明；各方向依赖应独立管理
├── engine_refs/                 # 上游版本锁、基线来源及实现对应说明
│   └── upstream/                # 通过 Git submodule 引用固定版本官方源码
│       ├── vllm/                # vLLM 起点代码及其原生缓存、调度、卸载实现
│       ├── sglang/              # SGLang 精确前缀缓存、LRU、HiCache 基线源码
│       └── lmcache/             # LMCache 多级 KV 缓存基线源码
├── tests/                       # 本地 CPU 契约测试、故障检测及 HTTP 集成测试
└── .github/
    └── workflows/               # GitHub Actions 自动运行测试与模拟回放
```

标为“预留”的 VLM/VLA 目录表示协作规划，当前代码分支未提交这些目录或实现；本次只实现 LLM 起点、评测、插桩与基线接入。模型、硬件和真实负载仍需填写。

**审查入口：** [main 完整目录与代码](https://github.com/qiansen0809-droid/ai4ai-deployment-bench/tree/main) · [PR #1 代码差异](https://github.com/qiansen0809-droid/ai4ai-deployment-bench/pull/1/files)。完整实现已合并到 `main`，可直接在仓库主页查看。

## 本地验证

```bash
git clone --recurse-submodules https://github.com/qiansen0809-droid/ai4ai-deployment-bench.git
cd ai4ai-deployment-bench
python -m pip install -e ".[test]"
python -m pytest -q
python -m evaluation.run --task tasks/llm/mock.json --output results/demo
```

输出目录必须全新；产物为 `result.json` 和 `events.jsonl`，mock 明确标注 `simulated: true`。Windows 长路径检出可使用 `git -c core.longpaths=true submodule update --init --recursive`。

## vLLM 起点分支

固定起点为 `v0.32.0 / 5df63a7203cdb9328d824a27b682e77c7b9928be`。本机已建立 `codex/deployment-start` 分支，与该官方提交一致。共享仓库以 submodule 锁住起点；克隆时 submodule 默认处于 detached HEAD，可以执行：

```bash
git -C engine_refs/upstream/vllm switch -c codex/deployment-start
```

这不是已经发布到官方 vLLM 的远程分支。本次没有擅自创建新的 GitHub fork。若三组修改引擎，应各自从同一提交创建候选分支，记录候选 commit；不要改冻结起点和只读评测器。路径边界见 `tasks/llm/scope.json`，出题时进一步收紧。

```bash
python -m evaluation.check_scope --repo engine_refs/upstream/vllm --base 5df63a7203cdb9328d824a27b682e77c7b9928be --head HEAD --policy tasks/llm/scope.json
```

路径检查是提交差异检查，不是沙箱或语义证明。

## 运行真实评测

1. 在独立 Linux GPU 环境安装固定 vLLM；填写 `tasks/llm/template.json` 的模型、模型 revision、引擎 commit、候选 commit、硬件 ID、服务地址与请求文件。保存为本地任务文件，不上传私有路径。
2. 请求使用已冻结模板的最终 `input.text`、生成参数以及独立基准产生的 `reference.token_ids`。公共客户端不隐式套聊天模板。每条记录有数据来源、split、session、计划到达时间、相对该时间的 deadline；格式见 `mock_requests.jsonl`。这只是评测输入格式，不负责数据集转换。
3. 选择基线，先预览再启动：

```bash
python -m baselines.launch baselines/configs/prefix_exact.json --model MODEL --revision REVISION
python -m baselines.launch baselines/configs/prefix_exact.json --model MODEL --revision REVISION --execute
```

4. 在另一个终端运行：

```bash
python -m evaluation.run --task tasks/llm/local_task.json --output results/run-001
```

启动器管理服务进程，评测器连接已启动的服务，并在计时前执行配置中的预热请求。它不自动下载模型，不自动管理服务启停或强制终止 GPU 作业。需要模型、数据与硬件负责人先冻结环境、冷/热缓存条件、预热协议。

## 测量与结果

- 外部：计划到达、实际发送、流式 token chunk 收到、完成/失败事件；TTFT、端到端 P50/P99、客户端调度偏差、正确且按时完成的请求/token 吞吐。
- 正确性：严格比较实际生成 token IDs；参考缺失、流截断、输出错、超时均不算成功。失败保留并按 deadline 计分，不删除困难请求。
- 内部：保存 vLLM `/metrics` 前后原文，提取前缀查询/命中、抢占、生成 token 和 offload 字节/时间计数器增量。标签不合并，重置/新增序列标为不可求差；服务须独占，指标更新可能滞后。不能当成逐请求精确计数。
- 资源：nvidia-smi 设备级显存采样，不是精确进程峰值，可能包含其他进程；CPU 峰值尚未实现，保留 null。
- 恢复：`RecoveryGuard` 提供字节校验与工具结果顺序校验参考；没有接入真实 KV 迁移/恢复流程，普通 HTTP completion 不支持工具暂停/恢复。

SSE 一次可能到达多个 token，因此记录 chunk 间隔，不伪称逐 token 精确时间。Python 事件时间也不等于 CUDA 异步完成时间。FP8 是单独 quality 赛道，严格评测入口拒绝它；原生质量评分需任务负责人提供。

## 基线代码

[来源表](engine_refs/BASELINES.md) 对应实施计划七类任务；[版本锁](engine_refs/versions.json) 固定官方源码。配置共用启动逻辑，不复制整套引擎。同步搬运运行：

```bash
python -m baselines.sync_transfer --mib 64 --repeats 10
```

该微基准要求 CUDA PyTorch，包含 H2D/D2H 字节一致性检查、同步且不重叠，不能当成模型 serving 的性能结果。LRU 独立策略参考同样不代替完整引擎 KV 管理。

## 验收边界

本地已验证接口与故障路径；真实模型尚未跑。下列仍需实际 GPU 环境：起点可运行性、三引擎版本组合、FP8 质量、至少 3 次稳定性、1 万请求调度精度、插桩时延/内存开销、服务端资源隔离。不能声称已满足 P99 调度偏差 ≤1ms 或插桩时延 ≤2%。

上游保留各自许可证。本仓库不上传权重、保密测试数据或账号凭据。
