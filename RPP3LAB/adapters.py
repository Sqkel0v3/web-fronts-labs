from datetime import datetime, timedelta

from scooters import (
    AggregateNotFound,
    Client,
    ClientId,
    Money,
    Scooter,
    ScooterId,
    Trip,
    TripId,
)


class ClockMovedBack(Exception):
    pass


class ShiftedClock:
    def __init__(self):
        self._offset = timedelta(0)

    def now(self) -> datetime:
        return datetime.now() + self._offset

    def move_to(self, moment: datetime):
        if moment < self.now():
            raise ClockMovedBack("Перевод часов назад запрещён")
        self._offset = moment - datetime.now()


class InMemoryPaymentGateway:
    def __init__(self):
        self._declined_authorization: set = set()
        self._declined_charge: set = set()
        self.operations: list = []

    def decline_authorization_for(self, client_id: ClientId):
        self._declined_authorization.add(client_id)

    def decline_charge_for(self, client_id: ClientId):
        self._declined_charge.add(client_id)

    def authorize(self, client_id: ClientId, amount: Money) -> bool:
        approved = client_id not in self._declined_authorization
        self.operations.append(("authorize", client_id, amount, approved))
        return approved

    def charge(self, client_id: ClientId, amount: Money) -> bool:
        charged = client_id not in self._declined_charge
        self.operations.append(("charge", client_id, amount, charged))
        return charged


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

    def all(self) -> list:
        return list(self._items.values())


class InMemoryClientRepository:
    def __init__(self):
        self._items: dict[ClientId, Client] = {}

    def get(self, client_id: ClientId) -> Client:
        if client_id not in self._items:
            raise AggregateNotFound("Клиент не найден")
        return self._items[client_id]

    def save(self, client: Client):
        self._items[client.id] = client
