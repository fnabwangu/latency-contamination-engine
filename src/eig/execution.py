"""Execution authority boundary.

Only ``RootExecutionEngine`` accepts a broker adapter. Other components can
create proposals, but cannot submit orders.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Protocol

from .coordinator import ExecutionProposal


class ExecutionError(ValueError):
    """A proposal failed an execution or authorization control."""


class OrderStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class ExecutionMandate:
    mandate_id: str
    candidate_id: str
    instrument: str
    side: str
    max_quantity: Decimal
    max_absolute_loss: Decimal


@dataclass(frozen=True)
class OrderReceipt:
    proposal_id: str
    status: OrderStatus
    broker_order_id: str | None = None
    reason: str = ""


class BrokerAdapter(Protocol):
    def submit(self, proposal: ExecutionProposal) -> OrderReceipt:
        """Submit an already authorized proposal to an external broker."""


class RootExecutionEngine:
    """The sole boundary allowed to call a broker adapter."""

    def __init__(self, broker: BrokerAdapter | None = None) -> None:
        self.broker = broker

    def submit(self, proposal: ExecutionProposal, mandate: ExecutionMandate) -> OrderReceipt:
        if self.broker is None:
            raise ExecutionError("no broker adapter configured")
        if proposal.state != "APPROVED":
            raise ExecutionError("exact human approval is required before execution")
        if proposal.candidate_id != mandate.candidate_id:
            raise ExecutionError("proposal is outside the approved candidate mandate")
        if proposal.instrument != mandate.instrument or proposal.side != mandate.side:
            raise ExecutionError("proposal instrument or side is outside the mandate")
        if proposal.quantity > mandate.max_quantity:
            raise ExecutionError("proposal quantity exceeds mandate")
        if proposal.absolute_loss > mandate.max_absolute_loss:
            raise ExecutionError("proposal loss exceeds mandate")
        return self.broker.submit(proposal)