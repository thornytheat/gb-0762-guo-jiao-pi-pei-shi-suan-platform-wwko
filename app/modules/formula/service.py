from app.errors import TrialError
from .metrics import measurements, quality, weigh


def inspect(plan, lots, proposal):
    if not isinstance(proposal, dict) or any(type(v) is not int or v < 0 or v > 10**9 for v in proposal.values()):
        raise TrialError('BAD_PROPOSAL')
    known = {row['lot']: row for row in lots}
    findings = []
    for lot_id, weight in proposal.items():
        if not weight:
            continue
        lot = known.get(lot_id)
        codes = []
        if not lot:
            codes.append('LOT_NOT_ACCEPTED')
        else:
            if lot['status'] != 'ELIGIBLE':
                codes.append(lot['status'])
            if weight > lot['stock_g']:
                codes.append('OVER_STOCK')
        if weight % plan['step_g']:
            codes.append('OFF_STEP')
        findings.append({'lot': lot_id, 'line': lot['line'] if lot else None, 'grams': weight, 'codes': codes})
    matched = [proposal.get(lot['lot'], 0) for lot in lots]
    dry, moment = weigh(lots, matched)
    mass = sum(proposal.values())
    checks = quality(plan, mass, dry, moment)
    return {'can_make': all(checks.values()) and not any(row['codes'] for row in findings),
            'mass_g': mass, **measurements(dry, moment), 'checks': checks, 'findings': findings}
