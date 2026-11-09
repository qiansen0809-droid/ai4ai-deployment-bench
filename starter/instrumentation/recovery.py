"""Reference state integrity guard for engine adapters to call on restore.

Detects byte corruption and out-of-order tool events. It does not implement KV
offload or establish that an engine calls the guard correctly.
"""
import hashlib


class RecoveryGuard:
    def __init__(self):
        self.waiting = {}

    def tool_wait(self, request_id, tool_sequence, state):
        if request_id in self.waiting:
            raise ValueError("request already waiting")
        self.waiting[request_id] = (tool_sequence, hashlib.sha256(state).hexdigest())

    def tool_done(self, request_id, tool_sequence, restored_state):
        if request_id not in self.waiting:
            raise ValueError("unexpected tool result")
        seq, digest = self.waiting[request_id]
        if seq != tool_sequence:
            raise ValueError("tool result out of order")
        if digest != hashlib.sha256(restored_state).hexdigest():
            raise ValueError("restore checksum mismatch")
        del self.waiting[request_id]
