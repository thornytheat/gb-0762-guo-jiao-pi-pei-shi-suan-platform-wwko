from decimal import Decimal, ROUND_HALF_UP

SCALE = 10_000


def dry_units(grams, moisture_bp):
    return grams * (SCALE - moisture_bp)


def as_grams(units):
    return f'{Decimal(units) / SCALE:.4f}'


def sag_display(moment, dry):
    if dry == 0:
        return None
    return str((Decimal(moment) / dry / 1000).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP))
