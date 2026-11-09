"""Measurements are owned by instrumentation, not candidate-returned times."""
import time


class RequestProbe:
    def __init__(self, log, request_id, scheduled_at):
        self.log = log
        self.request_id = request_id
        self.scheduled_at = scheduled_at
        self.started_at = time.perf_counter()
        self.token_times = []
        self.token_ids = []
        self.action_times = []
        self.emit("request_sent")

    def emit(self, kind, **fields):
        now = time.perf_counter()
        if kind == "token":
            ids = fields.get("token_ids")
            if not isinstance(ids, list) or not ids or any(type(t) is not int or t < 0 for t in ids):
                raise ValueError("token event needs nonnegative token_ids")
            self.token_times.append(now)
            self.token_ids.extend(ids)
        elif kind == "action_ready":
            self.action_times.append(now)
        self.log.emit(self.request_id, kind, **fields)

    def finish(self):
        self.finished_at = time.perf_counter()
        return {
            "dispatch_delay_ms": max(0, self.started_at - self.scheduled_at) * 1000,
            "service_ms": (self.finished_at - self.started_at) * 1000,
            "e2e_ms": (self.finished_at - self.scheduled_at) * 1000,
            "ttft_ms": (self.token_times[0] - self.started_at) * 1000 if self.token_times else None,
            "action_ready_ms": (self.action_times[0] - self.started_at) * 1000 if self.action_times else None,
            "observed_token_ids": list(self.token_ids),
            "token_chunk_interarrival_ms": [(b-a)*1000 for a,b in zip(self.token_times, self.token_times[1:])],
            "clock": "client monotonic; event receipt, not GPU completion",
        }
