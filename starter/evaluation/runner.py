"""Engine-neutral scheduler. Payloads and quality logic belong to providers."""
import concurrent.futures as cf
import dataclasses
import json
import math
import time
from starter.evaluation.contracts import WorkItem, Verdict, RunAborted
from starter.instrumentation.probe import RequestProbe


def percentile(values, q):
    if not values:
        return None
    values = sorted(values)
    p = (len(values) - 1) * q
    low = int(p)
    return values[low] + (values[min(low + 1, len(values)-1)] - values[low]) * (p-low)


def validate_items(items, concurrency):
    if type(concurrency) is not int or concurrency < 1:
        raise ValueError("positive concurrency required")
    if not items or any(not isinstance(x, WorkItem) for x in items):
        raise ValueError("provider must supply nonempty WorkItems")
    ids = [x.request_id for x in items]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("request IDs must be nonempty and unique")
    known = set(ids)
    for item in items:
        for key, minimum in (("arrival_ms", 0), ("deadline_ms", .001)):
            value = getattr(item, key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
                raise ValueError(f"invalid {key}")
        if not isinstance(item.dependencies, (tuple, list)) or any(not isinstance(d, str) for d in item.dependencies):
            raise ValueError("dependencies must contain request IDs")
        if set(item.dependencies) - known or item.request_id in item.dependencies:
            raise ValueError("missing or self dependency")
    resolved = set()
    while len(resolved) < len(items):
        ready = {x.request_id for x in items if set(x.dependencies) <= resolved}
        if not ready - resolved:
            raise ValueError("cyclic dependencies")
        resolved |= ready


def replay(task, log):
    items = list(task.items)
    validate_items(items, task.concurrency)
    epoch = time.perf_counter()
    completed = {}
    aborted = None

    def failed(item, reason):
        log.emit(item.request_id, "request_finished", status="failed", error=reason)
        return {"request_id": item.request_id, "status": "failed", "error": reason,
                "output": None, "quality": None, "measurement": None,
                "deadline_ms": item.deadline_ms, "scored_latency_ms": item.deadline_ms}

    def work(item):
        probe = RequestProbe(log, item.request_id, epoch + item.arrival_ms/1000)
        output = None
        error = None
        fatal = False
        try:
            output = task.execute(item, probe.emit)
        except RunAborted as exc:
            error, fatal = "engine_crash: " + str(exc), True
        except TimeoutError as exc:
            error = "timeout: " + str(exc)
        except Exception as exc:
            error = type(exc).__name__ + ": " + str(exc)
        measurement = probe.finish()  # quality checks are outside inference timing
        quality = None
        encoded = None
        if error is None:
            try:
                encoded = dataclasses.asdict(output) if dataclasses.is_dataclass(output) else output
                json.dumps(encoded, allow_nan=False)
                # An adapter emitting tokens must agree with the returned token sequence.
                returned = encoded.get("token_ids") if isinstance(encoded, dict) else None
                if returned is not None and returned != measurement["observed_token_ids"]:
                    raise ValueError("token event/output mismatch")
                verdict = task.judge(item, output)
                if not isinstance(verdict, Verdict) or type(verdict.passed) is not bool:
                    raise TypeError("judge must return Verdict with boolean passed")
                json.dumps(verdict.metrics, allow_nan=False)
                quality = dataclasses.asdict(verdict)
                if not verdict.passed:
                    error = verdict.reason or "quality_mismatch"
            except Exception as exc:
                error = "validation_error: " + str(exc)
        if measurement["e2e_ms"] > item.deadline_ms:
            error = "timeout" + (": " + error if error else "")
        status = "ok" if error is None else "failed"
        log.emit(item.request_id, "request_finished", status=status, error=error)
        return {"request_id": item.request_id, "status": status, "error": error,
                "output": encoded, "quality": quality, "measurement": measurement,
                "deadline_ms": item.deadline_ms, "_fatal": fatal,
                "scored_latency_ms": measurement["e2e_ms"] if status == "ok" else item.deadline_ms}

    pending = sorted(items, key=lambda x: x.arrival_ms)
    active = {}
    with cf.ThreadPoolExecutor(max_workers=task.concurrency) as pool:
        while pending or active:
            for future in list(active):
                if future.done():
                    item = active.pop(future)
                    result = future.result()
                    if result.pop("_fatal"):
                        aborted = result["error"]
                    completed[item.request_id] = result
            for item in list(pending):
                target = epoch + item.arrival_ms/1000
                now = time.perf_counter()
                if aborted:
                    completed[item.request_id] = failed(item, aborted)
                elif any(d in completed and completed[d]["status"] != "ok" for d in item.dependencies):
                    completed[item.request_id] = failed(item, "dependency_failed")
                elif now >= target + item.deadline_ms/1000:
                    completed[item.request_id] = failed(item, "timeout_before_dispatch")
                elif now >= target and all(d in completed for d in item.dependencies) and len(active) < task.concurrency:
                    active[pool.submit(work, item)] = item
                else:
                    continue
                pending.remove(item)
            if active:
                cf.wait(active, timeout=.001, return_when=cf.FIRST_COMPLETED)
            elif pending:
                next_arrival = min(epoch + i.arrival_ms/1000 for i in pending)
                time.sleep(max(0, min(.01, next_arrival-time.perf_counter())))
    if aborted:
        # An engine-wide crash invalidates the distribution, including prior successes.
        for result in completed.values():
            result.update(status="failed", error=aborted, scored_latency_ms=result["deadline_ms"])
        log.emit(None, "distribution_invalidated", error=aborted)
    duration = time.perf_counter() - epoch
    results = [completed[x.request_id] for x in items]
    ok = [r for r in results if r["status"] == "ok"]
    measured = [r["measurement"] for r in results if r["measurement"]]
    successful_measurements = [r["measurement"] for r in ok if r["measurement"]]
    ttft = [m["ttft_ms"] for m in successful_measurements if m["ttft_ms"] is not None]
    actions = [m["action_ready_ms"] for m in successful_measurements if m["action_ready_ms"] is not None]
    latencies = [r["scored_latency_ms"] for r in results]
    return {"requests": results, "summary": {
        "total": len(results), "passed": len(ok), "failed": len(results)-len(ok),
        "all_passed": len(ok) == len(results), "distribution_error": aborted,
        "on_time_pass_rate": len(ok)/len(results), "wall_time_s": duration,
        "request_goodput_per_s": len(ok)/duration,
        "validated_token_goodput_per_s": sum(len(m["observed_token_ids"]) for m in successful_measurements)/duration if any(m["observed_token_ids"] for m in measured) else None,
        "ttft_p50_ms": percentile(ttft, .5), "ttft_p99_ms": percentile(ttft, .99),
        "action_ready_p50_ms": percentile(actions, .5), "action_ready_p99_ms": percentile(actions, .99),
        "latency_p50_ms": percentile(latencies, .5), "latency_p99_ms": percentile(latencies, .99),
        "dispatch_delay_p99_ms": percentile([m["dispatch_delay_ms"] for m in measured], .99),
    }}
