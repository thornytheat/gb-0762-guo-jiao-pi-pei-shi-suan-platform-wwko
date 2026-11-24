from app.config import MAX_STEPS
from app.errors import TrialError
from app.modules.assay.units import day, scaled


FIELDS = ('as_of', 'target_g', 'step_g', 'dry_min_g', 'gel_low_sag', 'gel_high_sag')


def normalize(plan):
    if not isinstance(plan, dict) or set(plan) != set(FIELDS):
        raise TrialError('PLAN_FIELDS_REQUIRED')
    try:
        value = {'as_of': day(plan['as_of'])}
        for field in FIELDS[1:]:
            raw = plan[field]
            if not isinstance(raw, str) and type(raw) is not int:
                raise ValueError
            factor = 1 if field in {'target_g', 'step_g'} else 1000
            value[field] = scaled(str(raw), factor, 10**9)
    except (TypeError, ValueError):
        raise TrialError('BAD_PLAN_VALUE') from None
    target, step = value['target_g'], value['step_g']
    if not step or not target or target % step or target // step > MAX_STEPS:
        raise TrialError('BAD_STEP')
    if value['gel_low_sag'] > value['gel_high_sag'] or value['dry_min_g'] > target * 1000:
        raise TrialError('BAD_RANGE')
    value['dry_min_u'] = value.pop('dry_min_g') * 10
    return value
