import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Protocol
from uuid import UUID, uuid4

from trip_states import (
    AggregateNotFound,
    DomainError,
    DomainInvariantViolation,
    Finished,
    InRide,
    InvalidValueObject,
    Paused,
    Reserved,
    TransitionNotAllowed,
    TripState,
)

RESERVATION_TIMEOUT = timedelta(minutes=10)
LONG_RIDE = timedelta(hours=12)


@dataclass(frozen=True)
class ScooterId:
    value: UUID

    def __post_init__(self):
        if not isinstance(self.value, UUID):
            raise InvalidValueObject("ScooterId должен быть UUID")

    @staticmethod
    def new() -> "ScooterId":
        return ScooterId(uuid4())


@dataclass(frozen=True)
class TripId:
    value: UUID

    def __post_init__(self):
        if not isinstance(self.value, UUID):
            raise InvalidValueObject("TripId должен быть UUID")

    @staticmethod
    def new() -> "TripId":
        return TripId(uuid4())


@dataclass(frozen=True)
class ClientId:
    value: UUID

    def __post_init__(self):
        if not isinstance(self.value, UUID):
            raise InvalidValueObject("ClientId должен быть UUID")

    @staticmethod
    def new() -> "ClientId":
        return ClientId(uuid4())


@dataclass(frozen=True)
class BatteryLevel:
    percent: int

    def __post_init__(self):
        if not 0 <= self.percent <= 100:
            raise InvalidValueObject("Заряд должен быть от 0 до 100 %")


@dataclass(frozen=True)
class Money:
    amount: Decimal

    def __post_init__(self):
        if not isinstance(self.amount, Decimal):
            raise InvalidValueObject("Сумма должна быть Decimal")
        if self.amount < 0:
            raise InvalidValueObject("Сумма не может быть отрицательной")

    def __add__(self, other: "Money") -> "Money":
        return Money(self.amount + other.amount)


PREAUTH_AMOUNT = Money(Decimal(300))


@dataclass(frozen=True)
class Tariff:
    price_per_minute: Money
    min_price: Money
    pause_price_per_minute: Money

    def __post_init__(self):
        if self.price_per_minute.amount <= 0:
            raise InvalidValueObject("Цена за минуту должна быть больше нуля")
        if not 0 < self.pause_price_per_minute.amount < self.price_per_minute.amount:
            raise InvalidValueObject(
                "Цена минуты паузы должна быть больше нуля и меньше обычной цены"
            )


@dataclass(frozen=True)
class GeoPoint:
    lat: float
    lon: float

    def __post_init__(self):
        if not (-90 <= self.lat <= 90 and -180 <= self.lon <= 180):
            raise InvalidValueObject("Неверные координаты")


@dataclass(frozen=True)
class ParkingZone:
    south: float
    west: float
    north: float
    east: float

    def __post_init__(self):
        if self.south >= self.north or self.west >= self.east:
            raise InvalidValueObject("Неверные границы зоны парковки")

    def contains(self, point: GeoPoint) -> bool:
        return self.south <= point.lat <= self.north and self.west <= point.lon <= self.east


class ScooterStatus(Enum):
    AVAILABLE = "свободен"
    RESERVED = "забронирован"
    RENTED = "арендован"
    MAINTENANCE = "на обслуживании"


class Scooter:
    MIN_BATTERY = 20
    __slots__ = ("_id", "_battery", "_status")

    def __init__(
        self,
        scooter_id: ScooterId,
        battery: BatteryLevel,
        status: ScooterStatus = ScooterStatus.AVAILABLE,
    ):
        self._id = scooter_id
        self._battery = battery
        self._status = status

    @property
    def id(self) -> ScooterId:
        return self._id

    @property
    def status(self) -> ScooterStatus:
        return self._status

    def reserve(self):
        if self._status is not ScooterStatus.AVAILABLE:
            raise DomainInvariantViolation(f"Самокат {self._status.value}")
        if self._battery.percent < self.MIN_BATTERY:
            raise DomainInvariantViolation(f"Заряд ниже {self.MIN_BATTERY} %")
        self._status = ScooterStatus.RESERVED

    def rent(self):
        if self._status is not ScooterStatus.RESERVED:
            raise DomainInvariantViolation("Разблокировать можно только забронированный самокат")
        self._status = ScooterStatus.RENTED

    def release(self):
        if self._status not in (ScooterStatus.RESERVED, ScooterStatus.RENTED):
            raise DomainInvariantViolation(
                "Освободить можно только забронированный или арендованный самокат"
            )
        self._status = ScooterStatus.AVAILABLE


class Client:
    __slots__ = ("_id", "_debt", "_blocked")

    def __init__(self, client_id: ClientId, debt: Money = Money(Decimal(0))):
        self._id = client_id
        self._debt = debt
        self._blocked = debt.amount > 0

    @property
    def id(self) -> ClientId:
        return self._id

    @property
    def debt(self) -> Money:
        return self._debt

    @property
    def blocked(self) -> bool:
        return self._blocked

    def has_debt(self) -> bool:
        return self._debt.amount > 0

    def add_debt(self, amount: Money):
        if amount.amount <= 0:
            raise DomainInvariantViolation("Долг должен быть больше нуля")
        self._debt = self._debt + amount
        self._blocked = True


@dataclass(frozen=True)
class DomainEvent:
    trip_id: TripId
    occurred_at: datetime


@dataclass(frozen=True)
class TripReserved(DomainEvent):
    scooter_id: ScooterId


@dataclass(frozen=True)
class PaymentAuthorized(DomainEvent):
    amount: Money


@dataclass(frozen=True)
class PaymentAuthorizationDeclined(DomainEvent):
    amount: Money


@dataclass(frozen=True)
class TripRejected(DomainEvent):
    reason: str


@dataclass(frozen=True)
class ReservationTimedOut(DomainEvent):
    pass


@dataclass(frozen=True)
class TripStarted(DomainEvent):
    pass


@dataclass(frozen=True)
class TripPaused(DomainEvent):
    pass


@dataclass(frozen=True)
class TripResumed(DomainEvent):
    pass


@dataclass(frozen=True)
class TripFinished(DomainEvent):
    cost: Money


@dataclass(frozen=True)
class PhotoReceived(DomainEvent):
    photo_id: str


@dataclass(frozen=True)
class TripPaid(DomainEvent):
    amount: Money


@dataclass(frozen=True)
class PaymentFailed(DomainEvent):
    amount: Money


@dataclass(frozen=True)
class LongRideDetected(DomainEvent):
    pass


@dataclass(frozen=True)
class OperatorContactedClient(DomainEvent):
    result: str


class Trip:
    def __init__(
        self,
        trip_id: TripId,
        scooter_id: ScooterId,
        client_id: ClientId,
        tariff: Tariff,
        reserved_at: datetime,
    ):
        self._id = trip_id
        self._scooter_id = scooter_id
        self._client_id = client_id
        self._tariff = tariff
        self._reserved_at = reserved_at
        self._started_at = None
        self._finished_at = None
        self._paused_at = None
        self._paused_total = timedelta(0)
        self._lock_opened = False
        self._billing_started = False
        self._authorized = None
        self._photo_id = None
        self._cost = None
        self._long_ride_notified = False
        self._state: TripState = Reserved()
        self._events: list = [TripReserved(trip_id, reserved_at, scooter_id)]

    @property
    def id(self) -> TripId:
        return self._id

    @property
    def scooter_id(self) -> ScooterId:
        return self._scooter_id

    @property
    def client_id(self) -> ClientId:
        return self._client_id

    @property
    def status(self) -> str:
        return self._state.name

    @property
    def allowed_events(self) -> frozenset:
        return self._state.allowed

    @property
    def events(self) -> tuple:
        return tuple(self._events)

    @property
    def lock_opened(self) -> bool:
        return self._lock_opened

    @property
    def billing_started(self) -> bool:
        return self._billing_started

    @property
    def authorized(self):
        return self._authorized

    @property
    def photo_id(self):
        return self._photo_id

    @property
    def cost(self):
        return self._cost

    def _require_reserved(self, action: str):
        if not isinstance(self._state, Reserved):
            raise DomainInvariantViolation(f"{action} возможно только для забронированной поездки")

    def record_authorization(self, approved: bool, now: datetime):
        self._require_reserved("Авторизация платежа")
        self._authorized = approved
        event = PaymentAuthorized if approved else PaymentAuthorizationDeclined
        self._events.append(event(self._id, now, PREAUTH_AMOUNT))

    def mark_lock_opened(self):
        self._require_reserved("Разблокировка замка")
        self._lock_opened = True

    def mark_billing_started(self):
        self._require_reserved("Запуск тарификации")
        self._billing_started = True

    def start(self, now: datetime):
        new_state = self._state.start(self)
        self._started_at = now
        self._state = new_state
        self._events.append(TripStarted(self._id, now))

    def reject(self, reason: str, now: datetime):
        new_state = self._state.reject(self)
        self._state = new_state
        self._events.append(TripRejected(self._id, now, reason))

    def on_reservation_expired(self, now: datetime) -> bool:
        if now - self._reserved_at < RESERVATION_TIMEOUT:
            return False
        new_state = self._state.expire_reservation(self)
        self._state = new_state
        self._events.append(ReservationTimedOut(self._id, now))
        return True

    def pause(self, now: datetime):
        new_state = self._state.pause(self)
        self._paused_at = now
        self._state = new_state
        self._events.append(TripPaused(self._id, now))

    def resume(self, now: datetime):
        new_state = self._state.resume(self)
        if now < self._paused_at:
            raise DomainInvariantViolation("Пауза не может закончиться раньше начала")
        self._paused_total += now - self._paused_at
        self._paused_at = None
        self._state = new_state
        self._events.append(TripResumed(self._id, now))

    def finish(self, now: datetime, in_zone: bool) -> Money:
        new_state = self._state.finish(self, in_zone)
        if now < self._started_at:
            raise DomainInvariantViolation("Поездка не может завершиться раньше начала")
        self._finished_at = now
        self._cost = self._calculate_cost()
        self._state = new_state
        self._events.append(TripFinished(self._id, now, self._cost))
        return self._cost

    def _calculate_cost(self) -> Money:
        ride_seconds = (self._finished_at - self._started_at - self._paused_total).total_seconds()
        ride_minutes = math.ceil(ride_seconds / 60)
        pause_minutes = math.ceil(self._paused_total.total_seconds() / 60)
        cost = (
            self._tariff.price_per_minute.amount * ride_minutes
            + self._tariff.pause_price_per_minute.amount * pause_minutes
        )
        return Money(max(cost, self._tariff.min_price.amount))

    def attach_photo(self, photo_id: str, now: datetime):
        if not isinstance(self._state, Finished):
            raise DomainInvariantViolation("Фото принимается только после завершения поездки")
        if not photo_id:
            raise InvalidValueObject("Пустой идентификатор фото")
        self._photo_id = photo_id
        self._events.append(PhotoReceived(self._id, now, photo_id))

    def pay(self, now: datetime):
        new_state = self._state.pay(self)
        self._state = new_state
        self._events.append(TripPaid(self._id, now, self._cost))

    def fail_payment(self, now: datetime):
        new_state = self._state.fail_payment(self)
        self._state = new_state
        self._events.append(PaymentFailed(self._id, now, self._cost))

    def on_long_ride(self, now: datetime) -> bool:
        if not isinstance(self._state, (InRide, Paused)) or self._long_ride_notified:
            return False
        if now - self._started_at < LONG_RIDE:
            return False
        self._long_ride_notified = True
        self._events.append(LongRideDetected(self._id, now))
        return True

    def record_operator_contact(self, result: str, now: datetime):
        if not self._long_ride_notified:
            raise DomainInvariantViolation(
                "Оператор связывается с клиентом только после уведомления о долгой поездке"
            )
        self._events.append(OperatorContactedClient(self._id, now, result))


class BookingService:
    def book(self, scooter: Scooter, client: Client, tariff: Tariff, now: datetime) -> Trip:
        scooter.reserve()
        return Trip(TripId.new(), scooter.id, client.id, tariff, now)


class ScooterRepository(Protocol):
    def get(self, scooter_id: ScooterId) -> Scooter: ...
    def save(self, scooter: Scooter): ...


class TripRepository(Protocol):
    def get(self, trip_id: TripId) -> Trip: ...
    def save(self, trip: Trip): ...
    def all(self) -> list: ...


class ClientRepository(Protocol):
    def get(self, client_id: ClientId) -> Client: ...
    def save(self, client: Client): ...
