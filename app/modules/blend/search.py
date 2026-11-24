from app.config import SEARCH_LIMIT
from app.errors import TrialError


def search(lots, plan):
    """Visit lot counts in ascending order, then older allocations in descending order."""
    step = plan['step_g']
    target = plan['target_g'] // step
    capacities = [min(lot['stock_g'] // step, target) for lot in lots]
    coefficients = []
    for lot in lots:
        dry = step * (10_000 - lot['moisture_bp'])
        coefficients.append((dry, dry * (lot['gel_msag'] - plan['gel_low_sag']),
                             dry * (plan['gel_high_sag'] - lot['gel_msag'])))
    bounds = [(0, 0, 0, 0)] * (len(lots) + 1)
    for i in reversed(range(len(lots))):
        capacity, dry, low, high = bounds[i+1]
        d, lo, hi = coefficients[i]
        bounds[i] = (capacity + capacities[i], max(dry, d), max(low, lo), max(high, hi))
    visited = 0

    def visit(i, remain, use, dry, low, high):
        nonlocal visited
        visited += 1
        if visited > SEARCH_LIMIT:
            raise TrialError('SEARCH_LIMIT')
        if remain == 0:
            return (0,) * (len(lots) - i) if use == 0 and dry >= plan['dry_min_u'] and low >= 0 and high >= 0 else None
        cap, best_dry, best_low, best_high = bounds[i]
        if (use <= 0 or use > remain or use > len(lots) - i or remain > cap
                or dry + remain * best_dry < plan['dry_min_u'] or low + remain * best_low < 0 or high + remain * best_high < 0):
            return None
        d, lo, hi = coefficients[i]
        for n in range(min(remain, capacities[i]), -1, -1):
            tail = visit(i+1, remain-n, use-int(n > 0), dry+n*d, low+n*lo, high+n*hi)
            if tail is not None:
                return (n, *tail)
        return None

    for used in range(1, min(len(lots), target) + 1):
        found = visit(0, target, used, 0, 0, 0)
        if found is not None:
            return [n * step for n in found], visited
    return None, visited
