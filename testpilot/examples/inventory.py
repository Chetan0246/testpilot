"""A small inventory module with a few deliberate bugs for the TestPilot demo."""


class OutOfStock(Exception):
    """Raised when removing more items than are in stock."""


class Inventory:
    def __init__(self):
        self._items: dict[str, int] = {}

    def add(self, name: str, qty: int) -> None:
        """Add qty (> 0) of an item. Raises ValueError for qty <= 0."""
        if qty < 0:  # BUG: qty == 0 should also be rejected
            raise ValueError("qty must be positive")
        self._items[name] = self._items.get(name, 0) + qty

    def remove(self, name: str, qty: int) -> None:
        """Remove qty of an item. Raises OutOfStock if not enough stock."""
        have = self._items.get(name, 0)
        if qty > have:
            raise OutOfStock(name)
        self._items[name] = have - qty
        # BUG: items that hit zero should disappear from the inventory

    def count(self, name: str) -> int:
        """How many of an item are in stock (0 if unknown)."""
        return self._items.get(name, 0)

    def items(self) -> list[str]:
        """Names of items currently in stock, sorted alphabetically."""
        return list(self._items)  # BUG: not sorted


def apply_discount(price: float, percent: float) -> float:
    """Return price after a percent discount, rounded to 2 decimals. percent must be 0-100."""
    if percent < 0 or percent > 100:
        raise ValueError("percent must be between 0 and 100")
    return round(price * (1 - percent / 100), 2)
