"""ЛР2. Доменный слой «Прокат самокатов» (DDD): исключения, объекты-значения,
агрегаты, порты (Protocol) и доменный сервис. Только стандартная библиотека Python."""
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