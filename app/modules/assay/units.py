import re
import unicodedata
from datetime import date
from decimal import Decimal

NUMERIC = re.compile(r'(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,3})?', re.ASCII)


def number(value):
    value = unicodedata.normalize('NFKC', value.strip())
    if not NUMERIC.fullmatch(value):
        raise ValueError('BAD_NUMBER')
    return Decimal(value.replace(',', ''))


def scaled(value, factor, maximum):
    amount = number(value) * factor
    if amount != amount.to_integral_value() or amount > maximum:
        raise ValueError('BAD_SCALE')
    return int(amount)


def day(value):
    try:
        result = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError('BAD_DATE') from None
    if result.isoformat() != value:
        raise ValueError('BAD_DATE')
    return value


def grams(value, unit):
    if unit not in {'g', 'kg'}:
        raise ValueError('UNKNOWN_UNIT')
    return scaled(value, 1000 if unit == 'kg' else 1, 10_000_000)
