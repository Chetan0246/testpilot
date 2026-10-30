"""Pytest file for inventory module - tests intended behaviour per docstrings."""

import pytest
from inventory import Inventory, OutOfStock, apply_discount


@pytest.mark.xfail(reason="TestPilot found a bug: The `add` method only checks `qty < 0`, but the docstring requires `qty <= 0` to raise `ValueError`.", strict=True)
def test_add_zero_qty_raises_valueerror():
    """Docstring says qty must be positive; qty <= 0 should raise ValueError."""
    inv = Inventory()
    with pytest.raises(ValueError, match="qty must be positive"):
        inv.add("apple", 0)


def test_add_negative_qty_raises_valueerror():
    """Negative qty should raise ValueError."""
    inv = Inventory()
    with pytest.raises(ValueError, match="qty must be positive"):
        inv.add("apple", -1)


def test_add_large_qty():
    """Adding a large quantity should work correctly."""
    inv = Inventory()
    inv.add("apple", 10**6)
    assert inv.count("apple") == 10**6


@pytest.mark.xfail(reason="TestPilot found a bug: The `remove` method leaves items at zero stock instead of removing them, contradicting the documented behavior the test enforces.", strict=True)
def test_remove_exact_stock_removes_item_entirely():
    """Removing all stock should make item disappear from inventory."""
    inv = Inventory()
    inv.add("apple", 3)
    inv.remove("apple", 3)
    assert inv.count("apple") == 0
    assert "apple" not in inv.items()


def test_remove_more_than_stock_raises_out_of_stock():
    """Removing more than available should raise OutOfStock."""
    inv = Inventory()
    inv.add("apple", 2)
    with pytest.raises(OutOfStock):
        inv.remove("apple", 3)


def test_remove_unknown_item_raises_out_of_stock():
    """Removing an item not in stock should raise OutOfStock."""
    inv = Inventory()
    with pytest.raises(OutOfStock):
        inv.remove("apple", 1)


@pytest.mark.xfail(reason="TestPilot found a bug: The `items` method returns keys unsorted, while the docstring and test expect alphabetical ordering.", strict=True)
def test_items_returns_sorted_alphabetically():
    """items() should return names sorted alphabetically."""
    inv = Inventory()
    inv.add("banana", 1)
    inv.add("apple", 1)
    inv.add("cherry", 1)
    assert inv.items() == ["apple", "banana", "cherry"]


def test_count_unknown_item_returns_zero():
    """count() should return 0 for items not in stock."""
    inv = Inventory()
    assert inv.count("nonexistent") == 0


def test_apply_discount_percent_zero():
    """0% discount should return original price."""
    assert apply_discount(100.0, 0) == 100.0


def test_apply_discount_percent_100():
    """100% discount should return 0.0."""
    assert apply_discount(100.0, 100) == 0.0


def test_apply_discount_invalid_percent_raises_valueerror():
    """Percent outside 0-100 should raise ValueError."""
    with pytest.raises(ValueError, match="percent must be between 0 and 100"):
        apply_discount(100.0, -10)
    with pytest.raises(ValueError, match="percent must be between 0 and 100"):
        apply_discount(100.0, 110)


def test_apply_discount_large_price():
    """Discount on large price should still round to 2 decimals."""
    assert apply_discount(1_000_000.0, 10) == 900_000.0
