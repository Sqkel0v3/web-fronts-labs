"""ЛР2. Доменная модель «Библиотека» (DDD).  Запуск: python library.py"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4


# ===== 1. Доменные исключения =====

class DomainError(Exception):
    """Базовое доменное исключение."""


class InvalidValueObject(DomainError):
    """Некорректные данные при создании объекта-значения."""


class DomainInvariantViolation(DomainError):
    """Операция нарушает инвариант агрегата."""


# ===== 2. Объекты-значения =====

@dataclass(frozen=True)
class BookId:
    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise InvalidValueObject("BookId должен быть UUID")

    @staticmethod
    def new() -> BookId:
        return BookId(uuid4())


@dataclass(frozen=True)
class LoanId:
    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise InvalidValueObject("LoanId должен быть UUID")

    @staticmethod
    def new() -> LoanId:
        return LoanId(uuid4())


@dataclass(frozen=True)
class Money:
    amount: Decimal

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise InvalidValueObject("Сумма не может быть отрицательной")


@dataclass(frozen=True)
class LoanPeriod:
    issued_on: date
    due_on: date

    def __post_init__(self) -> None:
        if self.due_on <= self.issued_on:
            raise InvalidValueObject("Срок возврата должен быть позже даты выдачи")


# ===== 3. Агрегат Book (корень — Book) =====

class Book:
    __slots__ = ("_id", "_available_copies")

    def __init__(self, book_id: BookId, copies: int) -> None:
        self._id = book_id
        self._available_copies = copies

    @property
    def id(self) -> BookId:
        return self._id

    @property
    def available_copies(self) -> int:
        return self._available_copies

    def lend(self) -> None:
        """Инвариант: нельзя выдать книгу, если нет свободных экземпляров."""
        if self._available_copies == 0:
            raise DomainInvariantViolation("Нет свободных экземпляров")
        self._available_copies -= 1


# ===== 4. Агрегат Loan (корень — Loan, связь с Book только по book_id) =====

class Loan:
    __slots__ = ("_id", "_book_id", "_period", "_daily_fine", "_returned_on")

    def __init__(self, loan_id: LoanId, book_id: BookId, period: LoanPeriod, daily_fine: Money) -> None:
        self._id = loan_id
        self._book_id = book_id
        self._period = period
        self._daily_fine = daily_fine
        self._returned_on: date | None = None

    @property
    def id(self) -> LoanId:
        return self._id

    def close(self, returned_on: date) -> Money:
        """Инвариант: выдачу нельзя закрыть дважды и раньше даты выдачи;
        при просрочке начисляется штраф = дни просрочки × ставка."""
        if self._returned_on is not None:
            raise DomainInvariantViolation("Выдача уже закрыта")
        if returned_on < self._period.issued_on:
            raise DomainInvariantViolation("Дата возврата раньше даты выдачи")
        self._returned_on = returned_on
        overdue_days = max(0, (returned_on - self._period.due_on).days)
        return Money(self._daily_fine.amount * overdue_days)


# ===== 5. Репозитории (порты) =====

class BookRepository(Protocol):
    def get(self, book_id: BookId) -> Book: ...
    def save(self, book: Book) -> None: ...


class LoanRepository(Protocol):
    def get(self, loan_id: LoanId) -> Loan: ...
    def save(self, loan: Loan) -> None: ...


# ===== 6. Доменный сервис (затрагивает Book и Loan) =====

class LendingService:
    def __init__(self, books: BookRepository, loans: LoanRepository) -> None:
        self._books = books
        self._loans = loans

    def lend(self, book_id: BookId, period: LoanPeriod, daily_fine: Money) -> Loan:
        book = self._books.get(book_id)
        book.lend()
        loan = Loan(LoanId.new(), book.id, period, daily_fine)
        self._books.save(book)
        self._loans.save(loan)
        return loan


# ===== 7. In-memory база данных =====

class InMemoryBookRepository:
    def __init__(self) -> None:
        self._items: dict[BookId, Book] = {}

    def get(self, book_id: BookId) -> Book:
        return self._items[book_id]

    def save(self, book: Book) -> None:
        self._items[book.id] = book


class InMemoryLoanRepository:
    def __init__(self) -> None:
        self._items: dict[LoanId, Loan] = {}

    def get(self, loan_id: LoanId) -> Loan:
        return self._items[loan_id]

    def save(self, loan: Loan) -> None:
        self._items[loan.id] = loan


# ===== 8. Демонстрация =====

if __name__ == "__main__":
    books, loans = InMemoryBookRepository(), InMemoryLoanRepository()
    service = LendingService(books, loans)
    book = Book(BookId.new(), copies=1)
    books.save(book)
    period = LoanPeriod(date(2026, 10, 1), date(2026, 10, 15))
    fine_per_day = Money(Decimal(10))

    loan = service.lend(book.id, period, fine_per_day)
    print("1) Книга выдана, свободно:", books.get(book.id).available_copies)

    try:
        service.lend(book.id, period, fine_per_day)
    except DomainError as e:
        print("2) Повторная выдача — отказ:", e)

    print("3) Возврат 18.10 при сроке 15.10, штраф:", loan.close(date(2026, 10, 18)).amount, "руб.")

    try:
        loan.close(date(2026, 10, 19))
    except DomainError as e:
        print("4) Повторный возврат — отказ:", e)

    try:
        LoanPeriod(date(2026, 10, 15), date(2026, 10, 1))
    except DomainError as e:
        print("5) Некорректный период — отказ:", e)