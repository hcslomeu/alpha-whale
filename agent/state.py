"""Custom agent state extending LangGraph's MessagesState.

Adds domain-specific fields for risk assessment and trade signal tracking
on top of the built-in message accumulation behavior.
"""

from __future__ import annotations

from operator import add
from typing import Annotated

from langgraph.graph import MessagesState

from agent.models import RiskLevel, TradeSignal


class AgentState(MessagesState):
    """Extended state for the AlphaWhale trading agent.

    Inherits ``messages`` from MessagesState (with ``add_messages`` reducer).
    Custom fields use simple defaults so the graph starts with clean state.
    """

    risk_level: RiskLevel
    trade_signals: Annotated[list[TradeSignal], add]
    pending_approval: bool
