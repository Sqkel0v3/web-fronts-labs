# --- доменные исключения ---
class DomainError(Exception):
    pass


class InvalidValueObject(DomainError):
    pass


class DomainInvariantViolation(DomainError):
    pass


class AggregateNotFound(DomainError):
    pass


class TransitionNotAllowed(DomainError):
    def __init__(self, state: str, event: str):
        self.state = state
        self.event = event
        super().__init__(f"Событие {event} недопустимо в состоянии «{state}»")


# --- состояния поездки (паттерн «Состояние») ---


class TripState:
    name = ""
    allowed: frozenset = frozenset()

    def start(self, trip) -> "TripState":
        raise TransitionNotAllowed(self.name, "start")

    def reject(self, trip) -> "TripState":
        raise TransitionNotAllowed(self.name, "reject")

    def expire_reservation(self, trip) -> "TripState":
        raise TransitionNotAllowed(self.name, "expire_reservation")

    def pause(self, trip) -> "TripState":
        raise TransitionNotAllowed(self.name, "pause")

    def resume(self, trip) -> "TripState":
        raise TransitionNotAllowed(self.name, "resume")

    def finish(self, trip, in_zone: bool) -> "TripState":
        raise TransitionNotAllowed(self.name, "finish")

    def pay(self, trip) -> "TripState":
        raise TransitionNotAllowed(self.name, "pay")

    def fail_payment(self, trip) -> "TripState":
        raise TransitionNotAllowed(self.name, "fail_payment")


class Reserved(TripState):
    name = "Забронирована"
    allowed = frozenset({"start", "reject", "expire_reservation"})

    def start(self, trip):
        if not (trip.lock_opened and trip.billing_started):
            raise DomainInvariantViolation(
                "Поездка начинается только после разблокировки замка и запуска тарификации"
            )
        return InRide()

    def reject(self, trip):
        return NotStarted()

    def expire_reservation(self, trip):
        return ReservationExpired()


class InRide(TripState):
    name = "В пути"
    allowed = frozenset({"pause", "finish"})

    def pause(self, trip):
        return Paused()

    def finish(self, trip, in_zone):
        if not in_zone:
            raise DomainInvariantViolation(
                "Завершить поездку можно только в разрешённой зоне парковки"
            )
        return Finished()


class Paused(TripState):
    name = "На паузе"
    allowed = frozenset({"resume"})

    def resume(self, trip):
        return InRide()


class Finished(TripState):
    name = "Завершена"
    allowed = frozenset({"pay", "fail_payment"})

    def pay(self, trip):
        if trip.photo_id is None:
            raise DomainInvariantViolation("Списать стоимость можно только после фото самоката")
        return Paid()

    def fail_payment(self, trip):
        return Debt()


class ReservationExpired(TripState):
    name = "Бронь истекла"


class NotStarted(TripState):
    name = "Не начата"


class Paid(TripState):
    name = "Оплачена"


class Debt(TripState):
    name = "Задолженность"
