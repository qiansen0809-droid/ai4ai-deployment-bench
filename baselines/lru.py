"""Small byte-capacity LRU reference for contract tests, NOT an engine KV cache."""
from collections import OrderedDict


class LRU:
    def __init__(self, capacity_bytes):
        if type(capacity_bytes) is not int or capacity_bytes < 0:
            raise ValueError("capacity must be a nonnegative integer")
        self.capacity = capacity_bytes
        self.entries = OrderedDict()
        self.used = 0

    def get(self, key):
        value = self.entries[key]
        self.entries.move_to_end(key)
        return value

    def put(self, key, value):
        if not isinstance(value, bytes):
            raise TypeError("immutable bytes required")
        if len(value) > self.capacity:
            raise ValueError("entry exceeds capacity")
        if key in self.entries:
            self.used -= len(self.entries.pop(key))
        while self.used + len(value) > self.capacity:
            _, old = self.entries.popitem(last=False)
            self.used -= len(old)
        self.entries[key] = value
        self.used += len(value)
