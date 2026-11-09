"""Synthetic evaluator fixture, not a benchmark dataset or data format."""
from evaluation.contracts import Task, WorkItem, Verdict


def build(config, config_dir):
    items = [WorkItem(str(i), i, i * 2) for i in range(3)]

    def execute(item, emit):
        emit("fixture_completed")
        return item.payload * 2

    return Task(items, execute, lambda item, output: Verdict(output == item.reference),
                concurrency=2, simulated=True)
