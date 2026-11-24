from app.pipeline import process


def solve(material):
    return process(material, 'blend')['blend']


def test_conflicting_valid_choices_resolve_by_expiry(dirty):  # TRAP-19
    head, *rows = dirty['assays'].splitlines()
    reversed_csv = '\n'.join([head, *reversed(rows)])
    expected = {'PJ-01': 5000, 'PJ-02': 5000}
    assert solve(dirty)['allocation'] == expected
    assert solve({**dirty, 'assays': reversed_csv})['allocation'] == expected


def test_dry_weighted_sag(dirty):
    solution = solve(dirty)
    assert (solution['batch_count'], solution['dry_g'], solution['gel_sag']) == (2, '9000.0000', '153.333')


def test_infeasible_has_no_inventory_draw(dirty):
    dirty['plan'].update(gel_low_sag=195, gel_high_sag=200)
    solution = solve(dirty)
    assert (solution['status'], solution['allocation'], solution['step_capacity_g']) == ('QUALITY_INFEASIBLE', {}, 20000)


def test_step_capacity_zero_when_whole_lots_too_small(dirty):
    dirty['plan']['step_g'] = 10000
    assert solve(dirty)['status'] == 'INSUFFICIENT_STEP_STOCK'


def test_smallest_lot_count_before_earliest(dirty):
    dirty['assays'] += 'PJ-X,2026-12-30,10,kg,0,151\n'
    assert solve(dirty)['allocation'] == {'PJ-X': 10000}


def test_zero_dry_on_ineligible_sample_does_not_make_mix(clean):
    clean['plan']['as_of'] = '2027-01-01'
    assert solve(clean)['step_capacity_g'] == 0
