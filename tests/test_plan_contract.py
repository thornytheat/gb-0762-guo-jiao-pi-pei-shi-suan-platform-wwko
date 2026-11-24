import pytest

from app.errors import TrialError
from app.modules.formula.contract import normalize


@pytest.mark.parametrize('edits,reason', [({'step_g':3000},'BAD_STEP'), ({'gel_low_sag':200},'BAD_RANGE'), ({'dry_min_g':11000},'BAD_RANGE'), ({'target_g':True},'BAD_PLAN_VALUE')])
def test_contract_rejects_invalid_hard_limits(dirty, edits, reason):
    with pytest.raises(TrialError, match=reason):
        normalize({**dirty['plan'], **edits})
