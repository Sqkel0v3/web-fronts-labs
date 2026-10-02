"""Тесты для scooters.py.  Запуск: python -m unittest test_scooters -v"""
import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from scooters import (BatteryLevel, DomainInvariantViolation, InvalidValueObject, Money,
                      Scooter, ScooterId, ScooterStatus, StartTripService, Tariff, Trip, TripId)
from scooters_repository import InMemoryScooterRepository, InMemoryTripRepository

T0 = datetime(2026, 10, 1, 12, 0)
TARIFF = Tariff(Money(Decimal(10)), Money(Decimal(50)))


class ScooterTests(unittest.TestCase):
    def make_trip(self):
        return Trip(TripId.new(), ScooterId.new(), T0, TARIFF)

    def test_invalid_battery(self):
        with self.assertRaises(InvalidValueObject):
            BatteryLevel(150)

    def test_invalid_tariff(self):
        with self.assertRaises(InvalidValueObject):
            Tariff(Money(Decimal(0)), Money(Decimal(50)))

    def test_cannot_rent_low_battery(self):
        with self.assertRaises(DomainInvariantViolation):
            Scooter(ScooterId.new(), BatteryLevel(19)).rent()

    def test_cannot_rent_twice(self):
        scooter = Scooter(ScooterId.new(), BatteryLevel(80))
        scooter.rent()
        with self.assertRaises(DomainInvariantViolation):
            scooter.rent()

    def test_cannot_rent_in_maintenance(self):
        with self.assertRaises(DomainInvariantViolation):
            Scooter(ScooterId.new(), BatteryLevel(80), ScooterStatus.MAINTENANCE).rent()

    def test_no_public_setter(self):
        with self.assertRaises(AttributeError):
            Scooter(ScooterId.new(), BatteryLevel(80)).status = ScooterStatus.RENTED

    def test_cost_with_min_price(self):
        self.assertEqual(self.make_trip().finish(T0 + timedelta(minutes=2)), Money(Decimal(50)))

    def test_cost_rounds_minutes_up(self):
        self.assertEqual(self.make_trip().finish(T0 + timedelta(minutes=6, seconds=1)), Money(Decimal(70)))

    def test_cannot_finish_before_start(self):
        with self.assertRaises(DomainInvariantViolation):
            self.make_trip().finish(T0 - timedelta(minutes=1))

    def test_cannot_finish_twice(self):
        trip = self.make_trip()
        trip.finish(T0 + timedelta(minutes=10))
        with self.assertRaises(DomainInvariantViolation):
            trip.finish(T0 + timedelta(minutes=20))

    def test_start_trip_service(self):
        scooters, trips = InMemoryScooterRepository(), InMemoryTripRepository()
        scooter = Scooter(ScooterId.new(), BatteryLevel(90))
        scooters.save(scooter)
        trip = StartTripService(scooters, trips).start(scooter.id, T0, TARIFF)
        self.assertIs(scooters.get(scooter.id).status, ScooterStatus.RENTED)
        self.assertIs(trips.get(trip.id), trip)


if __name__ == "__main__":
    unittest.main()