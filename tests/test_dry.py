from app.pipeline import process


def dry(material):
    return process(material, 'dry')['dry']


def test_mass_exact_with_fractional_moisture(dirty):  # TRAP-10
    dirty['assays'] = dirty['assays'].replace('２０,１２０', '20.01,120')
    row = next(r for r in dry(dirty)['lots'] if r['lot'] == 'PJ-01')
    assert row['dry_stock_g'] == '3999.5000'


def test_eligible_dry_stock_does_not_include_expired(dirty):
    assert dry(dirty)['eligible_dry_g'] == '20920.0000'


def test_lot_is_eligible_on_expiry_day(dirty):
    dirty['plan']['as_of'] = '2026-11-20'
    assert dry(dirty)['lots'][0]['status'] == 'ELIGIBLE'


def test_expired_stock_preserved_for_inventory(dirty):
    row = dry(dirty)['lots'][0]
    assert (row['lot'], row['stock_g'], row['dry_stock_g'], row['status']) == ('PJ-00', 5000, '4800.0000', 'EXPIRED')


def test_empty_stock_separate_status(dirty):
    row = next(r for r in dry(dirty)['lots'] if r['lot'] == 'PJ-11')
    assert (row['dry_stock_g'], row['status']) == ('0.0000', 'NO_STOCK')


def test_turn_of_year_expiry_is_calendar_day(clean):
    clean['assays'] = clean['assays'].replace('2026-12-02', '2026-12-31')
    clean['plan']['as_of'] = '2027-01-01'
    assert dry(clean)['eligible_dry_g'] == '0.0000'
