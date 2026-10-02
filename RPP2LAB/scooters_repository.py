from scooters import AggregateNotFound, Scooter, ScooterId, Trip, TripId


class InMemoryScooterRepository:
    def __init__(self):
        self._items: dict[ScooterId, Scooter] = {}

    def get(self, scooter_id: ScooterId) -> Scooter:
        if scooter_id not in self._items:
            raise AggregateNotFound("Самокат не найден")
        return self._items[scooter_id]

    def save(self, scooter: Scooter):
        self._items[scooter.id] = scooter


class InMemoryTripRepository:
    def __init__(self):
        self._items: dict[TripId, Trip] = {}

    def get(self, trip_id: TripId) -> Trip:
        if trip_id not in self._items:
            raise AggregateNotFound("Поездка не найдена")
        return self._items[trip_id]

    def save(self, trip: Trip):
        self._items[trip.id] = trip