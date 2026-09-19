from __future__ import annotations

from dataclasses import dataclass
import hashlib
import random


@dataclass(frozen=True)
class RouteEvent:
    s0: float
    s1: float
    kind: str
    family_id: str | None = None

    def contains(self, s: float) -> bool:
        return self.s0 <= s <= self.s1


def deterministic_seed(project_seed: str, subsystem: str, tunnel_id: str, bucket: str = "") -> int:
    payload = f"{project_seed}|{subsystem}|{tunnel_id}|{bucket}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def periodic_positions(s0: float, s1: float, pitch: float, *, seed: int, jitter: float = 0.0) -> list[float]:
    if pitch <= 0 or s1 < s0 or jitter < 0:
        raise ValueError("invalid periodic placement inputs")
    rng = random.Random(seed)
    phase = rng.uniform(0.0, pitch)
    out = []
    k = int((s0 - phase) // pitch) - 1
    while True:
        nominal = phase + k * pitch
        if nominal > s1 + pitch:
            break
        if s0 <= nominal <= s1:
            pos = nominal + (rng.uniform(-jitter, jitter) if jitter else 0.0)
            if s0 <= pos <= s1:
                out.append(pos)
        k += 1
    return sorted(out)


def filter_by_override_events(positions: list[float], events: list[RouteEvent]) -> list[float]:
    return [s for s in positions if not any(e.contains(s) for e in events)]
