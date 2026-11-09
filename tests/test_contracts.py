import copy
import hashlib
import json
import time
from pathlib import Path
import pytest
from adapters.mock import MockAdapter
from adapters.base import Output
from baselines.lru import LRU
from baselines.launch import command
from evaluation.check_scope import check_paths
from evaluation.run import validate_config
from evaluation.runner import replay
from instrumentation.events import EventLog
from instrumentation.recovery import RecoveryGuard
from tasks.schema import load_requests, validate_request, verify_media


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def row():
    return load_requests(ROOT / "tasks/llm/mock_requests.jsonl")[0]


def run_one(tmp_path, row, adapter):
    log = EventLog(tmp_path / "events.jsonl", "test")
    try:
        return replay([row], adapter, log)
    finally:
        log.close()




@pytest.mark.parametrize("field,value", [("arrival_ms",float("nan")), ("deadline_ms",-1), ("turn",True)])
def test_bad_request(row, field, value):
    row[field] = value
    with pytest.raises(ValueError): validate_request(row)


def test_duplicate_and_split_leakage(tmp_path, row):
    other = copy.deepcopy(row); other["request_id"] = "other"; other["turn"] = 1; other["split"] = "test"
    p = tmp_path / "requests.jsonl"
    p.write_text(json.dumps(row) + "\n" + json.dumps(other), encoding="utf-8")
    with pytest.raises(ValueError, match="leakage"): load_requests(p)
    p.write_text(json.dumps(row) + "\n" + json.dumps(row), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"): load_requests(p)


def test_media_corruption_and_escape(tmp_path, row):
    (tmp_path / "img.bin").write_bytes(b"pixels")
    media = {"kind":"image", "path":"img.bin", "sha256":hashlib.sha256(b"pixels").hexdigest()}
    row["input"]["media"] = [media]
    verify_media([row], tmp_path)
    (tmp_path / "img.bin").write_bytes(b"tamper")
    with pytest.raises(ValueError, match="hash mismatch"): verify_media([row], tmp_path)
    media["path"] = "../escape"
    with pytest.raises(ValueError, match="escapes"): verify_media([row], tmp_path)


def test_mock_replay(tmp_path, row):
    result = run_one(tmp_path, row, MockAdapter())
    assert result["summary"]["quality_pass"]
    assert result["requests"][0]["token_ids"] == row["reference"]["token_ids"]
    events = [json.loads(s) for s in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert events[0]["kind"] == "request_sent"
    assert events[-1]["kind"] == "request_finished"
    assert all(e["run_id"] == "test" for e in events)


def test_wrong_tokens_count_as_failure(tmp_path, row):
    row["reference"]["token_ids"] = [999]
    result = run_one(tmp_path, row, MockAdapter())
    assert result["summary"]["failed"] == 1
    assert result["summary"]["validated_token_goodput_per_s"] == 0
    assert result["summary"]["latency_p99_ms"] == row["deadline_ms"]


def test_timeout_not_dropped(tmp_path, row):
    class Slow(MockAdapter):
        def run(self, r, emit):
            time.sleep(.02)
            return super().run(r, emit)
    row["deadline_ms"] = 1
    result = run_one(tmp_path, row, Slow())
    assert result["summary"]["failed"] == 1
    assert "timeout" in result["requests"][0]["error"]


def test_event_output_mismatch(tmp_path, row):
    class Forged:
        def run(self, r, emit): return Output(token_ids=r["reference"]["token_ids"])
    result = run_one(tmp_path, row, Forged())
    assert result["summary"]["failed"] == 1


def test_missing_reference_rejected(tmp_path, row):
    row["reference"] = {}
    with pytest.raises(ValueError, match="reference"): run_one(tmp_path, row, MockAdapter())


def test_lru_eviction_and_capacity():
    cache = LRU(4)
    cache.put("a", b"aa"); cache.put("b", b"bb"); cache.get("a"); cache.put("c", b"cc")
    with pytest.raises(KeyError): cache.get("b")
    assert cache.get("a") == b"aa" and cache.used == 4
    with pytest.raises(ValueError): cache.put("z", b"12345")
    assert cache.used == 4


def test_recovery_corruption_and_order():
    g = RecoveryGuard(); g.tool_wait("r", 3, b"kv")
    with pytest.raises(ValueError, match="order"): g.tool_done("r", 4, b"kv")
    with pytest.raises(ValueError, match="checksum"): g.tool_done("r", 3, b"bad")
    g.tool_done("r", 3, b"kv")
    with pytest.raises(ValueError, match="unexpected"): g.tool_done("r", 3, b"kv")










def test_templates_fail_closed():
    for path in (ROOT / "tasks").glob("*/template.json"):
        with pytest.raises(ValueError): validate_config(json.loads(path.read_text()))


def test_baseline_commands_and_tracks(tmp_path):
    for path in (ROOT / "baselines/configs").glob("*.json"):
        profile = json.loads(path.read_text())
        cmd, env = command(profile, "local/model", "frozen-revision", disk_path=tmp_path)
        assert "local/model" in cmd and "frozen-revision" in cmd
        assert all(isinstance(x,str) for x in cmd)
        if profile["name"] == "fp8_kv": assert profile["track"] == "quality"
    with pytest.raises(ValueError): command({"engine":"vllm"}, "", "rev")


def test_scope_protects_evaluator_and_path_traversal():
    assert check_paths(["vllm/v1/core/scheduler.py"], ["vllm/v1/core"]) == []
    assert len(check_paths(["evaluation/run.py","vllm/v1/core/../evil.py"], ["vllm/v1/core"])) == 2
