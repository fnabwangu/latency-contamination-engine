from decimal import Decimal

from eig import Exposure, hedge_reduces_named_risk, summarize_exposure


def test_exposure_detects_hidden_factor_concentration():
    report = summarize_exposure((Exposure("A", Decimal("15000"), "AI", "capex"), Exposure("B", Decimal("12000"), "AI", "capex")))
    assert report.gross_delta == Decimal("27000")
    assert report.hidden_concentration == ("AI",)


def test_hedge_must_reduce_same_named_risk():
    position = Exposure("A", Decimal("10000"), "rates", "duration")
    assert hedge_reduces_named_risk(position, Exposure("H", Decimal("-5000"), "rates", "duration"))
    assert not hedge_reduces_named_risk(position, Exposure("H", Decimal("-5000"), "tech", "duration"))