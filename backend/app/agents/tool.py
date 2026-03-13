"""
ToolAgent — abstract interface + MockToolAgent with canned responses.

Phase 1.5: MockToolAgent returns deterministic canned data for 3 intents.
Used to test the tool routing path without calling real Jackson County APIs.

Phase 5 upgrade path:
    Replace MockToolAgent with RealToolAgent that:
    - Calls actual Jackson County APIs for property lookup, utility status, permits
    - Handles rate limiting and authentication
    - Logs tool calls in agent traces (no sensitive data)
    - Implements retry logic with exponential backoff

CANNED_RESPONSES reference:
    property_tax    → {status: "current", amount_due: 0, next_due: "2026-04-01"}
    utility_services → {status: "active", balance: 45.23, last_payment: "2026-02-28"}
    permits         → {status: "approved", permit_id: "MOCK-2024-001", expires: "2026-12-31"}
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Canned responses — deterministic for testing and Phase 1.5 demo purposes
CANNED_RESPONSES: dict[str, dict[str, Any]] = {
    "property_tax": {
        "status": "current",
        "amount_due": 0,
        "next_due": "2026-04-01",
        "account": "MOCK-PROP-001",
    },
    "utility_services": {
        "status": "active",
        "balance": 45.23,
        "last_payment": "2026-02-28",
        "account": "MOCK-UTIL-001",
    },
    "permits": {
        "status": "approved",
        "permit_id": "MOCK-2024-001",
        "expires": "2026-12-31",
        "type": "building",
    },
}


@dataclass
class ToolResult:
    """Result of a tool execution.

    Attributes:
        tool_name: Name of the tool that was called.
        success: Whether the tool call succeeded.
        data: Returned data dict (empty on failure).
        error: Error message if success=False, else None.
        latency_ms: Simulated or actual execution time in milliseconds.
    """

    tool_name: str
    success: bool
    data: dict = field(default_factory=dict)
    error: Optional[str] = None
    latency_ms: int = 0


class ToolAgent(ABC):
    """Abstract interface for tool execution agents.

    Implementations:
    - MockToolAgent  (Phase 1.5): canned responses, 50ms simulated latency
    - RealToolAgent  (Phase 5): real Jackson County API calls
    """

    @abstractmethod
    async def execute(self, intent: str, parameters: dict) -> ToolResult:
        """Execute a tool for the given intent with provided parameters.

        Parameters
        ----------
        intent:
            The routing intent (e.g. 'property_tax', 'utility_services').
        parameters:
            Additional parameters for the tool call (account ID, filters, etc.).

        Returns
        -------
        ToolResult with success/failure status and returned data.
        """
        raise NotImplementedError


class MockToolAgent(ToolAgent):
    """Phase 1.5 mock tool agent with canned deterministic responses.

    Returns predictable data for property_tax, utility_services, and permits.
    Unknown intents return success=False with a clear error message.

    Simulated latency: 50ms (consistent with Phase 1.5 eval expectations).
    """

    async def execute(self, intent: str, parameters: dict) -> ToolResult:
        """Return canned response for the given intent.

        Parameters
        ----------
        intent:
            Intent label. Must be one of the keys in CANNED_RESPONSES.
        parameters:
            Ignored in Phase 1.5 (all data is canned).

        Returns
        -------
        ToolResult with success=True and canned data, or success=False
        for unknown intents.
        """
        if intent in CANNED_RESPONSES:
            logger.debug(
                "MockToolAgent.execute: intent=%s → canned data", intent
            )
            return ToolResult(
                tool_name=intent,
                success=True,
                data=dict(CANNED_RESPONSES[intent]),  # shallow copy
                error=None,
                latency_ms=50,
            )

        logger.warning(
            "MockToolAgent.execute: no mock data for intent=%s", intent
        )
        return ToolResult(
            tool_name=intent,
            success=False,
            data={},
            error=f"No mock data available for intent '{intent}'",
            latency_ms=50,
        )
