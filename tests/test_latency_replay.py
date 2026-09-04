from datetime import datetime, timedelta, timezone
from decimal import Decimal

from eig import OpportunityClock, InformationValue, ResearchDecision, choose_research_action
from eig.replay import orphaned_sleeve_replay, unavailable_account_replay, warning_veto_replay


def test_information_value_and_fast_lane():
    now = datetime.now(timezone.utc)
    clock = OpportunityClock(now + timedelta(hours=1))
    value = InformationValue(Decimal("0.5"), Decimal("100"), Decimal("10"), Decimal("1"))
    assert choose_research_action(clock, value, now) is ResearchDecision.CONTINUE
    assert choose_research_action(clock, value, now, fast_lane=True) is ResearchDecision.ESCALATE


def test_replays_preserve_candidates_and_rescue_sleeves():
    state, retained_proposal = unavailable_account_replay()
    assert state.value == "BLOCKED" and retained_proposal
    assert warning_veto_replay()
    assert orphaned_sleeve_replay()