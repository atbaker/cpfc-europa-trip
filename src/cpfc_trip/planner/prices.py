from decimal import Decimal, InvalidOperation

from cpfc_trip.domain import Money, Party, Quote


def money(value: object, currency: str) -> Money | None:
    # Search engines used here quote 2-decimal currencies; refuse others pending an adapter.
    if currency not in {"GBP", "EUR", "USD", "PLN", "TRY"} or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0:
            return None
        return Money(minor_units=int((amount * 100).quantize(Decimal("1"))), currency=currency)
    except (InvalidOperation, ValueError):
        return None


def total(quotes: list[Quote | None], party: Party) -> tuple[Money | None, float]:
    seen: set[str] = set()
    values: list[Money] = []
    covered = 0
    required = sum(q is None for q in quotes) + len({q.id for q in quotes if q is not None})
    for q in quotes:
        if q is None:
            continue
        if q.id in seen:
            continue
        seen.add(q.id)
        if (
            q.unit != "party"
            or q.priced_party != party
            or q.scope not in {"round_trip", "leg", "stay"}
        ):
            continue
        if q.taxes == "excluded" and q.additional_taxes is None:
            continue
        parts = [q.amount]
        if q.taxes == "excluded" and q.additional_taxes:
            parts.append(q.additional_taxes)
        if len({p.currency for p in parts}) != 1:
            continue
        values += parts
        covered += 1
    coverage = covered / required if required else 0
    currencies = {v.currency for v in values}
    if len(currencies) != 1:
        return None, 0
    return Money(
        minor_units=sum(v.minor_units for v in values), currency=values[0].currency
    ), coverage
