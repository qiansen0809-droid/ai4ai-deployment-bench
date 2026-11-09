# 基线代码来源与当前验收状态

版本以 [versions.json](versions.json) 和 Git submodule 的实际提交为准。官方代码已纳入仓库引用；没有真实模型/GPU验收，不能将来源接入或配置构造测试称为基线跑通。

| 文档基线 | 官方实现位置 | 本仓库接入 | 当前状态 |
|---|---|---|---|
| 精确前缀缓存、LRU | vLLM KV cache manager；SGLang radix cache | prefix_exact / sglang_lru 配置；LRU 独立参考 | 源码+配置；真实引擎未验证 |
| 分页、固定块 | vLLM block_pool / KV cache manager | paged_fixed | 源码+配置；未测碎片与峰值 |
| 固定设备、静态权重卸载 | vLLM UVA offload | static_device / static_weight_offload | 源码+配置；不等于 CPU 注意力执行 |
| FCFS、重算抢占 | vLLM v1/core/sched/scheduler.py | fcfs_recompute | 源码+配置；未验证抢占负载 |
| FP8 KV | vLLM KV quantization | fp8_kv | 源码+配置；质量赛道未接评分 |
| 多级缓存 | vLLM OffloadingConnector、LMCache、SGLang HiCache | kv_cpu_offload / kv_three_tier / lmcache_three_tier / sglang_hicache | 源码+启动配置；三层统一适配与端到端验证未完成 |
| 同步拷贝、不重叠 | 本仓库 PyTorch copy_ 与 cuda.synchronize | baselines/sync_transfer.py | 独立微基准；未接真实引擎执行路径，未做 CUDA 实测 |

上游来源：

- [vLLM v0.32.0](https://github.com/vllm-project/vllm/tree/v0.32.0)：`vllm/v1/core/`、`vllm/distributed/kv_transfer/`、`docs/features/kv_offloading_usage.md`。
- [SGLang v0.5.23](https://github.com/sgl-project/sglang/tree/v0.5.23)：`python/sglang/srt/mem_cache/`、`python/sglang/srt/arg_groups/fields/memory.py`。
- [LMCache v0.5.7](https://github.com/LMCache/LMCache/tree/v0.5.7)：`lmcache/inprocess/v1/`、`examples/inprocess/`。

HiCache 当前配置只有 GPU/CPU 层级，没有指定磁盘 backend；不要把该配置称作三层缓存。三个项目分别固定版本，不意味着它们可以直接组合使用。上游保留原许可证。

`baselines/lru.py` 是独立策略参考，不替代引擎块引用计数与并发管理。同步搬运微基准的结果也不能代替模型 serving 指标。
