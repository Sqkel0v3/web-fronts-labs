"""In-memory репозитории (база данных — словари). Реализуют порты из scooters.py."""
from __future__ import annotations

from scooters import Scooter, ScooterId, Trip, TripId


class InMemoryScooterRepository:
    def __init__(self) -> None:
        self._items: dict[ScooterId, Scooter] = {}

    def get(self, scooter_id: ScooterId) -> Scooter:
        return self._items[scooter_id]

    def save(self, scooter: Scooter) -> None:
        self._items[scooter.id] = scooter


class InMemoryTripRepository:
    def __init__(self) -> None:
        self._items: dict[TripId, Trip] = {}

    def get(self, trip_id: TripId) -> Trip:
        return self._items[trip_id]

    def save(self, trip: Trip) -> None:
        self._items[trip.id] = trip