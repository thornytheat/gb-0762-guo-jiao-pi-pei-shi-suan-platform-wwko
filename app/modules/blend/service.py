from app.config import MAX_LOTS
from app.errors import TrialError
from app.modules.formula.metrics import measurements, weigh
from .search import search


def select(plan, lots):
    available = [row for row in lots if row['status'] == 'ELIGIBLE' and row['stock_g'] >= plan['step_g']]
    if len(available) > MAX_LOTS:
        raise TrialError('TOO_MANY_LOTS')
    capacity = sum(lot['stock_g'] // plan['step_g'] * plan['step_g'] for lot in available)
    if capacity < plan['target_g']:
        return {'status': 'INSUFFICIENT_STEP_STOCK', 'allocation': {}, 'batch_count': 0, 'step_capacity_g': capacity, 'visited': 0}
    allocation, visited = search(available, plan)
    if allocation is None:
        return {'status': 'QUALITY_INFEASIBLE', 'allocation': {}, 'batch_count': 0, 'step_capacity_g': capacity, 'visited': visited}
    selected = {lot['lot']: weight for lot, weight in zip(available, allocation) if weight}
    dry, moment = weigh(available, allocation)
    return {'status': 'FEASIBLE', 'allocation': selected, 'batch_count': len(selected), 'step_capacity_g': capacity,
            'visited': visited, **measurements(dry, moment)}
