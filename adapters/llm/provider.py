"""Optional vLLM wiring/example JSONL reader; not the shared data standard.

The common evaluator never imports this module. Replace this provider when the
data owner supplies the finalized loader; no evaluator change is necessary.
"""
import json
from adapters.llm.vllm_http import VLLMAdapter
from adapters.mock import MockAdapter
from evaluation.contracts import Task, WorkItem, Verdict
from instrumentation.engine_metrics import snapshot, delta
from instrumentation.resources import GPUObserver


class VLLMMetrics:
    def __init__(self, endpoint):
        self.endpoint = endpoint

    def start(self, output_dir):
        self.before = snapshot(self.endpoint, output_dir / "metrics-before.prom")

    def finish(self, output_dir):
        return delta(self.before, snapshot(self.endpoint, output_dir / "metrics-after.prom"))


def strict_tokens(item, output):
    return Verdict(output.token_ids == item.reference, "quality_mismatch" if output.token_ids != item.reference else None)


def build(config, config_dir):
    mock = config.get("adapter") == "mock"
    if config.get("adapter") not in ("mock", "vllm_http") or config.get("track") != "strict_tokens":
        raise ValueError("this example provider supports mock/vllm_http strict_tokens only")
    if not mock:
        for key in ("model", "model_revision", "engine_revision", "candidate_revision", "hardware_id", "endpoint"):
            if not config.get(key):
                raise ValueError(f"fill {key} before real inference")
    rows = [json.loads(s) for s in (config_dir / config["requests"]).read_text(encoding="utf-8").splitlines() if s.strip()]
    for r in rows:
        if r.get("split") != config["split"]:
            raise ValueError("example request split differs from configuration")
        ids = r.get("reference", {}).get("token_ids")
        if not isinstance(ids, list) or any(type(t) is not int or t < 0 for t in ids):
            raise ValueError("example requires frozen reference token_ids")
    adapter = MockAdapter() if mock else VLLMAdapter(config["endpoint"], config["model"], config.get("timeout_s", 30))
    items = [WorkItem(r["request_id"], r, r["reference"]["token_ids"], r["arrival_ms"], r["deadline_ms"], tuple(r.get("dependencies", []))) for r in rows]

    def execute(item, emit):
        return adapter.run(item.payload, emit)

    def setup():
        warmup = config.get("warmup_requests", 0)
        if type(warmup) is not int or warmup < 0:
            raise ValueError("warmup_requests must be a nonnegative integer")
        for item in items[:warmup]:
            execute(item, lambda *a, **kw: None)

    observers = (GPUObserver(),) if mock else (GPUObserver(), VLLMMetrics(config["endpoint"]))
    return Task(items, execute, strict_tokens, config["concurrency"],
                metadata={"provider": "vllm_example", "model_revision": config.get("model_revision"),
                          "engine_revision": config.get("engine_revision"), "hardware_id": config.get("hardware_id"),
                          "candidate_revision": config.get("candidate_revision")},
                setup=setup, observers=observers, simulated=mock)
