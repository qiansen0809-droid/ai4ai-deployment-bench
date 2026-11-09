"""Wire already prepared WorkItems to vLLM; no data loading or conversion."""
from starter.adapters.llm.vllm_http import VLLMAdapter
from starter.evaluation.contracts import Task, Verdict
from starter.instrumentation.engine_metrics import snapshot, delta
from starter.instrumentation.resources import GPUObserver


class VLLMMetrics:
    def __init__(self, endpoint):
        self.endpoint = endpoint

    def start(self, output_dir):
        self.before = snapshot(self.endpoint, output_dir / "metrics-before.prom")

    def finish(self, output_dir):
        return delta(self.before, snapshot(self.endpoint, output_dir / "metrics-after.prom"))


def strict_tokens(item, output):
    passed = output.token_ids == item.reference
    return Verdict(passed, None if passed else "quality_mismatch")


def create_task(items, *, endpoint, model, concurrency=1, timeout_s=30,
                judge=strict_tokens, metadata=None):
    """Input preparation belongs to the caller; this function only wires execution."""
    if not endpoint or not model:
        raise ValueError("endpoint and model are required")
    adapter = VLLMAdapter(endpoint, model, timeout_s)

    def execute(item, emit):
        return adapter.run(item.payload, emit)

    return Task(items, execute, judge, concurrency=concurrency,
                metadata=dict(metadata or {}),
                observers=(GPUObserver(), VLLMMetrics(endpoint)))
