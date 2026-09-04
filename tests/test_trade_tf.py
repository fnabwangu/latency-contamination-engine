from decimal import Decimal

import pytest

from eig import FloatPosition, StrategyError, StrategyRiskBounds, StrategyState, TradeTF


def test_trade_tf_mandate_approval_and_float_risk():
    trade = TradeTF()
    mandate = trade.create_mandate("c1", "thesis", ("NBIS",), ("BUY",), "quarter", StrategyRiskBounds(Decimal("100"), Decimal("1000"), 2))
    trade.transition(mandate.mandate_id, StrategyState.PROPOSED)
    approved = trade.approve(mandate.mandate_id, mandate.payload_hash)
    assert approved.state is StrategyState.APPROVED
    trade.transition(mandate.mandate_id, StrategyState.ENTERING)
    position = FloatPosition("NBIS", "BUY", Decimal("500"), Decimal("50"))
    assert trade.add_position(mandate.mandate_id, position).worst_case_loss == Decimal("50")
    with pytest.raises(StrategyError):
        trade.add_position(mandate.mandate_id, FloatPosition("NBIS", "BUY", Decimal("500"), Decimal("60")))


def test_trade_tf_lifecycle_halt_exit_complete_and_revoke():
    trade = TradeTF()
    mandate = trade.create_mandate("c1", "thesis", ("NBIS",), ("BUY",), "day", StrategyRiskBounds(Decimal("100"), Decimal("1000"), 1))
    trade.transition(mandate.mandate_id, StrategyState.PROPOSED)
    trade.approve(mandate.mandate_id, mandate.payload_hash)
    trade.transition(mandate.mandate_id, StrategyState.HALTED)
    trade.transition(mandate.mandate_id, StrategyState.EXITING)
    assert trade.transition(mandate.mandate_id, StrategyState.COMPLETED).state is StrategyState.COMPLETED
    with pytest.raises(StrategyError):
        trade.revoke(mandate.mandate_id)