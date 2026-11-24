def reconcile(plan, lots, solution):
    picks = solution['allocation']
    rows = []
    for lot in lots:
        issued = picks.get(lot['lot'], 0)
        evidence = 'ISSUED' if issued else lot['status']
        if not issued and lot['status'] == 'ELIGIBLE':
            evidence = 'BELOW_STEP' if lot['stock_g'] < plan['step_g'] else 'NOT_SELECTED'
        rows.append({'lot': lot['lot'], 'line': lot['line'], 'expires': lot['expires'], 'begin_g': lot['stock_g'],
                     'issued_g': issued, 'end_g': lot['stock_g'] - issued, 'code': evidence})
    begin, issued, end = [sum(row[key] for row in rows) for key in ('begin_g', 'issued_g', 'end_g')]
    target = plan['target_g']
    shortage = target - issued
    return {'target_g': target, 'begin_g': begin, 'issued_g': issued, 'end_g': end, 'shortage_g': shortage,
            'balanced': begin == issued + end and 0 <= shortage <= target and all(row['end_g'] >= 0 for row in rows),
            'rows': rows}
