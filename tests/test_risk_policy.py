from decimal import Decimal

import pytest

from eig import AlgoRiskPolicy, ExecutionError, ExecutionMandate, RootExecutionEngine
from tests.test_execution import FakeBroker, make_approved


def test_algo_policy_blocks_halt_delta_and_reward_risk():
    policy = AlgoRiskPolicy()
    assert policy.execution_allowed(Decimal("0"), Decimal("1000"), Decimal("2"))
    assert not policy.execution_allowed(Decimal("-2150"), Decimal("1000"), Decimal("2"))
    assert not policy.execution_allowed(Decimal("0"), Decimal("26000"), Decimal("2"))
    assert not policy.execution_allowed(Decimal("0"), Decimal("1000"), Decimal("1.9"))


def test_objective_does_not_force_trade():
    broker = FakeBroker()
    with pytest.raises(ExecutionError):
        RootExecutionEngine(broker).submit(make_approved(), ExecutionMandate("m", "c1", "NBIS", "BUY", Decimal("2"), Decimal("25")), AlgoRiskPolicy(), Decimal("-2150"), Decimal("0"), Decimal("3"))