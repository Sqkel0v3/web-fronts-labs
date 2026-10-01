"""Тесты для scooters.py.  Запуск:  python -m unittest test_scooters -v"""
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta

from scooters import (BatteryLevel, DomainInvariantViolation, FinishTripService,
                      InMemoryScooterRepository, InMemoryTripRepository, InvalidValueObject,
                      Money, Scooter, ScooterId, ScooterStatus, StartTripService, Tariff, Trip,
                      UserId)

T0 = datetime(2026, 10, 1, 12, 0)
TARIFF = Tariff(Money.rub(10), Money.rub(50))


class ValueObjectTests(unittest.TestCase):
    def test_battery_out_of_range(self):
        for bad in (-1, 101):
            with self.assertRaises(InvalidValueObject):
                BatteryLevel(bad)

    def test_tariff_zero_price(self):
        with self.assertRaises(InvalidValueObject):
            Tariff(Money.rub(0), Money.rub(50))

    def test_money_negative(self):
        with self.assertRaises(InvalidValueObject):
            Money.rub(-1)

    def test_value_object_immutable_and_equal_by_value(self):
        a = BatteryLevel(50)
        self.assertEqual(a, BatteryLevel(50))
        with self.assertRaises(FrozenInstanceError):
            a.percent = 60

    def test_tariff_min_price(self):
        self.assertEqual(TARIFF.cost_for(2), Money.rub(50))   # 20 ₽ < 50 ₽ → минимальная
        self.assertEqual(TARIFF.cost_for(7), Money.rub(70))


class ScooterTests(unittest.TestCase):
    def test_cannot_rent_low_battery(self):
        with self.assertRaises(DomainInvariantViolation):
            Scooter.register(BatteryLevel(19)).rent()

    def test_cannot_rent_twice(self):
        scooter = Scooter.register(BatteryLevel(80))
        scooter.rent()
        with self.assertRaises(DomainInvariantViolation):
            scooter.rent()

    def test_cannot_rent_in_maintenance(self):
        scooter = Scooter.register(BatteryLevel(80))
        scooter.send_to_maintenance()
        with self.assertRaises(DomainInvariantViolation):
            scooter.rent()

    def test_no_public_setters(self):
        scooter = Scooter.register(BatteryLevel(80))
        with self.assertRaises(AttributeError):
            scooter.status = ScooterStatus.RENTED
        with self.assertRaises(AttributeError):
            scooter.new_field = 1


class TripTests(unittest.TestCase):
    def make_trip(self):
        return Trip.start(ScooterId.new(), UserId.new(), T0, TARIFF)

    def test_cannot_finish_before_start(self):
        with self.assertRaises(DomainInvariantViolation):
            self.make_trip().finish(T0 - timedelta(minutes=1))

    def test_cannot_finish_twice(self):
        trip = self.make_trip()
        trip.finish(T0 + timedelta(minutes=10))
        with self.assertRaises(DomainInvariantViolation):
            trip.finish(T0 + timedelta(minutes=20))

    def test_cost_rounds_minutes_up(self):
        cost = self.make_trip().finish(T0 + timedelta(minutes=6, seconds=1))   # 7 мин × 10 ₽
        self.assertEqual(cost, Money.rub(70))


class TripServiceTests(unittest.TestCase):
    def setUp(self):
        self.scooters = InMemoryScooterRepository()
        self.trips = InMemoryTripRepository()
        self.start = StartTripService(self.scooters, self.trips)
        self.finish = FinishTripService(self.scooters, self.trips)
        self.scooter = Scooter.register(BatteryLevel(90))
        self.scooters.save(self.scooter)

    def test_full_trip(self):
        trip = self.start.start(self.scooter.id, UserId.new(), T0, TARIFF)
        self.assertIs(self.scooters.get(self.scooter.id).status, ScooterStatus.RENTED)
        cost = self.finish.finish(trip.id, T0 + timedelta(minutes=10), BatteryLevel(75))
        self.assertEqual(cost, Money.rub(100))
        scooter = self.scooters.get(self.scooter.id)
        self.assertIs(scooter.status, ScooterStatus.AVAILABLE)
        self.assertEqual(scooter.battery, BatteryLevel(75))

    def test_failed_finish_changes_nothing(self):
        trip = self.start.start(self.scooter.id, UserId.new(), T0, TARIFF)
        with self.assertRaises(DomainInvariantViolation):
            self.finish.finish(trip.id, T0 - timedelta(minutes=1), BatteryLevel(75))
        self.assertIs(self.scooters.get(self.scooter.id).status, ScooterStatus.RENTED)


if __name__ == "__main__":
    unittest.main()