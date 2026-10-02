from datetime import datetime
from decimal import Decimal

from scooters import BatteryLevel, DomainError, Money, Scooter, ScooterId, StartTripService, Tariff
from scooters_repository import InMemoryScooterRepository, InMemoryTripRepository


def main():
    scooters = InMemoryScooterRepository()
    trips = InMemoryTripRepository()
    service = StartTripService(scooters, trips)
    tariff = Tariff(Money(Decimal("7.5")), Money(Decimal(50)))
    start_time = datetime(2026, 10, 1, 12, 0)

    charged = Scooter(ScooterId.new(), BatteryLevel(85))
    low = Scooter(ScooterId.new(), BatteryLevel(10))
    scooters.save(charged)
    scooters.save(low)

    trip = service.start(charged.id, start_time, tariff)
    print("1) Поездка начата, самокат:", scooters.get(charged.id).status.value)

    try:
        service.start(charged.id, start_time, tariff)
    except DomainError as e:
        print("2) Повторная аренда — отказ:", e)

    try:
        service.start(low.id, start_time, tariff)
    except DomainError as e:
        print("3) Заряд 10 % — отказ:", e)

    cost = trip.finish(datetime(2026, 10, 1, 12, 12, 10))
    print("4) Поездка 12 мин 10 с, стоимость:", cost.amount, "руб.")

    try:
        trip.finish(datetime(2026, 10, 1, 12, 20))
    except DomainError as e:
        print("5) Повторное завершение — отказ:", e)

    try:
        BatteryLevel(150)
    except DomainError as e:
        print("6) Заряд 150 % — отказ:", e)


if __name__ == "__main__":
    main()