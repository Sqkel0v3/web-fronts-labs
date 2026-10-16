from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from scooters import (
    PREAUTH_AMOUNT,
    BookingService,
    Client,
    ClientId,
    ClientRepository,
    GeoPoint,
    InvalidValueObject,
    Money,
    ParkingZone,
    Scooter,
    ScooterId,
    ScooterRepository,
    Tariff,
    TransitionNotAllowed,
    Trip,
    TripId,
    TripRepository,
)


class GatewayUnresolved(Exception):
    def __init__(self, gateway: str):
        self.gateway = gateway
        super().__init__(f"Шлюз «{gateway}»: должно выполняться ровно одно условие")


class Clock(Protocol):
    def now(self) -> datetime: ...


class PaymentGateway(Protocol):
    def authorize(self, client_id: ClientId, amount: Money) -> bool: ...
    def charge(self, client_id: ClientId, amount: Money) -> bool: ...


@dataclass(frozen=True)
class ClientCommand:
    value: str

    def __post_init__(self):
        if self.value not in ("пауза", "завершить"):
            raise InvalidValueObject("Команда клиента: «пауза» или «завершить»")


def resolve_gateway(name: str, outcomes: dict) -> str:
    chosen = [outcome for outcome, condition in outcomes.items() if condition]
    if len(chosen) != 1:
        raise GatewayUnresolved(name)
    return chosen[0]


def client_has_debt(client: Client) -> bool:
    return client.has_debt()


def payment_authorized(trip: Trip) -> bool:
    return trip.authorized is True


def command_is_pause(command: ClientCommand) -> bool:
    return command.value == "пауза"


def command_is_finish(command: ClientCommand) -> bool:
    return command.value == "завершить"


def scooter_in_allowed_zone(location: GeoPoint, zones: list) -> bool:
    return any(zone.contains(location) for zone in zones)


class RentalProcess:
    def __init__(
        self,
        scooters: ScooterRepository,
        trips: TripRepository,
        clients: ClientRepository,
        payments: PaymentGateway,
        clock: Clock,
        tariff: Tariff,
        zones: list,
    ):
        self._scooters = scooters
        self._trips = trips
        self._clients = clients
        self._payments = payments
        self._clock = clock
        self._tariff = tariff
        self._zones = zones
        self._booking = BookingService()

    @staticmethod
    def _require_event(trip: Trip, event: str):
        if event not in trip.allowed_events:
            raise TransitionNotAllowed(trip.status, event)

    def get_trip(self, trip_id: TripId) -> Trip:
        return self._trips.get(trip_id)

    def book_scooter(self, scooter_id: ScooterId, client_id: ClientId) -> Trip:
        scooter = self._scooters.get(scooter_id)
        client = self._clients.get(client_id)
        trip = self._booking.book(scooter, client, self._tariff, self._clock.now())
        self._scooters.save(scooter)
        self._trips.save(trip)
        return trip

    def receive_trip_start_request(self, trip_id: TripId) -> Trip:
        trip = self._trips.get(trip_id)
        self._require_event(trip, "start")
        client = self._clients.get(trip.client_id)
        outcome = resolve_gateway(
            "Есть задолженность?",
            {"да": client_has_debt(client), "нет": not client_has_debt(client)},
        )
        if outcome == "да":
            return self._not_started(trip, "задолженность")
        self.authorize_payment(trip)
        outcome = resolve_gateway(
            "Платёж авторизован?",
            {"да": payment_authorized(trip), "нет": not payment_authorized(trip)},
        )
        if outcome == "нет":
            return self._not_started(trip, "платёж не авторизован")
        scooter = self._scooters.get(trip.scooter_id)
        self.unlock_lock(trip, scooter)
        self.start_billing(trip)
        trip.start(self._clock.now())
        self._scooters.save(scooter)
        self._trips.save(trip)
        return trip

    def authorize_payment(self, trip: Trip):
        approved = self._payments.authorize(trip.client_id, PREAUTH_AMOUNT)
        trip.record_authorization(approved, self._clock.now())

    def unlock_lock(self, trip: Trip, scooter: Scooter):
        scooter.rent()
        trip.mark_lock_opened()

    def start_billing(self, trip: Trip):
        trip.mark_billing_started()

    def _not_started(self, trip: Trip, reason: str) -> Trip:
        trip.reject(reason, self._clock.now())
        scooter = self._scooters.get(trip.scooter_id)
        scooter.release()
        self._scooters.save(scooter)
        self._trips.save(trip)
        return trip

    def receive_client_command(
        self, trip_id: TripId, command: ClientCommand, location: GeoPoint = None
    ) -> Trip:
        trip = self._trips.get(trip_id)
        outcome = resolve_gateway(
            "Команда клиента?",
            {"пауза": command_is_pause(command), "завершить": command_is_finish(command)},
        )
        if outcome == "пауза":
            self.pause_trip(trip)
        else:
            self._require_event(trip, "finish")
            if location is None:
                raise InvalidValueObject("Для завершения нужны координаты самоката")
            in_zone = scooter_in_allowed_zone(location, self._zones)
            outcome = resolve_gateway(
                "Самокат в разрешённой зоне?", {"да": in_zone, "нет": not in_zone}
            )
            if outcome == "да":
                trip.finish(self._clock.now(), in_zone)
        self._trips.save(trip)
        return trip

    def pause_trip(self, trip: Trip):
        trip.pause(self._clock.now())

    def receive_resume_command(self, trip_id: TripId) -> Trip:
        trip = self._trips.get(trip_id)
        trip.resume(self._clock.now())
        self._trips.save(trip)
        return trip

    def receive_photo(self, trip_id: TripId, photo_id: str) -> Trip:
        trip = self._trips.get(trip_id)
        self._require_event(trip, "pay")
        trip.attach_photo(photo_id, self._clock.now())
        self.charge_trip_cost(trip)
        self._trips.save(trip)
        return trip

    def charge_trip_cost(self, trip: Trip):
        charged = self._payments.charge(trip.client_id, trip.cost)
        outcome = resolve_gateway("Списание прошло?", {"да": charged, "нет": not charged})
        if outcome == "да":
            trip.pay(self._clock.now())
        else:
            self.record_debt_and_block(trip)
        scooter = self._scooters.get(trip.scooter_id)
        scooter.release()
        self._scooters.save(scooter)

    def record_debt_and_block(self, trip: Trip):
        client = self._clients.get(trip.client_id)
        client.add_debt(trip.cost)
        trip.fail_payment(self._clock.now())
        self._clients.save(client)

    def contact_client(self, trip_id: TripId, result: str) -> Trip:
        trip = self._trips.get(trip_id)
        trip.record_operator_contact(result, self._clock.now())
        self._trips.save(trip)
        return trip

    def on_tick(self) -> list:
        now = self._clock.now()
        changed = []
        for trip in self._trips.all():
            if "expire_reservation" in trip.allowed_events and trip.on_reservation_expired(now):
                scooter = self._scooters.get(trip.scooter_id)
                scooter.release()
                self._scooters.save(scooter)
                changed.append(trip)
            elif trip.on_long_ride(now):
                changed.append(trip)
            self._trips.save(trip)
        return changed
