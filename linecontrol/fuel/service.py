"""Deliveries are accumulated from the committed record stream."""

from typing import Any, Dict

from ..runtime.errors import ValidationError
from ..store.kinds import KIND_FUEL_DELIVER
from .errors import TankOverflow


class FuelService:
    def __init__(self, log, clock, registry) -> None:
        self._log = log
        self._clock = clock
        self._registry = registry

    def delivered_liters(self) -> float:
        total = 0.0
        for record in self._log.by_kind(KIND_FUEL_DELIVER):
            total += float(record.payload.get("liters", 0.0))
        return round(total, 6)

    def capacity_liters(self) -> float:
        return self._registry.value("fuel.tank_capacity_l")

    def deliver(self, liters: float) -> Dict[str, Any]:
        value = float(liters)
        if value <= 0:
            raise ValidationError("delivery volume must be positive", liters=value)
        projected = round(self.delivered_liters() + value, 6)
        if projected > self.capacity_liters():
            raise TankOverflow(
                "delivery would exceed the tank capacity",
                delivered_liters=self.delivered_liters(),
                capacity_liters=self.capacity_liters(),
            )
        record = self._log.append(
            KIND_FUEL_DELIVER,
            generation=self._registry.combine(("fuel.tank_capacity_l",)),
            payload={"liters": round(value, 6)},
            tick=self._clock.tick,
        )
        self._log.commit(tick=self._clock.tick)
        return {"delivered_liters": projected, "record": record.record_id}

    def status(self) -> Dict[str, Any]:
        delivered = self.delivered_liters()
        capacity = self.capacity_liters()
        return {
            "delivered_liters": delivered,
            "capacity_liters": capacity,
            "remaining_liters": round(capacity - delivered, 6),
            "fill_ratio": round(delivered / capacity, 6) if capacity else 0.0,
        }
