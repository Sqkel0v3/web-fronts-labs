"""Тесты для library.py.  Запуск:  python -m unittest test_library -v"""
import unittest
from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal

from library import (Book, BookId, DomainInvariantViolation, InMemoryBookRepository,
                     InMemoryLoanRepository, InvalidValueObject, LendingService, Loan,
                     LoanPeriod, Money, ReaderId)

PERIOD = LoanPeriod(date(2026, 10, 1), date(2026, 10, 15))
RATE = Money.rub(10)


class ValueObjectTests(unittest.TestCase):
    def test_due_before_issue(self):
        with self.assertRaises(InvalidValueObject):
            LoanPeriod(date(2026, 10, 15), date(2026, 10, 1))

    def test_money_negative(self):
        with self.assertRaises(InvalidValueObject):
            Money(Decimal("-1"))

    def test_value_object_immutable_and_equal_by_value(self):
        a = Money.rub(5)
        self.assertEqual(a, Money.rub(5))
        with self.assertRaises(FrozenInstanceError):
            a.amount = Decimal(10)


class BookTests(unittest.TestCase):
    def test_cannot_lend_without_free_copies(self):
        book = Book.register("Книга", 1)
        book.lend()
        with self.assertRaises(DomainInvariantViolation):
            book.lend()

    def test_cannot_return_more_than_total(self):
        with self.assertRaises(DomainInvariantViolation):
            Book.register("Книга", 2).accept_return()

    def test_total_copies_at_least_one(self):
        with self.assertRaises(DomainInvariantViolation):
            Book.register("Книга", 0)

    def test_no_public_setters(self):
        book = Book.register("Книга", 1)
        with self.assertRaises(AttributeError):
            book.available_copies = 100
        with self.assertRaises(AttributeError):
            book.new_field = 1


class LoanTests(unittest.TestCase):
    def make_loan(self):
        return Loan.open(BookId.new(), ReaderId.new(), PERIOD, RATE)

    def test_no_fine_when_on_time(self):
        self.assertEqual(self.make_loan().close(date(2026, 10, 15)), Money.rub(0))

    def test_fine_when_overdue(self):
        self.assertEqual(self.make_loan().close(date(2026, 10, 18)), Money.rub(30))

    def test_cannot_return_before_issue(self):
        with self.assertRaises(DomainInvariantViolation):
            self.make_loan().close(date(2026, 9, 30))

    def test_cannot_close_twice(self):
        loan = self.make_loan()
        loan.close(date(2026, 10, 10))
        with self.assertRaises(DomainInvariantViolation):
            loan.close(date(2026, 10, 11))


class LendingServiceTests(unittest.TestCase):
    def setUp(self):
        self.books = InMemoryBookRepository()
        self.loans = InMemoryLoanRepository()
        self.service = LendingService(self.books, self.loans)
        self.book = Book.register("Книга", 1)
        self.books.save(self.book)
        self.reader = ReaderId.new()

    def test_full_cycle(self):
        self.service.lend(self.book.id, self.reader, PERIOD, RATE)
        self.assertEqual(self.books.get(self.book.id).available_copies, 0)
        fine = self.service.return_book(self.book.id, self.reader, date(2026, 10, 17))
        self.assertEqual(fine, Money.rub(20))
        self.assertEqual(self.books.get(self.book.id).available_copies, 1)

    def test_return_without_open_loan(self):
        with self.assertRaises(DomainInvariantViolation):
            self.service.return_book(self.book.id, self.reader, date(2026, 10, 10))

    def test_failed_return_changes_nothing(self):
        loan = self.service.lend(self.book.id, self.reader, PERIOD, RATE)
        with self.assertRaises(DomainInvariantViolation):
            self.service.return_book(self.book.id, self.reader, date(2026, 9, 1))
        self.assertTrue(self.loans.get(loan.id).is_open)
        self.assertEqual(self.books.get(self.book.id).available_copies, 0)


if __name__ == "__main__":
    unittest.main()