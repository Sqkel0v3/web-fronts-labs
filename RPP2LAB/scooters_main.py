"""Демонстрация работы доменной модели.  Запуск: python scooters_main.py"""
from datetime import datetime
from decimal import Decimal

from scooters import BatteryLevel, DomainError, Money, Scooter, ScooterId, StartTripService, Tariff
from scooters_repository import InMemoryScooterRepository, InMemoryTripRepository


def main() -> None:
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


if __name__ == "__main__":
    main()