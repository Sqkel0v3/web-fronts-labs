"""Веб-адаптер: HTTP-маршруты к прикладному сервису RentalProcess. Flask используется только здесь."""

import logging
import os
from dataclasses import fields
from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from adapters import (
    ClockMovedBack,
    InMemoryClientRepository,
    InMemoryPaymentGateway,
    InMemoryScooterRepository,
    InMemoryTripRepository,
    ShiftedClock,
)
from rental_process import ClientCommand, GatewayUnresolved, RentalProcess
from scooters import (
    AggregateNotFound,
    BatteryLevel,
    Client,
    ClientId,
    DomainInvariantViolation,
    GeoPoint,
    InvalidValueObject,
    Money,
    ParkingZone,
    Scooter,
    ScooterId,
    Tariff,
    TransitionNotAllowed,
    Trip,
    TripId,
)

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())
log = logging.getLogger("scooters")

# --- сборка приложения: сервис, часы и репозитории создаются один раз при запуске ---
clock = ShiftedClock()
scooters, trips, clients = (
    InMemoryScooterRepository(),
    InMemoryTripRepository(),
    InMemoryClientRepository(),
)
payments = InMemoryPaymentGateway()
tariff = Tariff(Money(Decimal("7.5")), Money(Decimal(50)), Money(Decimal(2)))
process = RentalProcess(
    scooters, trips, clients, payments, clock, tariff, [ParkingZone(54.0, 82.0, 55.0, 83.0)]
)

# начальные данные: 3 самоката, 3 клиента (обычный, с долгом, с отказом в списании)
for n, battery in ((1, 90), (2, 85), (3, 15)):
    scooters.save(Scooter(ScooterId(UUID(int=n)), BatteryLevel(battery)))
clients.save(Client(ClientId(UUID(int=101))))
clients.save(Client(ClientId(UUID(int=102)), debt=Money(Decimal(200))))
clients.save(Client(ClientId(UUID(int=103))))
payments.decline_charge_for(ClientId(UUID(int=103)))

app = Flask(__name__)
app.json.ensure_ascii = False


# --- разбор входных данных ---
def json_body() -> dict:
    data = request.get_json(silent=True)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise InvalidValueObject("Тело запроса должно быть JSON-объектом")
    return data


def required(data: dict, key: str):
    if key not in data:
        raise InvalidValueObject(f"Отсутствует поле {key}")
    return data[key]


def parse_uuid(value) -> UUID:
    try:
        return UUID(str(value))
    except ValueError:
        raise InvalidValueObject(f"Некорректный идентификатор: {value}") from None


def parse_time(value) -> datetime:
    if not isinstance(value, str):
        raise InvalidValueObject("Время должно быть строкой ISO 8601")
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        raise InvalidValueObject("Некорректное время ISO 8601") from None
    if moment.tzinfo is not None:
        moment = moment.astimezone().replace(tzinfo=None)
    return moment


def parse_number(data: dict, key: str) -> float:
    value = required(data, key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidValueObject(f"Поле {key} должно быть числом")
    return float(value)


# --- представление поездки ---
def plain(value):
    if isinstance(value, (ScooterId, TripId, ClientId)):
        return str(value.value)
    if isinstance(value, Money):
        return str(value.amount)
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, (Decimal, UUID, Enum)):
        return str(value)
    return value


def trip_view(trip: Trip, full: bool = False) -> dict:
    """Ответ бизнес-операции: состояние и допустимые события; GET добавляет данные и журнал."""
    view = {
        "id": str(trip.id.value),
        "status": trip.status,
        "allowed_events": sorted(trip.allowed_events),
    }
    if trip.cost:
        view["cost"] = plain(trip.cost)
    if full:
        view["scooter_id"] = str(trip.scooter_id.value)
        view["client_id"] = str(trip.client_id.value)
        view["events"] = [
            {"type": type(e).__name__, **{f.name: plain(getattr(e, f.name)) for f in fields(e)}}
            for e in trip.events
        ]
    return view


def trip_id(value) -> TripId:
    return TripId(parse_uuid(value))


# --- маршруты бизнес-операций (задачи схемы BPMN) ---
@app.post("/trips")
def book_scooter():
    data = json_body()
    scooter_id = ScooterId(parse_uuid(required(data, "scooter_id")))
    client_id = ClientId(parse_uuid(required(data, "client_id")))
    trip = process.book_scooter(scooter_id, client_id)
    log.info("Забронирован самокат %s, поездка %s", scooter_id.value, trip.id.value)
    return jsonify(trip_view(trip)), 201


@app.post("/trips/<tid>/start")
def receive_trip_start_request(tid):
    return jsonify(trip_view(process.receive_trip_start_request(trip_id(tid))))


@app.post("/trips/<tid>/command")
def receive_client_command(tid):
    data = json_body()
    command = ClientCommand(required(data, "command"))
    location = None
    if "lat" in data or "lon" in data:
        location = GeoPoint(parse_number(data, "lat"), parse_number(data, "lon"))
    return jsonify(trip_view(process.receive_client_command(trip_id(tid), command, location)))


@app.post("/trips/<tid>/resume")
def receive_resume_command(tid):
    return jsonify(trip_view(process.receive_resume_command(trip_id(tid))))


@app.post("/trips/<tid>/photo")
def receive_photo(tid):
    photo_id = required(json_body(), "photo_id")
    if not isinstance(photo_id, str):
        raise InvalidValueObject("Поле photo_id должно быть строкой")
    return jsonify(trip_view(process.receive_photo(trip_id(tid), photo_id)))


@app.post("/trips/<tid>/operator-contact")
def contact_client(tid):
    result = required(json_body(), "result")
    if not isinstance(result, str) or not result:
        raise InvalidValueObject("Поле result должно быть непустой строкой")
    return jsonify(trip_view(process.contact_client(trip_id(tid), result)))


@app.get("/trips/<tid>")
def get_trip(tid):
    return jsonify(trip_view(process.get_trip(trip_id(tid)), full=True))


# --- служебные маршруты ---
@app.post("/internal/tick")
def tick():
    data = json_body()
    if "now" in data:
        clock.move_to(parse_time(data["now"]))
    changed = process.on_tick()
    return jsonify(
        {
            "now": clock.now().isoformat(timespec="seconds"),
            "changed": [{"id": str(t.id.value), "status": t.status} for t in changed],
        }
    )


@app.get("/health")
def health():
    return jsonify({"status": "ok", "now": clock.now().isoformat(timespec="seconds")})


# --- обработка ошибок: {"error": "код", "message": "описание"} ---
def error(exc: Exception, code: int):
    return jsonify({"error": type(exc).__name__, "message": str(exc)}), code


@app.errorhandler(TransitionNotAllowed)
def on_transition(exc):
    return error(exc, 409)


@app.errorhandler(DomainInvariantViolation)
@app.errorhandler(InvalidValueObject)
@app.errorhandler(ClockMovedBack)
def on_invalid(exc):
    return error(exc, 422)


@app.errorhandler(AggregateNotFound)
def on_not_found(exc):
    return error(exc, 404)


@app.errorhandler(GatewayUnresolved)
def on_gateway(exc):
    log.error("Неразрешённый шлюз: %s", exc)
    return error(exc, 500)


@app.errorhandler(HTTPException)
def on_http(exc):
    return jsonify({"error": exc.name, "message": exc.description}), exc.code


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
