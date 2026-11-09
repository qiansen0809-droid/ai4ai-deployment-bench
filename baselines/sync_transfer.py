"""CUDA synchronous H2D/D2H microbenchmark; NOT model-serving results."""
import argparse
import json
import time


def run(mib=64, repeats=10, pinned=False):
    import torch
    if mib <= 0 or repeats <= 0 or not torch.cuda.is_available():
        raise ValueError("positive size/repeats and CUDA PyTorch required")
    src = torch.arange(mib * 1024 * 1024, dtype=torch.int64).remainder(251).to(torch.uint8)
    if pinned:
        src = src.pin_memory()
    gpu = torch.empty_like(src, device="cuda")
    dst = torch.empty_like(src, pin_memory=pinned)
    gpu.copy_(src, non_blocking=False)
    dst.copy_(gpu, non_blocking=False)
    torch.cuda.synchronize()
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        gpu.copy_(src, non_blocking=False)
        dst.copy_(gpu, non_blocking=False)
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - start
        if not torch.equal(src, dst):
            raise RuntimeError("round-trip corruption")
        samples.append(elapsed)
    return {"kind": "microbenchmark", "synchronous": True, "overlap": False,
            "pinned": pinned, "bytes_per_direction": src.numel(), "round_trip_seconds": samples,
            "gpu": torch.cuda.get_device_name(), "torch": torch.__version__, "cuda": torch.version.cuda}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mib", type=int, default=64); p.add_argument("--repeats", type=int, default=10)
    p.add_argument("--pinned", action="store_true")
    a = p.parse_args()
    print(json.dumps(run(a.mib, a.repeats, a.pinned), indent=2))
