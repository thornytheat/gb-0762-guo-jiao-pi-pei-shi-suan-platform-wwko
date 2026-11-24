import pytest

from app.errors import TrialError
from app.modules.assay.service import receive


def test_bom_and_split_header(dirty):  # TRAP-02 TRAP-04
    r = receive(dirty['assays'])
    assert r['counts'] == dict(input=16, blanks=1, sections=2, accepted=7, isolated=7)
    assert r['balanced'] is True


def test_extra_column_keeps_line(dirty):  # TRAP-05
    row = next(r for r in receive(dirty['assays'])['isolated'] if r['code'] == 'COLUMN_COUNT')
    assert (row['line'], row['raw'][-1]) == (14, 'extra')


def test_blank_and_sentinel_are_distinct(dirty):  # TRAP-07
    rows = receive(dirty['assays'])['isolated']
    assert [(r['line'], r['code']) for r in rows if r['code'] in {'EMPTY_CELL', 'MISSING_SENTINEL'}] == [(11, 'MISSING_SENTINEL'), (12, 'EMPTY_CELL')]


def test_fullwidth_thousands_and_decimal_contract(dirty):  # TRAP-06
    lot = next(r for r in receive(dirty['assays'])['lots'] if r['lot'] == 'PJ-01')
    assert (lot['stock_g'], lot['moisture_bp'], lot['gel_msag']) == (5000, 2000, 120000)


def test_contradictory_assays_disable_both(dirty):  # TRAP-14
    result = receive(dirty['assays'])
    assert 'PJ-06' not in [r['lot'] for r in result['lots']]
    assert [r['line'] for r in result['isolated'] if r['code'] == 'ASSAY_CONFLICT'] == [9, 10]


def test_kg_is_normalized_before_duplicate_detection(dirty):  # TRAP-15
    result = receive(dirty['assays'])
    lot = next(r for r in result['lots'] if r['lot'] == 'PJ-02')
    assert lot['stock_g'] == 5000 and result['reason_counts']['EXACT_DUPLICATE'] == 1


def test_header_only_distinct_from_blank(clean):
    assert receive(clean['assays'].splitlines()[0])['state'] == 'HEADER_ONLY'
    with pytest.raises(TrialError, match='BLANK_FILE'):
        receive('\n , ,\n')
    with pytest.raises(TrialError, match='EMPTY_FILE'):
        receive('')
