from dataclasses import dataclass, field
from typing import Protocol, Callable


@dataclass
class Output:
    text: str = ""
    token_ids: list[int] = field(default_factory=list)
    actions: list = field(default_factory=list)
    internal: dict = field(default_factory=dict)


class Adapter(Protocol):
    """One call per request; instances must support concurrent calls.

    emit(kind, **fields) feeds the read-only instrumentation sink. Token events
    mark client receipt, NOT GPU kernel completion. raise on protocol failure.
    """
    def run(self, request: dict, emit: Callable) -> Output: ...


class ResumableAdapter(Protocol):
    """Engine-specific lifecycle; HTTP adapter does not pretend to support it."""
    def submit(self, request: dict): ...
    def tool_wait(self, request_id: str, expected_ms: float): ...
    def tool_done(self, request_id: str, result: dict, state_sha256: str): ...
    def result(self, request_id: str) -> Output: ...
