"""Rider waiting time accounting."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WaitingRecord:
    request_id: str
    queue_wait_min: float = 0.0
    pickup_travel_min: float = 0.0

    @property
    def total_wait_min(self) -> float:
        return self.queue_wait_min + self.pickup_travel_min


@dataclass
class WaitingTimeTracker:
    records: dict[str, WaitingRecord] = field(default_factory=dict)

    def start_queue(self, request_id: str, queue_wait_min: float) -> None:
        self.records[request_id] = WaitingRecord(
            request_id=request_id,
            queue_wait_min=queue_wait_min,
        )

    def add_pickup(self, request_id: str, pickup_travel_min: float) -> None:
        rec = self.records[request_id]
        rec.pickup_travel_min = pickup_travel_min

    def mean_total_wait_min(self) -> float:
        if not self.records:
            return 0.0
        return sum(r.total_wait_min for r in self.records.values()) / len(self.records)
