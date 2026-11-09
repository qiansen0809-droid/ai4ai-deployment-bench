import json
import threading
import time


class EventLog:
    def __init__(self, path, run_id):
        self.file = open(path, "x", encoding="utf-8")
        self.run_id = run_id
        self.start_ns = time.perf_counter_ns()
        self.lock = threading.Lock()

    def emit(self, request_id, kind, **fields):
        if set(fields) & {"run_id", "request_id", "kind", "time_ns"}:
            raise ValueError("reserved event field")
        with self.lock:
            record = {"run_id": self.run_id, "request_id": request_id, "kind": kind,
                      "time_ns": time.perf_counter_ns() - self.start_ns, **fields}
            self.file.write(json.dumps(record, allow_nan=False) + "\n")
            self.file.flush()
        return record

    def close(self):
        self.file.close()
