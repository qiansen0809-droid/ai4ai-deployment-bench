# 七类传统基线的来源与实现对应

以下以已下载的固定提交源码为依据，而不是仅凭最新网页描述。所有配置均已做本地构造测试，但没有真实 GPU 运行结果；三个版本独立固定不代表其组合已验证兼容。

| 实施计划任务 | 基线入口 | 官方方法/项目与源码位置 |
|---|---|---|
| KV 管理：精确前缀复用、LRU | `prefix_exact.json`, `sglang_lru.json` | [vLLM](https://github.com/vllm-project/vllm/tree/v0.32.0) 的 `vllm/v1/core/kv_cache_manager.py`；[SGLang](https://github.com/sgl-project/sglang/tree/v0.5.23) 的 radix cache 与 `python/sglang/srt/arg_groups/fields/memory.py` |
| 多级缓存 | `kv_cpu_offload.json`, `kv_three_tier.json`, `lmcache_three_tier.json`, `sglang_hicache.json` | vLLM `docs/features/kv_offloading_usage.md` 与 OffloadingConnector；[LMCache](https://github.com/LMCache/LMCache/tree/v0.5.7) 的 `lmcache/inprocess/v1/config.py` 与 `examples/inprocess/`；SGLang HiCache |
| 分页与固定块大小 | `paged_fixed.json` | vLLM PagedAttention，`vllm/engine/arg_utils.py` 的 block-size，`vllm/v1/core/block_pool.py` |
| 同步搬运、不重叠 | `python -m baselines.sync_transfer` | 本项目 PyTorch `copy_(non_blocking=False)` 与 `cuda.synchronize()` 参考微基准；双向字节相等校验；不是完整模型 serving baseline |
| 固定设备与静态权重卸载 | `static_device.json`, `static_weight_offload.json` | vLLM `--cpu-offload-gb` / UVA offload；这不是 CPU 注意力算子执行基线 |
| FCFS 与重算式抢占 | `fcfs_recompute.json` | vLLM `vllm/v1/core/sched/scheduler.py` 的调度和抢占路径；当前版本默认抢占行为，不伪造旧版 preemption CLI |
| FP8 KV | `fp8_kv.json` | vLLM `--kv-cache-dtype fp8`；质量独立赛道，需硬件支持与质量验证 |

`baselines/lru.py` 只提供按字节容量的独立策略参考，不能替代引擎中的块引用计数、前缀哈希和并发安全。HiCache 当前配置是 GPU/CPU 层级，未指定持久存储 backend；三层配置由 vLLM/LMCache 示例提供，不能把 HiCache 默认配置称为三层。

上游完整代码通过 git submodule 接入，不复制后移除许可证。版本 commit 见 `versions.json`；克隆后运行 `git submodule update --init --recursive` 获取。若修改引擎，请使用独立候选 fork 并记录候选 commit，保留冻结起点。
