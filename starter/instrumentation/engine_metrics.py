"""Read vLLM's existing /metrics instrumentation without changing inference."""
import math
import re
import urllib.request


COUNTERS = {
    "vllm:prefix_cache_queries_total", "vllm:prefix_cache_hits_total",
    "vllm:external_prefix_cache_queries_total", "vllm:external_prefix_cache_hits_total",
    "vllm:num_preemptions_total", "vllm:prompt_tokens_total", "vllm:generation_tokens_total",
    "vllm:kv_offload_load_bytes_total", "vllm:kv_offload_store_bytes_total",
    "vllm:kv_offload_load_time_total", "vllm:kv_offload_store_time_total",
}
LINE = re.compile(r'^(?P<name>[a-zA-Z_:][a-zA-Z_0-9:]*)(?P<labels>\{(?:[^"}]|"(?:\\.|[^"\\])*")*\})?\s+(?P<value>\S+)(?:\s+\S+)?$')


def parse_counters(text):
    samples = {}
    for line in text.splitlines():
        match = LINE.match(line)
        if not match or match["name"] not in COUNTERS:
            continue
        value = float(match["value"])
        if not math.isfinite(value) or value < 0:
            continue
        key = match["name"] + (match["labels"] or "")
        samples[key] = value
    return samples


def snapshot(endpoint, path):
    try:
        with urllib.request.urlopen(endpoint.rstrip("/") + "/metrics", timeout=5) as response:
            raw = response.read(10_000_001)
        if len(raw) > 10_000_000:
            raise ValueError("metrics response exceeds 10 MB")
        text = raw.decode("utf-8")
        path.write_text(text, encoding="utf-8")
        return {"counters": parse_counters(text), "error": None}
    except (OSError, ValueError) as exc:
        return {"counters": {}, "error": str(exc)}


def delta(before, after):
    values = {}
    invalid = []
    for key in before["counters"].keys() | after["counters"].keys():
        a, b = before["counters"].get(key), after["counters"].get(key)
        if a is None or b is None or b < a:
            invalid.append(key)
        else:
            values[key] = b - a
    return {"counter_deltas": values or None, "missing_or_reset_series": sorted(invalid),
            "before_error": before["error"], "after_error": after["error"],
            "scope": "server-wide, labels preserved; requires exclusive server; reporting may lag",
            "per_request_transfer_bytes": None}
