# 环境约定

公共代码仅需 Python 3.10+ 标准库，测试使用 pytest 8。GPU 引擎应在 Linux 的独立虚拟环境或容器中安装；Windows 本地 CPU 测试不证明推理引擎可用。

源码已经固定，但硬件尚未指定，因此不提供虚假的通用 CUDA/Torch 锁文件。LLM 完成真实验证后提交环境说明及 `pip freeze`（检查并去除私有 URL/凭据）、Python、驱动、CUDA、GPU 型号/UUID、引擎 commit、模型/tokenizer revision。

vLLM 和 SGLang 采用各自环境，不在同一环境强行混装。LMCache 与 vLLM 的组合必须依据固定版本安装说明验证；出现依赖不兼容时，应由任务负责人选定新的兼容提交并同时更新版本锁、submodule 和实验起点。

同步搬运微基准需要 CUDA 版 PyTorch。
