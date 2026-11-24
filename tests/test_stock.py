from app.pipeline import process


def stock(material):
    return process(material, 'stock')['stock']


def test_warehouse_conservation(dirty):
    r = stock(dirty)
    assert (r['begin_g'], r['issued_g'], r['end_g'], r['shortage_g'], r['balanced']) == (27000, 10000, 17000, 0, True)


def test_below_step_remains_in_whole_stock(dirty):
    row = next(r for r in stock(dirty)['rows'] if r['lot'] == 'PJ-05')
    assert (row['begin_g'], row['issued_g'], row['end_g'], row['code']) == (2000, 0, 2000, 'BELOW_STEP')


def test_expired_and_available_unused_different(dirty):
    codes = {r['lot']: r['code'] for r in stock(dirty)['rows']}
    assert (codes['PJ-00'], codes['PJ-04'], codes['PJ-01']) == ('EXPIRED', 'NOT_SELECTED', 'ISSUED')


def test_infeasible_plan_stays_open(dirty):
    dirty['plan'].update(gel_low_sag=195, gel_high_sag=200)
    r = stock(dirty)
    assert (r['issued_g'], r['end_g'], r['shortage_g']) == (0, 27000, 10000)


def test_clean_withdraws_earliest_only(clean):
    rows = stock(clean)['rows']
    assert [r['issued_g'] for r in rows] == [5000, 0, 0]


def test_conflicts_never_enter_cleared_stock(dirty):
    assert all(r['lot'] != 'PJ-06' for r in stock(dirty)['rows'])
