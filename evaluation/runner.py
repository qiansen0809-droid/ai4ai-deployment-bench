import concurrent.futures
import math
import time


def percentile(values, q):
    if not values:
        return None
    s = sorted(values)
    position = (len(s) - 1) * q
    low = int(position)
    return s[low] + (s[min(low + 1, len(s) - 1)] - s[low]) * (position - low)


def replay(rows, adapter, log, concurrency=1):
    if type(concurrency) is not int or concurrency < 1:
        raise ValueError("concurrency must be positive integer")
    if any(r["modality"] != "llm" for r in rows):
        raise ValueError("this runner is LLM-only; VLM/VLA need their owner-supplied evaluator")
    if any("token_ids" not in r["reference"] for r in rows):
        raise ValueError("strict evaluation requires frozen reference token_ids for every request")
    epoch = time.perf_counter()

    def work(r):
        target = epoch + r["arrival_ms"] / 1000
        sent = time.perf_counter()
        tokens_at = []
        chunks = []
        record = {"request_id": r["request_id"], "deadline_ms": r["deadline_ms"],
                  "dispatch_delay_ms": max(0, (sent - target) * 1000),
                  "status": "failed", "error": None, "token_ids": [], "text": ""}

        def emit(kind, **fields):
            if kind == "token":
                if not fields.get("token_ids"):
                    raise ValueError("empty token event")
                tokens_at.append(time.perf_counter())
                chunks.extend(fields["token_ids"])
            log.emit(r["request_id"], kind, **fields)

        log.emit(r["request_id"], "request_sent", scheduled_ms=r["arrival_ms"])
        try:
            if (sent - target) * 1000 >= r["deadline_ms"]:
                raise TimeoutError("deadline expired in client queue")
            output = adapter.run(r, emit)
            record.update(text=output.text, token_ids=output.token_ids, internal=output.internal or None)
            if chunks != output.token_ids:
                raise ValueError("token event/output mismatch")
            if output.token_ids != r["reference"]["token_ids"]:
                record["error"] = "quality_mismatch"
            else:
                record["status"] = "ok"
        except TimeoutError as exc:
            record["error"] = "timeout: " + str(exc)
        except Exception as exc:
            record["error"] = type(exc).__name__ + ": " + str(exc)
        finished = time.perf_counter()
        e2e = (finished - target) * 1000
        if e2e > r["deadline_ms"]:
            record["status"] = "failed"
            record["error"] = "timeout" + (": " + record["error"] if record["error"] else "")
        record.update(e2e_ms=e2e, service_ms=(finished - sent) * 1000,
                      scored_latency_ms=min(e2e, r["deadline_ms"]) if record["status"] == "ok" else r["deadline_ms"],
                      ttft_ms=(tokens_at[0] - sent) * 1000 if tokens_at else None,
                      chunk_interarrival_ms=[(b-a)*1000 for a,b in zip(tokens_at, tokens_at[1:])],
                      token_timestamp_resolution="SSE chunk receipt; multiple tokens may share one chunk")
        log.emit(r["request_id"], "request_finished", status=record["status"], error=record["error"])
        return record

    futures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        for row in sorted(rows, key=lambda r: r["arrival_ms"]):
            delay = epoch + row["arrival_ms"] / 1000 - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            futures.append(pool.submit(work, row))
        results = [f.result() for f in futures]
    duration = time.perf_counter() - epoch
    ok = [r for r in results if r["status"] == "ok"]
    latencies = [r["scored_latency_ms"] for r in results]
    return {"requests": results, "summary": {
        "total": len(results), "passed": len(ok), "failed": len(results) - len(ok),
        "quality_pass": all(r["status"] == "ok" for r in results),
        "on_time_pass_rate": len(ok) / len(results), "wall_time_s": duration,
        "request_goodput_per_s": len(ok) / duration,
        "validated_token_goodput_per_s": sum(len(r["token_ids"]) for r in ok) / duration,
        "latency_p50_ms": percentile(latencies, .50), "latency_p99_ms": percentile(latencies, .99),
        "ttft_p50_ms": percentile([r["ttft_ms"] for r in ok if r["ttft_ms"] is not None], .5),
        "ttft_p99_ms": percentile([r["ttft_ms"] for r in ok if r["ttft_ms"] is not None], .99),
        "dispatch_delay_p99_ms": percentile([r["dispatch_delay_ms"] for r in results], .99)}}
