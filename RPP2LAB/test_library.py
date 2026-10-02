"""Тесты для library.py.  Запуск: python -m unittest test_library -v"""
import unittest
from datetime import date
from decimal import Decimal

from library import (Book, BookId, DomainInvariantViolation, InMemoryBookRepository,
                     InMemoryLoanRepository, InvalidValueObject, LendingService, Loan, LoanId,
                     LoanPeriod, Money)

PERIOD = LoanPeriod(date(2026, 10, 1), date(2026, 10, 15))
FINE = Money(Decimal(10))


class LibraryTests(unittest.TestCase):
    def make_loan(self):
        return Loan(LoanId.new(), BookId.new(), PERIOD, FINE)

    def test_invalid_period(self):
        with self.assertRaises(InvalidValueObject):
            LoanPeriod(date(2026, 10, 15), date(2026, 10, 1))

    def test_negative_money(self):
        with self.assertRaises(InvalidValueObject):
            Money(Decimal(-1))

    def test_cannot_lend_without_copies(self):
        book = Book(BookId.new(), 1)
        book.lend()
        with self.assertRaises(DomainInvariantViolation):
            book.lend()

    def test_no_public_setter(self):
        with self.assertRaises(AttributeError):
            Book(BookId.new(), 1).available_copies = 5

    def test_fine_when_overdue(self):
        self.assertEqual(self.make_loan().close(date(2026, 10, 18)), Money(Decimal(30)))

    def test_no_fine_on_time(self):
        self.assertEqual(self.make_loan().close(date(2026, 10, 15)), Money(Decimal(0)))

    def test_cannot_close_twice(self):
        loan = self.make_loan()
        loan.close(date(2026, 10, 10))
        with self.assertRaises(DomainInvariantViolation):
            loan.close(date(2026, 10, 11))

    def test_cannot_return_before_issue(self):
        with self.assertRaises(DomainInvariantViolation):
            self.make_loan().close(date(2026, 9, 30))

    def test_lending_service(self):
        books, loans = InMemoryBookRepository(), InMemoryLoanRepository()
        book = Book(BookId.new(), 1)
        books.save(book)
        loan = LendingService(books, loans).lend(book.id, PERIOD, FINE)
        self.assertEqual(books.get(book.id).available_copies, 0)
        self.assertIs(loans.get(loan.id), loan)


if __name__ == "__main__":
    unittest.main()