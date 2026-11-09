"""python -m evaluation.run --task tasks/llm/mock.json --output results/demo"""
import argparse
import json
import platform
import subprocess
import uuid
from pathlib import Path
from adapters.mock import MockAdapter
from adapters.llm.vllm_http import VLLMAdapter
from evaluation.runner import replay
from instrumentation.events import EventLog
from instrumentation.resources import GPUSampler
from instrumentation.engine_metrics import snapshot, delta
from tasks.schema import fingerprint, load_requests, verify_media


def validate_config(cfg):
    if cfg.get("adapter") not in ("mock", "vllm_http"):
        raise ValueError("supported runners: mock, vllm_http; VLM/VLA require explicit implementation")
    if cfg.get("track") != "strict_tokens":
        raise ValueError("quality/compression tracks require a task-specific quality evaluator")
    if cfg.get("adapter") != "mock":
        for field in ("model", "model_revision", "engine_revision", "hardware_id", "endpoint", "candidate_revision"):
            if not cfg.get(field):
                raise ValueError(f"fill task.{field} before a real run")
    if type(cfg.get("concurrency")) is not int or cfg["concurrency"] < 1:
        raise ValueError("positive concurrency required")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--task", required=True); p.add_argument("--output", required=True)
    a = p.parse_args()
    config_path = Path(a.task).resolve()
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    validate_config(cfg)
    rows = load_requests(config_path.parent / cfg["requests"])
    if any(r["split"] != cfg["split"] for r in rows):
        raise ValueError("workload split differs from task split")
    verify_media(rows, config_path.parent / cfg.get("data_root", "."))
    output = Path(a.output)
    output.mkdir(parents=True, exist_ok=False)
    run_id = str(uuid.uuid4())
    log = EventLog(output / "events.jsonl", run_id)
    sampler = GPUSampler()
    adapter = MockAdapter() if cfg["adapter"] == "mock" else VLLMAdapter(cfg["endpoint"], cfg["model"], cfg.get("timeout_s", 30))
    # Explicit readiness and warmup are outside measured replay.
    try:
        for row in rows[:cfg.get("warmup_requests", 0)]:
            adapter.run(row, lambda *args, **kwargs: None)
        before = snapshot(cfg["endpoint"], output / "metrics-before.prom") if cfg["adapter"] != "mock" else None
        sampler.start()
        result = replay(rows, adapter, log, cfg["concurrency"])
        after = snapshot(cfg["endpoint"], output / "metrics-after.prom") if before is not None else None
    finally:
        resources = sampler.finish()
        log.close()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or None
    result.update(schema_version=1, run_id=run_id, simulated=cfg["adapter"] == "mock",
                  task=cfg, task_sha256=fingerprint(cfg), workload_sha256=fingerprint(rows),
                  harness_revision=commit, platform=platform.platform(), resources=resources,
                  engine_metrics=delta(before, after) if before is not None else None,
                  validation_level="mock_contract" if cfg["adapter"] == "mock" else "client_measurement_only")
    (output / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
