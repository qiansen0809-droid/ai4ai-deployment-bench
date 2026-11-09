# 基线是 AI 的优化输入

这里保留基础实现，不提前替 AI 完成优化。官方代码放在 `../engine_refs/upstream/`，简单参考代码在本目录；`configs/` 用来选择起点配置。

## 方法代码入口

以下路径相对仓库根目录：

| 任务 | 现有起点代码 | 交给 AI 修改的对象 |
|---|---|---|
| KV 管理 | `engine_refs/upstream/vllm/vllm/v1/core/kv_cache_manager.py`；SGLang `python/sglang/srt/mem_cache/`；`baselines/lru.py` | 分配、回收、保留与驱逐策略 |
| 多级缓存 | vLLM `vllm/distributed/kv_transfer/kv_connector/v1/offloading/`、`vllm/v1/kv_offload/`；LMCache `lmcache/inprocess/v1/storage_backend/`；SGLang HiCache | 层级选择、保留、搬运、预取等实现 |
| 分页与块管理 | vLLM `vllm/v1/core/block_pool.py` | 块管理与任务允许的分配策略 |
| 同步搬运、不重叠 | `baselines/sync_transfer.py` | 基础 H2D/D2H 搬运路径；可研究合批、固定内存、异步与重叠 |
| 固定设备 / 静态权重卸载 | vLLM `vllm/model_executor/offloader/uva.py` | 权重加载、卸载与调度策略 |
| FCFS / 重算抢占 | vLLM `vllm/v1/core/sched/scheduler.py` | 排队、批处理、抢占和恢复 |
| FP8 KV | vLLM `vllm/model_executor/layers/quantization/kv_cache.py` | 任务允许的 KV 压缩策略；独立质量赛道 |

可修改范围最终按具体优化任务冻结；表中列出代码位置，不授予更改模型权重、质量参考、评测器或插桩的权限。

## 启动

```bash
# 先打印启动命令；加 --execute 才启动服务
python -m baselines.launch baselines/configs/prefix_exact.json --model MODEL --revision REVISION

# 同步搬运起点，需要 CUDA PyTorch
python -m baselines.sync_transfer --mib 64 --repeats 10
```

11 个配置覆盖精确缓存、固定分页、CPU KV 卸载、三层缓存、LMCache、HiCache、静态执行、静态权重卸载、FCFS 和 FP8。配置调用官方实现，不是独立算法实现。

三层缓存从现有 offloading/backend 代码和配置开始，不以我们先实现完整统一优化系统为前提。要把某项功能设为性能优化题，应先在该题选定环境跑通基础功能；如果任务要求 AI 补齐功能，则应明确记录为功能实现任务。

## 公共评测保持固定

AI 修改候选代码后，由同一公共评测入口比较起点与候选。同步搬运的往返校验、公共质量判定与插桩属于验证逻辑，应由评测方保留可信副本，不能采信候选自行报告的结果或让候选删除校验。

目前交付的是方法源码、基础程序和启动配置。实际兼容性、质量和性能由后续实验记录，不预先声称提升。
