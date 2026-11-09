# 起点源码与来源

以下官方实现作为 AI 的优化输入，以 [versions.json](versions.json) 和 submodule 提交固定版本。源码本身可以作为起点，不要求先由我们做完优化。

| 方法来源 | 仓库中的实现入口 | 启动配置 |
|---|---|---|
| vLLM 精确缓存、分页与调度 | `upstream/vllm/vllm/v1/core/` | prefix_exact / paged_fixed / fcfs_recompute |
| vLLM KV 多级存储 | `upstream/vllm/vllm/v1/kv_offload/` 与 offloading connector | kv_cpu_offload / kv_three_tier |
| vLLM 静态权重卸载 | `upstream/vllm/vllm/model_executor/offloader/` | static_device / static_weight_offload |
| vLLM FP8 KV | `upstream/vllm/vllm/model_executor/layers/quantization/kv_cache.py` | fp8_kv |
| SGLang 精确前缀缓存、LRU、HiCache | `upstream/sglang/python/sglang/srt/mem_cache/` | sglang_lru / sglang_hicache |
| LMCache CPU/磁盘缓存 | `upstream/lmcache/lmcache/inprocess/v1/storage_backend/` | lmcache_three_tier |
| 同步搬运参考起点 | `../baselines/sync_transfer.py` | Python 模块独立运行 |
| LRU 策略参考起点 | `../baselines/lru.py` | Python 类直接调用 |

官方来源：[vLLM v0.32.0](https://github.com/vllm-project/vllm/tree/v0.32.0)、[SGLang v0.5.23](https://github.com/sgl-project/sglang/tree/v0.5.23)、[LMCache v0.5.7](https://github.com/LMCache/LMCache/tree/v0.5.7)。上游保留原许可证。

HiCache 当前配置使用 GPU/CPU 层级；三层配置由 vLLM/LMCache 提供。各项目的固定版本不等于其组合兼容性已验证。同步搬运程序是独立优化起点，其测量范围是搬运，不是模型服务。真实环境运行情况与性能由实验记录，不影响当前提供基础代码。
