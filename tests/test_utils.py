import os
import sys
from decimal import Decimal

# Ensure the app module is importable when tests run from any location
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app import to_decimal, money


def test_to_decimal_valid():
    assert to_decimal("3.14") == Decimal("3.14")


def test_to_decimal_invalid():
    assert to_decimal("abc") == Decimal(0)


def test_to_decimal_default_zero():
    assert to_decimal(None) == Decimal(0)


def test_money_format():
    assert money(Decimal("2")) == "$2.00"
