import copy
import hashlib
import json
import time
from pathlib import Path
import pytest
from starter.adapters.base import Output
from baselines.lru import LRU
from baselines.launch import command
from starter.evaluation.check_scope import check_paths
from starter.instrumentation.events import EventLog
from starter.instrumentation.recovery import RecoveryGuard


ROOT = Path(__file__).resolve().parents[2]


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
