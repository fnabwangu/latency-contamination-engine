from decimal import Decimal

import pytest

from eig import SourceReliability


def test_reliability_shrinks_small_samples_and_updates():
    profile = SourceReliability("feed")
    assert profile.posterior_mean == Decimal("0.5")
    updated = profile.record(True).record(True).record(False)
    assert updated.posterior_mean == Decimal("0.6")
    assert updated.effective_sample_size == Decimal("5")


def test_reliability_weight_bounds_are_validated():
    assert SourceReliability("weak", failures=100).weight() == Decimal("0.25")
    with pytest.raises(ValueError):
        SourceReliability("feed").weight(Decimal("0"))