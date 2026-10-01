"""ЛР2. Проектирование доменной модели с помощью DDD — Прокат самокатов.

Доменный слой (разделы 1–6) использует только стандартную библиотеку Python.
Запуск:  python scooters.py
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Protocol
from uuid import UUID, uuid4


# =====================================================================
# 1. ДОМЕННЫЕ ИСКЛЮЧЕНИЯ — собственная иерархия
# =====================================================================

class DomainError(Exception):
    """Базовое исключение доменного слоя: операция нарушает правило предметной области."""


class InvalidValueObject(DomainError):
    """Объект-значение нельзя создать с такими данными (ошибка в конструкторе)."""


class DomainInvariantViolation(DomainError):
    """Операция над агрегатом нарушила бы его инвариант."""


class AggregateNotFound(DomainError):
    """Агрегат с таким идентификатором не найден в репозитории."""


# =====================================================================
# 2. ОБЪЕКТЫ-ЗНАЧЕНИЯ (frozen=True, проверка в __post_init__)
# =====================================================================

@dataclass(frozen=True)
class Money:
    """Денежная сумма в рублях (инвариант: не отрицательна)."""
    amount: Decimal
    currency: str = "RUB"

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise InvalidValueObject("Сумма должна быть Decimal")
        if self.amount < 0:
            raise InvalidValueObject(f"Сумма не может быть отрицательной: {self.amount}")
        if self.currency != "RUB":
            raise InvalidValueObject("Поддерживаются только рубли")

    @staticmethod
    def rub(value: str | int) -> Money:
        return Money(Decimal(str(value)))

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"


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
class UserId:
    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise InvalidValueObject("UserId должен быть UUID")

    @staticmethod
    def new() -> UserId:
        return UserId(uuid4())


@dataclass(frozen=True)
class BatteryLevel:
    """Уровень заряда в процентах (инвариант 3: от 0 до 100)."""
    percent: int

    def __post_init__(self) -> None:
        if not isinstance(self.percent, int) or isinstance(self.percent, bool):
            raise InvalidValueObject("Уровень заряда должен быть целым числом")
        if not 0 <= self.percent <= 100:
            raise InvalidValueObject(f"Уровень заряда должен быть от 0 до 100 %, получено {self.percent}")

    def is_below(self, other: BatteryLevel) -> bool:
        return self.percent < other.percent


@dataclass(frozen=True)
class Tariff:
    """Тариф: цена за минуту (> 0) и минимальная стоимость поездки (>= 0)."""
    price_per_minute: Money
    min_price: Money

    def __post_init__(self) -> None:
        if not isinstance(self.price_per_minute, Money) or not isinstance(self.min_price, Money):
            raise InvalidValueObject("Цены тарифа должны быть Money")
        if self.price_per_minute.amount <= 0:
            raise InvalidValueObject("Цена за минуту должна быть больше нуля")

    def cost_for(self, minutes: int) -> Money:
        """Стоимость = цена за минуту × минуты, но не меньше минимальной стоимости."""
        if minutes < 0:
            raise InvalidValueObject("Длительность не может быть отрицательной")
        raw = self.price_per_minute.amount * minutes
        return Money(max(raw, self.min_price.amount))


# =====================================================================
# 3. АГРЕГАТ Scooter (корень — Scooter)
# =====================================================================

class ScooterStatus(Enum):
    AVAILABLE = "свободен"
    RENTED = "арендован"
    MAINTENANCE = "на обслуживании"


class Scooter:
    MIN_BATTERY_TO_RENT = BatteryLevel(20)       # минимальный порог заряда для выдачи

    __slots__ = ("_id", "_status", "_battery")

    def __init__(self, scooter_id: ScooterId, battery: BatteryLevel) -> None:
        self._id = scooter_id
        self._battery = battery
        self._status = ScooterStatus.AVAILABLE

    @classmethod
    def register(cls, battery: BatteryLevel) -> Scooter:
        """Фабрика: новый самокат поступает в парк в состоянии «свободен»."""
        return cls(ScooterId.new(), battery)

    @property
    def id(self) -> ScooterId:
        return self._id

    @property
    def status(self) -> ScooterStatus:
        return self._status

    @property
    def battery(self) -> BatteryLevel:
        return self._battery

    def rent(self) -> None:
        """Инварианты 1 и 2: выдать можно только свободный самокат с достаточным зарядом."""
        if self._status is not ScooterStatus.AVAILABLE:
            raise DomainInvariantViolation(
                f"Самокат нельзя выдать: текущее состояние — «{self._status.value}»")
        if self._battery.is_below(self.MIN_BATTERY_TO_RENT):
            raise DomainInvariantViolation(
                f"Самокат нельзя выдать: заряд {self._battery.percent} % ниже порога "
                f"{self.MIN_BATTERY_TO_RENT.percent} %")
        self._status = ScooterStatus.RENTED

    def release(self, battery_left: BatteryLevel) -> None:
        """Возврат самоката после поездки с фиксацией оставшегося заряда."""
        if self._status is not ScooterStatus.RENTED:
            raise DomainInvariantViolation("Вернуть можно только арендованный самокат")
        self._battery = battery_left
        self._status = ScooterStatus.AVAILABLE

    def send_to_maintenance(self) -> None:
        """На обслуживание можно отправить только свободный самокат."""
        if self._status is not ScooterStatus.AVAILABLE:
            raise DomainInvariantViolation(
                f"На обслуживание можно отправить только свободный самокат, сейчас — «{self._status.value}»")
        self._status = ScooterStatus.MAINTENANCE

    def finish_maintenance(self, battery: BatteryLevel) -> None:
        if self._status is not ScooterStatus.MAINTENANCE:
            raise DomainInvariantViolation("Самокат не находится на обслуживании")
        self._battery = battery
        self._status = ScooterStatus.AVAILABLE

# =====================================================================
# 4. АГРЕГАТ Trip (корень — Trip; связь со Scooter только по scooter_id)
# =====================================================================

class Trip:
    __slots__ = ("_id", "_scooter_id", "_user_id", "_started_at", "_finished_at", "_tariff", "_cost")

    def __init__(self, trip_id: TripId, scooter_id: ScooterId, user_id: UserId,
                 started_at: datetime, tariff: Tariff) -> None:
        self._id = trip_id
        self._scooter_id = scooter_id      # связь с агрегатом Scooter — только через идентификатор
        self._user_id = user_id
        self._started_at = started_at
        self._tariff = tariff              # копия тарифа на момент старта
        self._finished_at: datetime | None = None
        self._cost: Money | None = None

    @classmethod
    def start(cls, scooter_id: ScooterId, user_id: UserId,
              started_at: datetime, tariff: Tariff) -> Trip:
        """Фабрика: начать новую поездку."""
        return cls(TripId.new(), scooter_id, user_id, started_at, tariff)

    @property
    def id(self) -> TripId:
        return self._id

    @property
    def scooter_id(self) -> ScooterId:
        return self._scooter_id

    def finish(self, finished_at: datetime) -> Money:
        """Инварианты 4, 5, 6: нельзя завершить дважды, раньше начала;
        стоимость рассчитывается по тарифу одновременно с фиксацией времени окончания."""
        if self._finished_at is not None:
            raise DomainInvariantViolation("Поездка уже завершена")
        if finished_at < self._started_at:
            raise DomainInvariantViolation("Поездка не может быть завершена раньше, чем начата")
        minutes = math.ceil((finished_at - self._started_at).total_seconds() / 60)  # вверх
        self._finished_at = finished_at
        self._cost = self._tariff.cost_for(minutes)
        return self._cost

# =====================================================================
# 5. ПОРТЫ — репозитории как Protocol
# =====================================================================

class ScooterRepository(Protocol):
    def get(self, scooter_id: ScooterId) -> Scooter: ...
    def save(self, scooter: Scooter) -> None: ...


class TripRepository(Protocol):
    def get(self, trip_id: TripId) -> Trip: ...
    def save(self, trip: Trip) -> None: ...


# =====================================================================
# 6. ДОМЕННЫЕ СЕРВИСЫ — затрагивают Scooter и Trip
# =====================================================================

class StartTripService:
    """Начать поездку: арендовать самокат (Scooter) + создать поездку (Trip)."""

    def __init__(self, scooters: ScooterRepository, trips: TripRepository) -> None:
        self._scooters = scooters
        self._trips = trips

    def start(self, scooter_id: ScooterId, user_id: UserId,
              started_at: datetime, tariff: Tariff) -> Trip:
        scooter = self._scooters.get(scooter_id)
        scooter.rent()                                   # инварианты 1–2 проверяет сам Scooter
        trip = Trip.start(scooter.id, user_id, started_at, tariff)
        self._scooters.save(scooter)
        self._trips.save(trip)
        return trip


class FinishTripService:
    """Завершить поездку: закрыть Trip с расчётом стоимости + вернуть Scooter в «свободен»."""

    def __init__(self, scooters: ScooterRepository, trips: TripRepository) -> None:
        self._scooters = scooters
        self._trips = trips

    def finish(self, trip_id: TripId, finished_at: datetime, battery_left: BatteryLevel) -> Money:
        trip = self._trips.get(trip_id)
        scooter = self._scooters.get(trip.scooter_id)    # загрузка второго агрегата по ID
        cost = trip.finish(finished_at)                  # инварианты 4–6 проверяет сам Trip
        scooter.release(battery_left)
        self._trips.save(trip)
        self._scooters.save(scooter)
        return cost


# =====================================================================
# 7. АДАПТЕРЫ — in-memory репозитории (база данных — словари)
# =====================================================================

# Не наследуются от Protocol: достаточно иметь методы с нужными именами.
# Хранят копии агрегатов: изменения попадают в «базу» только через save().

class InMemoryScooterRepository:
    def __init__(self) -> None:
        self._items: dict[ScooterId, Scooter] = {}

    def get(self, scooter_id: ScooterId) -> Scooter:
        if scooter_id not in self._items:
            raise AggregateNotFound(f"Самокат {scooter_id.value} не найден")
        return copy.deepcopy(self._items[scooter_id])

    def save(self, scooter: Scooter) -> None:
        self._items[scooter.id] = copy.deepcopy(scooter)


class InMemoryTripRepository:
    def __init__(self) -> None:
        self._items: dict[TripId, Trip] = {}

    def get(self, trip_id: TripId) -> Trip:
        if trip_id not in self._items:
            raise AggregateNotFound(f"Поездка {trip_id.value} не найдена")
        return copy.deepcopy(self._items[trip_id])

    def save(self, trip: Trip) -> None:
        self._items[trip.id] = copy.deepcopy(trip)


# =====================================================================
# 8. ДЕМОНСТРАЦИЯ
# =====================================================================

def attempt(description: str, action) -> None:
    """Выполнить действие, которое должно нарушить правило, и показать отказ."""
    print(description)
    try:
        action()
        print("    Выполнено")
    except DomainError as e:
        print(f"    Отказ ({type(e).__name__}): {e}")


def show_scooter(scooter: Scooter) -> None:
    print(f"    Самокат: {scooter.status.value}, заряд {scooter.battery.percent} %")


def demo_scooters() -> None:
    scooters = InMemoryScooterRepository()
    trips = InMemoryTripRepository()
    start_service = StartTripService(scooters, trips)
    finish_service = FinishTripService(scooters, trips)

    tariff = Tariff(price_per_minute=Money.rub("7.50"), min_price=Money.rub(50))
    charged = Scooter.register(BatteryLevel(85))
    low = Scooter.register(BatteryLevel(10))
    scooters.save(charged)
    scooters.save(low)

    print("1) Начинаем поездку на самокате с зарядом 85 %")
    trip = start_service.start(charged.id, UserId.new(), datetime(2026, 10, 1, 12, 0), tariff)
    show_scooter(scooters.get(charged.id))

    attempt("2) Другой пользователь пытается взять тот же самокат",
            lambda: start_service.start(charged.id, UserId.new(), datetime(2026, 10, 1, 12, 5), tariff))
    attempt("3) Пытаемся взять самокат с зарядом 10 %",
            lambda: start_service.start(low.id, UserId.new(), datetime(2026, 10, 1, 12, 5), tariff))

    print("4) Отправляем разряженный самокат на обслуживание")
    scooter = scooters.get(low.id)
    scooter.send_to_maintenance()
    scooters.save(scooter)
    show_scooter(scooters.get(low.id))

    attempt("5) Пытаемся взять самокат, который на обслуживании",
            lambda: start_service.start(low.id, UserId.new(), datetime(2026, 10, 1, 12, 10), tariff))

    print("6) Обслуживание закончено, самокат заряжен до 100 %")
    scooter = scooters.get(low.id)
    scooter.finish_maintenance(BatteryLevel(100))
    scooters.save(scooter)
    show_scooter(scooters.get(low.id))

    attempt("7) Пытаемся завершить первую поездку раньше её начала",
            lambda: finish_service.finish(trip.id, datetime(2026, 10, 1, 11, 0), BatteryLevel(70)))

    print("8) Завершаем первую поездку через 12 мин 10 с, после поездки осталось 70 % заряда")
    cost = finish_service.finish(trip.id, datetime(2026, 10, 1, 12, 12, 10), BatteryLevel(70))
    print(f"    Стоимость: {cost} (13 мин × 7.50 ₽)")
    show_scooter(scooters.get(charged.id))

    attempt("9) Пытаемся завершить ту же поездку повторно",
            lambda: finish_service.finish(trip.id, datetime(2026, 10, 1, 12, 20), BatteryLevel(70)))
    attempt("10) Создаём заряд 150 %",
            lambda: BatteryLevel(150))
    attempt("11) Создаём тариф с ценой 0 ₽ за минуту",
            lambda: Tariff(Money.rub(0), Money.rub(50)))


if __name__ == "__main__":
    demo_scooters()