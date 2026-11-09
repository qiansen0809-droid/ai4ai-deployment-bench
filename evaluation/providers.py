"""Load a trusted provider by module:function, independent of repo layout."""
import importlib
from evaluation.contracts import Task


def build_task(target, config, config_dir):
    module, sep, name = target.partition(":")
    if not sep or not module or not name:
        raise ValueError("provider must be module:function")
    factory = getattr(importlib.import_module(module), name)
    task = factory(config, config_dir)
    if not isinstance(task, Task):
        raise TypeError("provider must return evaluation.contracts.Task")
    return task
