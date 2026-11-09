import hashlib
import json
import math
from pathlib import Path


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode("utf-8")).hexdigest()


def number(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
        raise ValueError(f"{name} must be finite and >= {minimum}")


def validate_request(r):
    if r.get("schema_version") != 1:
        raise ValueError("unsupported schema_version")
    for key in ("request_id", "session_id", "split", "modality"):
        if not isinstance(r.get(key), str) or not r[key]:
            raise ValueError(f"missing {key}")
    if r["modality"] not in ("llm", "vlm", "vla") or r["split"] not in ("dev", "test"):
        raise ValueError("invalid modality or split")
    for key in ("dataset", "version", "original_id"):
        if not isinstance(r.get("source", {}).get(key), str) or not r["source"][key]:
            raise ValueError(f"missing source.{key}")
    number(r.get("arrival_ms"), "arrival_ms")
    number(r.get("deadline_ms"), "deadline_ms", 0.001)
    if not isinstance(r.get("turn"), int) or isinstance(r["turn"], bool) or r["turn"] < 0:
        raise ValueError("invalid turn")
    if not isinstance(r.get("input"), dict):
        raise ValueError("input must be an object")
    if not isinstance(r.get("reference"), dict):
        raise ValueError("reference must be an object")
    for m in r["input"].get("media", []):
        if m.get("kind") not in ("image", "video", "audio") or not m.get("path"):
            raise ValueError("media kind/path required")
        digest = m.get("sha256", "")
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("media sha256 required")
    for key in ("token_ids",):
        if key in r["reference"] and (not isinstance(r["reference"][key], list) or any(type(x) is not int or x < 0 for x in r["reference"][key])):
            raise ValueError("reference token_ids must be nonnegative integers")
    return r


def load_requests(path):
    rows = [validate_request(json.loads(line)) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise ValueError("empty workload")
    if len({r["request_id"] for r in rows}) != len(rows):
        raise ValueError("duplicate request_id")
    sessions = {}
    turns = set()
    for r in rows:
        if r["session_id"] in sessions and sessions[r["session_id"]] != r["split"]:
            raise ValueError("session leakage across dev/test")
        sessions[r["session_id"]] = r["split"]
        pair = (r["session_id"], r["turn"])
        if pair in turns:
            raise ValueError("duplicate session turn")
        turns.add(pair)
    return rows


def verify_media(rows, root):
    root = Path(root).resolve()
    for r in rows:
        for media in r["input"].get("media", []):
            path = (root / media["path"]).resolve()
            if not path.is_relative_to(root):
                raise ValueError("media path escapes data root")
            if hashlib.sha256(path.read_bytes()).hexdigest() != media["sha256"]:
                raise ValueError(f"media hash mismatch: {media['path']}")
