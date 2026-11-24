import pytest

from app.errors import TrialError
from app.pipeline import process


def verify(material):
    return process(material, 'formula')['formula']


def test_proposal_with_expired_lot(dirty):
    r = verify(dirty)
    assert (r['mass_g'], r['gel_sag'], r['checks']['gel_high']) == (10000, '155.102', False)
    assert r['findings'][0]['codes'] == ['EXPIRED'] and r['can_make'] is False


def test_dry_and_sag_equal_boundaries_pass(clean):
    r = verify(clean)
    assert r['dry_g'] == '4500.0000' and r['gel_sag'] == '152.000' and r['can_make'] is True


def test_unknown_lot_does_not_contribute_dry(clean):
    clean['proposal'] = {'missing': 5000}
    r = verify(clean)
    assert r['dry_g'] == '0.0000' and r['gel_sag'] is None and r['findings'][0]['codes'] == ['LOT_NOT_ACCEPTED']


def test_off_grid_and_stock_cap(clean):
    clean['proposal'] = {'Q-20': 6001}
    assert verify(clean)['findings'][0]['codes'] == ['OVER_STOCK', 'OFF_STEP']


def test_negative_draw_rejected(clean):
    clean['proposal'] = {'Q-20': -1}
    with pytest.raises(TrialError, match='BAD_PROPOSAL'):
        verify(clean)


def test_unrounded_strength_controls_acceptance(clean):
    clean['assays'] = clean['assays'].replace('10,152', '9.99,152').replace('10,154', '10,152.001')
    clean['plan']['gel_high_sag'] = '152.000'
    clean['proposal'] = {'Q-20': 2500, 'Q-21': 2500}
    r = verify(clean)
    assert r['gel_sag'] == '152.000' and r['checks']['gel_high'] is False
