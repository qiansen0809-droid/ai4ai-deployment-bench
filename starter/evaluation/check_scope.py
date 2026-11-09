"""Path allowlist check; advisory only, not a sandbox or semantic proof."""
import argparse
import json
import subprocess
from pathlib import Path, PurePosixPath


def check_paths(paths, allowed):
    denied = []
    for path in paths:
        p = PurePosixPath(path)
        if p.is_absolute() or ".." in p.parts or not any(path.startswith(prefix.rstrip("/") + "/") for prefix in allowed):
            denied.append(path)
    return denied


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", required=True); p.add_argument("--base", required=True); p.add_argument("--head", default="HEAD")
    p.add_argument("--policy", required=True)
    a = p.parse_args()
    policy = json.loads(Path(a.policy).read_text(encoding="utf-8"))
    data = subprocess.check_output(["git", "-C", a.repo, "diff", "--no-renames", "--name-only", "-z", a.base, a.head])
    denied = check_paths([s for s in data.decode().split("\0") if s], policy["allowed_paths"])
    print(json.dumps({"passed": not denied, "denied": denied}))
    raise SystemExit(bool(denied))
