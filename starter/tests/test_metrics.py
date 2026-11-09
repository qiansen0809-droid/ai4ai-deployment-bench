from starter.instrumentation.engine_metrics import parse_counters, delta


def test_counter_labels_and_unsupported_metrics():
    raw = '''# HELP vllm:prefix_cache_hits_total Hits
vllm:prefix_cache_hits_total{model_name="a b",engine="0"} 8.0
vllm:prefix_cache_hits_total{model_name="a b",engine="1"} 4.0
vllm:kv_cache_usage_perc 0.5
vllm:generation_tokens_total NaN
'''
    parsed = parse_counters(raw)
    assert len(parsed) == 2 and sum(parsed.values()) == 12


def test_resets_and_new_series_are_not_false_gains():
    result = delta({"counters":{"a":10,"b":3},"error":None},
                   {"counters":{"a":2,"b":7,"c":99},"error":None})
    assert result["counter_deltas"] == {"b":4}
    assert result["missing_or_reset_series"] == ["a","c"]


def test_unavailable_metrics_remain_missing():
    result = delta({"counters":{},"error":"offline"},{"counters":{},"error":"offline"})
    assert result["counter_deltas"] is None and result["before_error"] == "offline"
