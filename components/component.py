from __future__ import annotations

from dataclasses import dataclass

@dataclass
class Component:
    name: str

    def __call__(self, *args, **kwargs):
        return self.process(*args, **kwargs)

    def process(self, *args, **kwargs):
        raise NotImplementedError
