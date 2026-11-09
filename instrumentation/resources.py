"""nvidia-smi device memory samples; not exact allocator or process peak."""
import csv
import io
import shutil
import subprocess
import threading
import time


class GPUSampler:
    def __init__(self, interval_s=0.25):
        self.interval_s = interval_s
        self.samples = []
        self.error = None
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        if not shutil.which("nvidia-smi"):
            self.error = "nvidia-smi unavailable"
            return
        self.thread = threading.Thread(target=self._sample, daemon=True)
        self.thread.start()

    def _sample(self):
        while not self.stop_event.is_set():
            try:
                p = subprocess.run(["nvidia-smi", "--query-gpu=uuid,memory.used", "--format=csv,noheader,nounits"],
                                   capture_output=True, text=True, check=True, timeout=5)
                for uuid, mib in csv.reader(io.StringIO(p.stdout)):
                    self.samples.append({"monotonic_ns": time.perf_counter_ns(), "gpu_uuid": uuid.strip(), "used_mib": float(mib)})
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                self.error = str(exc)
                return
            self.stop_event.wait(self.interval_s)

    def finish(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=6)
        peaks = {}
        for s in self.samples:
            peaks[s["gpu_uuid"]] = max(peaks.get(s["gpu_uuid"], 0), s["used_mib"])
        return {"method": "nvidia-smi device-wide sampled memory; includes other processes",
                "interval_s": self.interval_s, "peak_mib_by_gpu": peaks or None,
                "cpu_peak_bytes": None, "error": self.error, "samples": self.samples}
