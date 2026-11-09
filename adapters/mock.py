from adapters.base import Output


class MockAdapter:
    """Deterministic interface fixture, never a performance baseline."""
    def run(self, request, emit):
        tokens = [ord(c) for c in request["input"].get("text", "")]
        for token in tokens:
            emit("token", token_ids=[token])
        return Output(text=request["input"].get("text", ""), token_ids=tokens)
