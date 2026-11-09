import json
import time
from pathlib import Path
import pytest
from starter.evaluation.contracts import Task, WorkItem, Verdict, RunAborted
from starter.evaluation.providers import build_task
from starter.evaluation.run import evaluate


def test_opaque_payloads_and_action_outputs_need_no_llm_schema(tmp_path):
    payload = object()  # no serialization, text field, media format or tokenizer
    seen = []

    def execute(item, emit):
        assert item.payload is payload
        seen.append(item.request_id)
        emit("action_ready", action_count=2)
        return {"actions": [0.1, -0.5]}

    task = Task([WorkItem("step", payload)], execute,
                lambda item, output: Verdict(output["actions"] == [0.1, -0.5]), simulated=True)
    result = evaluate(task, tmp_path / "run")
    assert result["summary"]["all_passed"] and seen == ["step"]
    measurement = result["requests"][0]["measurement"]
    assert measurement["ttft_ms"] is None and measurement["action_ready_ms"] is not None
    assert result["requests"][0]["output"]["actions"] == [0.1, -0.5]


def test_dependency_order_and_provider_state_are_shared(tmp_path):
    order = []
    def execute(item, emit):
        if item.request_id == "second":
            assert order == ["first"]
        order.append(item.request_id)
        return {"value": len(order)}
    task = Task([WorkItem("second", None, dependencies=("first",)), WorkItem("first", None)],
                execute, lambda i,o: Verdict(True), concurrency=2)
    assert evaluate(task, tmp_path / "run")["summary"]["all_passed"]
    assert order == ["first", "second"]


@pytest.mark.parametrize("items", [
    [], [WorkItem("a", None), WorkItem("a", None)],
    [WorkItem("a", None, dependencies=("missing",))],
    [WorkItem("a", None, dependencies=("b",)), WorkItem("b", None, dependencies=("a",))],
    [WorkItem("a", None, arrival_ms=float("nan"))],
])
def test_invalid_execution_graph_rejected_before_setup(tmp_path, items):
    task = Task(items, lambda *a: None, lambda *a: Verdict(True), setup=lambda: pytest.fail("must not start"))
    with pytest.raises(ValueError): evaluate(task, tmp_path / "run")


def test_failed_dependency_never_dispatched(tmp_path):
    calls = []
    def execute(item, emit):
        calls.append(item.request_id)
        return 0
    task = Task([WorkItem("a", None), WorkItem("b", None, dependencies=("a",))], execute,
                lambda *a: Verdict(False, "quality_mismatch"), concurrency=2)
    result = evaluate(task, tmp_path / "run")
    assert calls == ["a"] and result["summary"]["failed"] == 2
    assert result["requests"][1]["error"] == "dependency_failed"


def test_engine_crash_invalidates_distribution(tmp_path):
    def execute(item, emit):
        if item.request_id == "b": raise RunAborted("worker exited")
        return "ok"
    task = Task([WorkItem(x, None) for x in "abc"], execute, lambda *a: Verdict(True))
    result = evaluate(task, tmp_path / "run")
    assert result["summary"]["passed"] == 0
    assert all(r["error"].startswith("engine_crash") for r in result["requests"])


def test_deadline_failure_retained(tmp_path):
    def execute(item, emit):
        time.sleep(.02)
        return "ok"
    result = evaluate(Task([WorkItem("a", None, deadline_ms=1)], execute, lambda *a: Verdict(True)), tmp_path / "run")
    assert result["summary"]["failed"] == 1
    assert result["requests"][0]["scored_latency_ms"] == 1


def test_judge_runs_after_inference_measurements_are_frozen(tmp_path, monkeypatch):
    from starter.instrumentation.probe import RequestProbe
    finished = []
    original_finish = RequestProbe.finish
    def finish(probe):
        measured = original_finish(probe)
        finished.append(True)
        return measured
    monkeypatch.setattr(RequestProbe, "finish", finish)
    def judge(item, output):
        assert finished == [True]
        return Verdict(True)
    result = evaluate(Task([WorkItem("a", None)], lambda *a: "ok", judge), tmp_path / "run")
    assert result["summary"]["all_passed"]


def test_token_stream_must_match_output(tmp_path):
    def execute(item, emit):
        emit("token", token_ids=[1])
        return {"token_ids": [2]}
    result = evaluate(Task([WorkItem("a", None)], execute, lambda *a: Verdict(True)), tmp_path / "run")
    assert result["summary"]["failed"] == 1


def test_setup_failure_writes_failure_artifact_and_tears_down(tmp_path):
    cleaned = []
    def setup(): raise RuntimeError("model unavailable")
    task = Task([WorkItem("a", None)], lambda *a: 1, lambda *a: Verdict(True),
                setup=setup, teardown=lambda: cleaned.append(True))
    result = evaluate(task, tmp_path / "run")
    assert cleaned and result["summary"]["failed"] == 1
    assert json.loads((tmp_path / "run/result.json").read_text())["summary"]["run_error"]


def test_observers_are_closed_after_partial_start_failure(tmp_path):
    closed = []
    class Observer:
        def start(self, directory): raise RuntimeError("sample failure")
        def finish(self, directory): closed.append(True); return {"sample": None}
    task = Task([WorkItem("a", None)], lambda *a: 1, lambda *a: Verdict(True), observers=(Observer(),))
    result = evaluate(task, tmp_path / "run")
    assert closed and result["summary"]["failed"] == 1


def test_smoke_fixture_uses_common_entry(tmp_path):
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "tests/fixtures/smoke.json").read_text())
    task = build_task(config["provider"], config, root / "tests/fixtures")
    result = evaluate(task, tmp_path / "run", config)
    assert result["simulated"] and result["summary"]["passed"] == 3
