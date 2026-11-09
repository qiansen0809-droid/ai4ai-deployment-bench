"""Local vLLM completion SSE client. No hosted API credentials required."""
import json
import time
import urllib.request
from starter.adapters.base import Output


class VLLMAdapter:
    def __init__(self, endpoint, model, timeout_s=30):
        self.url = endpoint.rstrip("/") + "/v1/completions"
        self.model = model
        self.timeout_s = timeout_s

    def run(self, request, emit):
        if request["modality"] != "llm" or request["input"].get("media") or request["input"].get("tool_events"):
            raise ValueError("completion adapter supports text only; tool lifecycle requires a resumable adapter")
        g = request.get("generation", {})
        if g.get("temperature", 0) != 0 or g.get("n", 1) != 1:
            raise ValueError("strict track requires greedy single output")
        allowed = {"max_tokens", "temperature", "seed", "ignore_eos", "stop_token_ids"}
        if set(g) - allowed:
            raise ValueError(f"unsupported generation keys: {set(g) - allowed}")
        if not isinstance(g.get("max_tokens"), int) or g["max_tokens"] <= 0:
            raise ValueError("positive max_tokens required")
        payload = {"model": self.model, "prompt": request["input"]["text"],
                   "temperature": 0, **g, "stream": True, "return_token_ids": True}
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json", "X-Request-Id": request["request_id"]})
        output = Output()
        start = time.perf_counter()
        done = False
        with urllib.request.urlopen(req, timeout=self.timeout_s) as response:
            for raw in response:
                if time.perf_counter() - start > self.timeout_s:
                    raise TimeoutError("stream deadline exceeded")
                line = raw.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    done = True
                    break
                chunk = json.loads(data)
                if "error" in chunk:
                    raise RuntimeError(str(chunk["error"]))
                for choice in chunk.get("choices", []):
                    ids = choice.get("token_ids") or []
                    text = choice.get("text", "")
                    if text and not ids:
                        raise ValueError("server did not return token IDs; strict validation unavailable")
                    if ids:
                        if any(type(t) is not int or t < 0 for t in ids):
                            raise ValueError("invalid token IDs")
                        emit("token", token_ids=ids)
                        output.token_ids.extend(ids)
                    output.text += text
        if not done:
            raise RuntimeError("truncated SSE stream")
        return output
