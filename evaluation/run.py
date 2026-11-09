"""Shared entry: a trusted provider supplies loading, execution and judging."""
import argparse
import hashlib
import json
import platform
import subprocess
import uuid
from pathlib import Path
from evaluation.providers import build_task
from evaluation.runner import replay, validate_items
from instrumentation.events import EventLog


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode()).hexdigest()


def evaluate(task, output_dir, config=None):
    task.items = list(task.items)
    validate_items(task.items, task.concurrency)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    run_id = str(uuid.uuid4())
    log = EventLog(output_dir / "events.jsonl", run_id)
    observers = []
    resources = []
    result = None
    failure = None
    try:
        task.setup()
        for observer in task.observers:
            # Register before start so partially initialized observers are cleaned up.
            observers.append(observer)
            observer.start(output_dir)
        result = replay(task, log)
    except Exception as exc:
        failure = type(exc).__name__ + ": " + str(exc)
        log.emit(None, "run_failed", error=failure)
    finally:
        for observer in reversed(observers):
            try:
                resources.append({"observer": type(observer).__name__, "data": observer.finish(output_dir)})
            except Exception as exc:
                resources.append({"observer": type(observer).__name__, "error": str(exc)})
        try:
            task.teardown()
        except Exception as exc:
            failure = failure or "teardown_error: " + str(exc)
        log.close()
    if result is None:
        result = {"requests": [{"request_id": i.request_id, "status": "failed", "error": failure,
                                "scored_latency_ms": i.deadline_ms} for i in task.items],
                  "summary": {"total": len(task.items), "passed": 0, "failed": len(task.items),
                              "all_passed": False, "distribution_error": failure}}
    if failure:
        result["summary"].update(all_passed=False, run_error=failure)
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                                cwd=Path(__file__).resolve().parents[1], timeout=5).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        commit = None
    result.update(schema_version=2, run_id=run_id, simulated=task.simulated,
                  metadata=task.metadata, config_sha256=fingerprint(config or {}),
                  harness_revision=commit, platform=platform.platform(), resources=resources)
    (output_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True)
    parser.add_argument("--provider", help="trusted module:function; overrides config.provider")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    path = Path(args.task).resolve()
    config = json.loads(path.read_text(encoding="utf-8"))
    provider = args.provider or config.get("provider")
    if not provider:
        parser.error("supply --provider module:function or config.provider")
    task = build_task(provider, config, path.parent)
    result = evaluate(task, args.output, config)
    print(json.dumps(result["summary"], indent=2))
    raise SystemExit(0 if result["summary"]["all_passed"] else 1)


if __name__ == "__main__":
    main()
