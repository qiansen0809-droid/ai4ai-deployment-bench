"""Print a baseline server command; pass --execute to launch it."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def command(profile, model, revision, port=8000, cpu_gb=8, disk_path=None):
    if not model or not revision:
        raise ValueError("model path/ID and frozen revision are required")
    if type(port) is not int or not 1 <= port <= 65535 or cpu_gb <= 0:
        raise ValueError("invalid port or CPU capacity")
    engine = profile["engine"]
    if engine == "vllm":
        cmd = [sys.executable, "-m", "vllm.entrypoints.cli.main", "serve", model,
               "--revision", revision, "--host", "127.0.0.1", "--port", str(port)]
    elif engine == "sglang":
        cmd = [sys.executable, "-m", "sglang.launch_server", "--model-path", model,
               "--revision", revision, "--host", "127.0.0.1", "--port", str(port)]
    else:
        raise ValueError("unsupported engine")
    cmd += profile.get("args", [])
    env = {}
    kind = profile.get("kind")
    if kind == "weight_offload":
        cmd += ["--cpu-offload-gb", str(cpu_gb)]
    elif kind in ("kv_offload", "kv_three_tier"):
        extra = {"block_size": 16, "cpu_bytes_to_use": int(cpu_gb * 2**30), "eviction_policy": "lru"}
        if kind == "kv_three_tier":
            if not disk_path:
                raise ValueError("--disk-path required for three-tier cache")
            extra.update(spec_name="TieringOffloadingSpec", secondary_tiers=[{"type": "fs", "root_dir": str(Path(disk_path).resolve())}])
        cmd += ["--kv-transfer-config", json.dumps({"kv_connector": "OffloadingConnector", "kv_role": "kv_both", "kv_connector_extra_config": extra})]
    elif kind == "lmcache":
        if not disk_path:
            raise ValueError("--disk-path required for LMCache three-tier cache")
        cmd += ["--kv-transfer-config", json.dumps({"kv_connector": "LMCacheConnectorV1", "kv_role": "kv_both"})]
        env = {"LMCACHE_LOCAL_CPU": "True", "LMCACHE_MAX_LOCAL_CPU_SIZE": str(cpu_gb),
               "LMCACHE_LOCAL_DISK": "file://" + Path(disk_path).resolve().as_posix(), "LMCACHE_MAX_LOCAL_DISK_SIZE": "20"}
    return cmd, env


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("profile"); p.add_argument("--model", required=True); p.add_argument("--revision", required=True)
    p.add_argument("--port", type=int, default=8000); p.add_argument("--cpu-gb", type=float, default=8)
    p.add_argument("--disk-path"); p.add_argument("--execute", action="store_true")
    a = p.parse_args()
    profile = json.loads(Path(a.profile).read_text(encoding="utf-8"))
    cmd, env = command(profile, a.model, a.revision, a.port, a.cpu_gb, a.disk_path)
    print(json.dumps({"argv": cmd, "environment_overrides": env, "track": profile["track"],
                      "status": "configuration only; GPU integration unverified"}, indent=2))
    if a.execute:
        raise SystemExit(subprocess.call(cmd, env={**os.environ, **env}))


if __name__ == "__main__":
    main()
