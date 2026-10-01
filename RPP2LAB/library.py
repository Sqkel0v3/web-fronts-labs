"""ЛР2. Проектирование доменной модели с помощью DDD — Библиотека.

Доменный слой (разделы 1–6) использует только стандартную библиотеку Python.
Запуск:  python library.py
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4


# =====================================================================
# 1. ДОМЕННЫЕ ИСКЛЮЧЕНИЯ — собственная иерархия
# =====================================================================

class DomainError(Exception):
    """Базовое исключение доменного слоя: операция нарушает правило предметной области."""


class InvalidValueObject(DomainError):
    """Объект-значение нельзя создать с такими данными (ошибка в конструкторе)."""


class DomainInvariantViolation(DomainError):
    """Операция над агрегатом нарушила бы его инвариант."""


class AggregateNotFound(DomainError):
    """Агрегат с таким идентификатором не найден в репозитории."""


# =====================================================================
# 2. ОБЪЕКТЫ-ЗНАЧЕНИЯ (frozen=True, проверка в __post_init__)
# =====================================================================

@dataclass(frozen=True)
class Money:
    """Денежная сумма в рублях (инвариант: не отрицательна)."""
    amount: Decimal
    currency: str = "RUB"

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise InvalidValueObject("Сумма должна быть Decimal")
        if self.amount < 0:
            raise InvalidValueObject(f"Сумма не может быть отрицательной: {self.amount}")
        if self.currency != "RUB":
            raise InvalidValueObject("Поддерживаются только рубли")

    @staticmethod
    def rub(value: str | int) -> Money:
        return Money(Decimal(str(value)))

    def times(self, n: int) -> Money:
        return Money(self.amount * n, self.currency)

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"


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
class ReaderId:
    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise InvalidValueObject("ReaderId должен быть UUID")

    @staticmethod
    def new() -> ReaderId:
        return ReaderId(uuid4())


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
class LoanPeriod:
    """Период выдачи (инвариант 3: срок возврата позже даты выдачи)."""
    issued_on: date
    due_on: date

    def __post_init__(self) -> None:
        if not isinstance(self.issued_on, date) or not isinstance(self.due_on, date):
            raise InvalidValueObject("Даты периода выдачи должны быть date")
        if self.due_on <= self.issued_on:
            raise InvalidValueObject(
                f"Срок возврата ({self.due_on}) должен быть позже даты выдачи ({self.issued_on})")

    def overdue_days(self, returned_on: date) -> int:
        """Сколько дней прошло после срока возврата (0, если вернули вовремя)."""
        return max(0, (returned_on - self.due_on).days)


# =====================================================================
# 3. АГРЕГАТ Book (корень — Book)
# =====================================================================

class Book:
    # __slots__ запрещает добавлять новые атрибуты снаружи,
    # а поля доступны только на чтение через свойства (без сеттеров).
    __slots__ = ("_id", "_title", "_total_copies", "_available_copies")

    def __init__(self, book_id: BookId, title: str, total_copies: int) -> None:
        if not title.strip():
            raise DomainInvariantViolation("Название книги не может быть пустым")
        if total_copies < 1:
            raise DomainInvariantViolation("Общее число экземпляров должно быть не меньше одного")
        self._id = book_id
        self._title = title
        self._total_copies = total_copies
        self._available_copies = total_copies

    @classmethod
    def register(cls, title: str, total_copies: int) -> Book:
        """Фабрика: новая книга поступает в фонд, все экземпляры свободны."""
        return cls(BookId.new(), title, total_copies)

    @property
    def id(self) -> BookId:
        return self._id

    @property
    def title(self) -> str:
        return self._title

    @property
    def total_copies(self) -> int:
        return self._total_copies

    @property
    def available_copies(self) -> int:
        return self._available_copies

    def lend(self) -> None:
        """Инвариант 1: нельзя выдать книгу, если нет свободных экземпляров."""
        if self._available_copies == 0:
            raise DomainInvariantViolation(f"Нет свободных экземпляров книги «{self._title}»")
        self._available_copies -= 1

    def accept_return(self) -> None:
        """Инвариант 2: свободных экземпляров не может стать больше общего числа."""
        if self._available_copies >= self._total_copies:
            raise DomainInvariantViolation(
                f"Все экземпляры книги «{self._title}» уже на месте — возврат невозможен")
        self._available_copies += 1

# =====================================================================
# 4. АГРЕГАТ Loan (корень — Loan; связь с Book только по book_id)
# =====================================================================

class Loan:
    __slots__ = ("_id", "_book_id", "_reader_id", "_period", "_daily_fine_rate", "_returned_on", "_fine")

    def __init__(self, loan_id: LoanId, book_id: BookId, reader_id: ReaderId,
                 period: LoanPeriod, daily_fine_rate: Money) -> None:
        self._id = loan_id
        self._book_id = book_id            # связь с агрегатом Book — только через идентификатор
        self._reader_id = reader_id
        self._period = period
        self._daily_fine_rate = daily_fine_rate
        self._returned_on: date | None = None
        self._fine: Money | None = None

    @classmethod
    def open(cls, book_id: BookId, reader_id: ReaderId,
             period: LoanPeriod, daily_fine_rate: Money) -> Loan:
        """Фабрика: открыть новую выдачу."""
        return cls(LoanId.new(), book_id, reader_id, period, daily_fine_rate)

    @property
    def id(self) -> LoanId:
        return self._id

    @property
    def book_id(self) -> BookId:
        return self._book_id

    @property
    def reader_id(self) -> ReaderId:
        return self._reader_id

    @property
    def is_open(self) -> bool:
        return self._returned_on is None

    def close(self, returned_on: date) -> Money:
        """Инварианты 4, 5, 6: возврат не раньше выдачи, выдачу нельзя закрыть дважды;
        штраф = дни просрочки × ставка за день фиксируется вместе с датой возврата."""
        if self._returned_on is not None:
            raise DomainInvariantViolation("Выдача уже закрыта возвратом")
        if returned_on < self._period.issued_on:
            raise DomainInvariantViolation("Дата возврата не может быть раньше даты выдачи")
        self._returned_on = returned_on
        self._fine = self._daily_fine_rate.times(self._period.overdue_days(returned_on))
        return self._fine

# =====================================================================
# 5. ПОРТЫ — репозитории как Protocol
# =====================================================================

class BookRepository(Protocol):
    def get(self, book_id: BookId) -> Book: ...
    def save(self, book: Book) -> None: ...


class LoanRepository(Protocol):
    def get(self, loan_id: LoanId) -> Loan: ...
    def save(self, loan: Loan) -> None: ...
    def find_open(self, book_id: BookId, reader_id: ReaderId) -> Loan | None: ...


# =====================================================================
# 6. ДОМЕННЫЙ СЕРВИС — затрагивает Book и Loan
# =====================================================================

class LendingService:
    def __init__(self, books: BookRepository, loans: LoanRepository) -> None:
        self._books = books
        self._loans = loans

    def lend(self, book_id: BookId, reader_id: ReaderId,
             period: LoanPeriod, daily_fine_rate: Money) -> Loan:
        """Выдача: занять экземпляр книги (Book) + открыть выдачу (Loan)."""
        book = self._books.get(book_id)
        book.lend()                                      # инвариант 1 проверяет сам Book
        loan = Loan.open(book.id, reader_id, period, daily_fine_rate)
        self._books.save(book)
        self._loans.save(loan)
        return loan

    def return_book(self, book_id: BookId, reader_id: ReaderId, returned_on: date) -> Money:
        """Возврат: закрыть выдачу с расчётом штрафа (Loan) + вернуть экземпляр (Book)."""
        loan = self._loans.find_open(book_id, reader_id)
        if loan is None:                                 # правило 7 — условие поиска записи
            raise DomainInvariantViolation("У этого читателя нет открытой выдачи этой книги")
        book = self._books.get(loan.book_id)             # загрузка второго агрегата по ID
        fine = loan.close(returned_on)                   # инварианты 4–6 проверяет сам Loan
        book.accept_return()                             # инвариант 2 проверяет сам Book
        self._loans.save(loan)
        self._books.save(book)
        return fine


# =====================================================================
# 7. АДАПТЕРЫ — in-memory репозитории (база данных — словари)
# =====================================================================

# Не наследуются от Protocol: достаточно иметь методы с нужными именами.
# Хранят копии агрегатов: изменения попадают в «базу» только через save().

class InMemoryBookRepository:
    def __init__(self) -> None:
        self._items: dict[BookId, Book] = {}

    def get(self, book_id: BookId) -> Book:
        if book_id not in self._items:
            raise AggregateNotFound(f"Книга {book_id.value} не найдена")
        return copy.deepcopy(self._items[book_id])

    def save(self, book: Book) -> None:
        self._items[book.id] = copy.deepcopy(book)


class InMemoryLoanRepository:
    def __init__(self) -> None:
        self._items: dict[LoanId, Loan] = {}

    def get(self, loan_id: LoanId) -> Loan:
        if loan_id not in self._items:
            raise AggregateNotFound(f"Выдача {loan_id.value} не найдена")
        return copy.deepcopy(self._items[loan_id])

    def save(self, loan: Loan) -> None:
        self._items[loan.id] = copy.deepcopy(loan)

    def find_open(self, book_id: BookId, reader_id: ReaderId) -> Loan | None:
        for loan in self._items.values():
            if loan.book_id == book_id and loan.reader_id == reader_id and loan.is_open:
                return copy.deepcopy(loan)
        return None


# =====================================================================
# 8. ДЕМОНСТРАЦИЯ
# =====================================================================

def attempt(description: str, action) -> None:
    """Выполнить действие, которое должно нарушить правило, и показать отказ."""
    print(description)
    try:
        action()
        print("    Выполнено")
    except DomainError as e:
        print(f"    Отказ ({type(e).__name__}): {e}")


def show_book(book: Book) -> None:
    print(f"    «{book.title}»: свободно {book.available_copies} из {book.total_copies}")


def demo_library() -> None:
    books = InMemoryBookRepository()
    loans = InMemoryLoanRepository()
    service = LendingService(books, loans)

    rate = Money.rub(10)                         # штраф 10 ₽ за день просрочки
    book = Book.register("Мастер и Маргарита", total_copies=1)
    books.save(book)
    anna, ivan = ReaderId.new(), ReaderId.new()
    period = LoanPeriod(date(2026, 10, 1), date(2026, 10, 15))

    print("1) Анна берёт книгу (в фонде 1 экземпляр)")
    service.lend(book.id, anna, period, rate)
    show_book(books.get(book.id))

    attempt("2) Иван пытается взять ту же книгу",
            lambda: service.lend(book.id, ivan, period, rate))
    attempt("3) Иван пытается вернуть книгу, которую не брал",
            lambda: service.return_book(book.id, ivan, date(2026, 10, 10)))
    attempt("4) Анна возвращает книгу раньше даты выдачи",
            lambda: service.return_book(book.id, anna, date(2026, 9, 30)))

    print("5) Анна возвращает книгу 18.10 (срок — 15.10)")
    fine = service.return_book(book.id, anna, date(2026, 10, 18))
    print(f"    Штраф: {fine} (3 дня × 10 ₽)")
    show_book(books.get(book.id))

    attempt("6) Анна пытается вернуть ту же книгу повторно",
            lambda: service.return_book(book.id, anna, date(2026, 10, 19)))
    attempt("7) Создаём период выдачи со сроком раньше даты выдачи",
            lambda: LoanPeriod(date(2026, 10, 15), date(2026, 10, 1)))
    attempt("8) Создаём отрицательную сумму",
            lambda: Money.rub(-5))


if __name__ == "__main__":
    demo_library()