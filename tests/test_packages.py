from decimal import Decimal

import pytest

from eig import Candidate, CandidateType, PackageError, Sleeve, build_trade_set, promote_sleeve_to_algo


def make_sleeve(thesis="thesis"):
    return Sleeve("s1", "NBIS", "BUY", "equity", thesis, "earnings", "breakout", "45", "below 36", Decimal("100"), Decimal("50"))


def test_trade_set_requires_coherent_shared_thesis():
    candidate = Candidate("set-1", CandidateType.BRANDED_TRADE_SET, "Set", "thesis", "catalyst", "week", sleeves=(make_sleeve(),))
    package = build_trade_set(candidate)
    assert package.aggregate_risk == Decimal("50")
    with pytest.raises(PackageError):
        build_trade_set(Candidate("set-2", CandidateType.BRANDED_TRADE_SET, "Set", "thesis", "catalyst", "week", sleeves=(make_sleeve("other"),)))


def test_algo_promotion_does_not_inherit_package_probability():
    sleeve = make_sleeve()
    source = Candidate("set-1", CandidateType.BRANDED_TRADE_SET, "Set", "thesis", "catalyst", "week", probability=Decimal("0.8"), sleeves=(sleeve,))
    child = promote_sleeve_to_algo(source, sleeve)
    assert child.candidate_type is CandidateType.ALGO_SINGLE
    assert child.probability is None