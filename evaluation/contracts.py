"""Internal execution contracts, NOT a dataset serialization format.

Dataset owners map their records to WorkItem; payload/reference remain opaque.
Providers and quality judges are trusted evaluator code, not candidate code.
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class WorkItem:
    request_id: str
    payload: Any
    reference: Any = None
    arrival_ms: float = 0
    deadline_ms: float = 30000
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class Verdict:
    passed: bool
    reason: str | None = None
    metrics: dict = field(default_factory=dict)


@dataclass
class Task:
    items: Iterable[WorkItem]
    execute: Callable  # execute(item, emit) -> JSON-serializable value/dataclass
    judge: Callable  # judge(item, output) -> Verdict; runs outside inference timing
    concurrency: int = 1
    metadata: dict = field(default_factory=dict)
    setup: Callable = lambda: None  # readiness/reset/warmup, outside replay timing
    teardown: Callable = lambda: None
    observers: tuple = ()  # start(output_dir), finish(output_dir) -> measurements
    simulated: bool = False


class RunAborted(RuntimeError):
    """An engine-wide crash invalidates all requests in this distribution."""
