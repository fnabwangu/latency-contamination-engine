"""Concurrent research orchestration with deadline-aware stopping."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Awaitable, Callable, Iterable

from .latency import InformationValue, OpportunityClock, ResearchDecision, choose_research_action


@dataclass(frozen=True)
class ResearchTask:
    task_id: str
    agent_id: str
    run: Callable[[], Awaitable[object]]


@dataclass(frozen=True)
class OrchestrationResult:
    decision: ResearchDecision
    completed_task_ids: tuple[str, ...]
    results: tuple[object, ...]
    deadline: datetime


async def run_research(
    tasks: Iterable[ResearchTask],
    clock: OpportunityClock,
    value: InformationValue,
    now: datetime,
    required_unknowns: bool = False,
    fast_lane: bool = False,
) -> OrchestrationResult:
    decision = choose_research_action(clock, value, now, required_unknowns, fast_lane)
    if decision is ResearchDecision.STOP:
        return OrchestrationResult(decision, (), (), clock.effective_deadline)
    selected = tuple(tasks)
    if decision is ResearchDecision.ESCALATE:
        selected = selected[: max(1, min(3, len(selected)))]
    gathered = await asyncio.gather(*(task.run() for task in selected), return_exceptions=False)
    return OrchestrationResult(decision, tuple(task.task_id for task in selected), tuple(gathered), clock.effective_deadline)