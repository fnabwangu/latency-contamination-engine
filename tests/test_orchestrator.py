import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from eig import InformationValue, OpportunityClock, ResearchDecision, ResearchTask, run_research


def test_research_tasks_run_concurrently_and_stop_after_deadline():
    now = datetime.now(timezone.utc)
    clock = OpportunityClock(now + timedelta(minutes=5))
    value = InformationValue(Decimal("0.8"), Decimal("100"), Decimal("1"), Decimal("0"))
    started = []

    async def task(name):
        started.append(name)
        await asyncio.sleep(0)
        return name

    tasks = (ResearchTask("a", "A", lambda: task("A")), ResearchTask("b", "B", lambda: task("B")))
    result = asyncio.run(run_research(tasks, clock, value, now))
    assert result.decision is ResearchDecision.CONTINUE
    assert result.completed_task_ids == ("a", "b")
    assert started == ["A", "B"]
    stopped = asyncio.run(run_research(tasks, clock, value, now + timedelta(minutes=6)))
    assert stopped.decision is ResearchDecision.STOP
    assert stopped.completed_task_ids == ()