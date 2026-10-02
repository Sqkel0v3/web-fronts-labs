"""ЛР2. Доменная модель «Прокат самокатов» (DDD).  Запуск: python scooters.py"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Protocol
from uuid import UUID, uuid4


# ===== 1. Доменные исключения =====

class DomainError(Exception):
    """Базовое доменное исключение."""


class InvalidValueObject(DomainError):
    """Некорректные данные при создании объекта-значения."""


class DomainInvariantViolation(DomainError):
    """Операция нарушает инвариант агрегата."""


# ===== 2. Объекты-значения =====

@dataclass(frozen=True)
class ScooterId:
    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise InvalidValueObject("ScooterId должен быть UUID")

    @staticmethod
    def new() -> ScooterId:
        return ScooterId(uuid4())


@dataclass(frozen=True)
class TripId:
    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise InvalidValueObject("TripId должен быть UUID")

    @staticmethod
    def new() -> TripId:
        return TripId(uuid4())


@dataclass(frozen=True)
class BatteryLevel:
    percent: int

    def __post_init__(self) -> None:
        if not 0 <= self.percent <= 100:
            raise InvalidValueObject("Заряд должен быть от 0 до 100 %")


@dataclass(frozen=True)
class Money:
    amount: Decimal

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise InvalidValueObject("Сумма не может быть отрицательной")


@dataclass(frozen=True)
class Tariff:
    price_per_minute: Money
    min_price: Money

    def __post_init__(self) -> None:
        if self.price_per_minute.amount <= 0:
            raise InvalidValueObject("Цена за минуту должна быть больше нуля")


# ===== 3. Агрегат Scooter (корень — Scooter) =====

class ScooterStatus(Enum):
    AVAILABLE = "свободен"
    RENTED = "арендован"
    MAINTENANCE = "на обслуживании"


class Scooter:
    MIN_BATTERY = 20
    __slots__ = ("_id", "_battery", "_status")

    def __init__(self, scooter_id: ScooterId, battery: BatteryLevel,
                 status: ScooterStatus = ScooterStatus.AVAILABLE) -> None:
        self._id = scooter_id
        self._battery = battery
        self._status = status

    @property
    def id(self) -> ScooterId:
        return self._id

    @property
    def status(self) -> ScooterStatus:
        return self._status

    def rent(self) -> None:
        """Инвариант: выдать можно только свободный самокат с зарядом не ниже порога."""
        if self._status is not ScooterStatus.AVAILABLE:
            raise DomainInvariantViolation(f"Самокат {self._status.value}")
        if self._battery.percent < self.MIN_BATTERY:
            raise DomainInvariantViolation(f"Заряд ниже {self.MIN_BATTERY} %")
        self._status = ScooterStatus.RENTED


# ===== 4. Агрегат Trip (корень — Trip, связь со Scooter только по scooter_id) =====

class Trip:
    __slots__ = ("_id", "_scooter_id", "_started_at", "_finished_at", "_tariff")

    def __init__(self, trip_id: TripId, scooter_id: ScooterId, started_at: datetime, tariff: Tariff) -> None:
        self._id = trip_id
        self._scooter_id = scooter_id
        self._started_at = started_at
        self._tariff = tariff
        self._finished_at: datetime | None = None

    @property
    def id(self) -> TripId:
        return self._id

    def finish(self, finished_at: datetime) -> Money:
        """Инвариант: поездку нельзя завершить дважды и раньше начала;
        стоимость = цена за минуту × минуты, но не меньше минимальной."""
        if self._finished_at is not None:
            raise DomainInvariantViolation("Поездка уже завершена")
        if finished_at < self._started_at:
            raise DomainInvariantViolation("Поездка не может завершиться раньше начала")
        self._finished_at = finished_at
        minutes = math.ceil((finished_at - self._started_at).total_seconds() / 60)
        cost = self._tariff.price_per_minute.amount * minutes
        return Money(max(cost, self._tariff.min_price.amount))


# ===== 5. Репозитории (порты) =====

class ScooterRepository(Protocol):
    def get(self, scooter_id: ScooterId) -> Scooter: ...
    def save(self, scooter: Scooter) -> None: ...


class TripRepository(Protocol):
    def get(self, trip_id: TripId) -> Trip: ...
    def save(self, trip: Trip) -> None: ...


# ===== 6. Доменный сервис (затрагивает Scooter и Trip) =====

class StartTripService:
    def __init__(self, scooters: ScooterRepository, trips: TripRepository) -> None:
        self._scooters = scooters
        self._trips = trips

    def start(self, scooter_id: ScooterId, started_at: datetime, tariff: Tariff) -> Trip:
        scooter = self._scooters.get(scooter_id)
        scooter.rent()
        trip = Trip(TripId.new(), scooter.id, started_at, tariff)
        self._scooters.save(scooter)
        self._trips.save(trip)
        return trip


# ===== 7. In-memory база данных =====

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


# ===== 8. Демонстрация =====

if __name__ == "__main__":
    scooters, trips = InMemoryScooterRepository(), InMemoryTripRepository()
    service = StartTripService(scooters, trips)
    tariff = Tariff(Money(Decimal("7.5")), Money(Decimal(50)))
    t0 = datetime(2026, 10, 1, 12, 0)

    charged = Scooter(ScooterId.new(), BatteryLevel(85))
    low = Scooter(ScooterId.new(), BatteryLevel(10))
    for s in (charged, low):
        scooters.save(s)

    trip = service.start(charged.id, t0, tariff)
    print("1) Поездка начата, самокат:", scooters.get(charged.id).status.value)

    for text, scooter_id in (("2) Повторная аренда", charged.id), ("3) Заряд 10 %", low.id)):
        try:
            service.start(scooter_id, t0, tariff)
        except DomainError as e:
            print(f"{text} — отказ:", e)

    print("4) Поездка 12 мин 10 с, стоимость:", trip.finish(datetime(2026, 10, 1, 12, 12, 10)).amount, "руб.")

    try:
        trip.finish(datetime(2026, 10, 1, 12, 20))
    except DomainError as e:
        print("5) Повторное завершение — отказ:", e)

    try:
        BatteryLevel(150)
    except DomainError as e:
        print("6) Заряд 150 % — отказ:", e)