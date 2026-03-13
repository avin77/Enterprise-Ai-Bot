"""
OrchestratorAgent — routes each user query to retrieval, tool, or fallback.

Phase 1.5: First Claude call in the multi-agent pipeline. Uses Bedrock haiku
with temperature=0 for deterministic eval reproducibility.

Routing logic:
- retrieval: informational FAQ query (property tax rates, permit requirements, etc.)
- tool: transactional lookup (my account balance, my permit status, etc.)
- fallback: out-of-scope, low-confidence (< 0.7), or ambiguous queries
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from backend.app.agents.types import Message, RoutingDecision
from backend.app.services.aws_clients import AwsClientBundle

logger = logging.getLogger(__name__)

# Haiku for routing — deterministic, low latency, low cost
_ORCHESTRATOR_MODEL = "anthropic.claude-3-5-haiku-20241022-v1:0"

_SYSTEM_PROMPT = """\
You are a routing agent for the Jackson County Government voice assistant.
Your ONLY job is to classify the user's intent and decide which agent should handle it.

INTENT LABELS (pick exactly one):
- property_tax: property tax questions, rates, assessments, payments
- utility_services: water, sewer, trash pickup, billing, account balances
- permits: building permits, applications, status, requirements
- trash_waste: trash collection, recycling, bulk pickup schedules
- voting: voter registration, polling places, election info
- court_fees: municipal court fees, fines, payment plans
- benefits: social services, assistance programs, eligibility
- parks: parks, recreation facilities, hours, programs
- emergency: emergencies (always route to fallback — cannot help via voice bot)
- general_info: general county information not fitting other categories
- out_of_scope: queries unrelated to Jackson County government services

ROUTING TARGETS:
- retrieval: informational query (user wants to KNOW something) → BM25 FAQ search
- tool: transactional query (user wants to CHECK their specific account/status) → tool lookup
- fallback: low-confidence, out-of-scope, ambiguous, emergency, or cannot determine intent

RULES:
1. Respond ONLY with valid JSON — no prose, no markdown.
2. Set confidence = 0.0 to 1.0 (your certainty this routing is correct).
3. If confidence < 0.7, set routing_target = "fallback".
4. Emergencies ALWAYS route to fallback.
5. Reasoning must be one sentence.

OUTPUT FORMAT (strict JSON):
{
  "intent": "<intent_label>",
  "confidence": <float 0-1>,
  "routing_target": "<retrieval|tool|fallback>",
  "reasoning": "<one sentence>"
}
"""


class OrchestratorAgent:
    """Routes a user query to the appropriate downstream agent.

    Parameters
    ----------
    aws_clients:
        AwsClientBundle providing access to bedrock_runtime.
    """

    def __init__(self, aws_clients: AwsClientBundle) -> None:
        self._clients = aws_clients
        self._model_id = _ORCHESTRATOR_MODEL

    def _bedrock(self):
        """Lazy access to bedrock-runtime client."""
        return self._clients.bedrock_runtime

    async def route(
        self, query: str, history: Optional[list[Message]] = None
    ) -> RoutingDecision:
        """Classify intent and return a routing decision.

        Parameters
        ----------
        query:
            The current user utterance.
        history:
            Recent conversation turns (up to last 5 used for context).

        Returns
        -------
        RoutingDecision with intent, confidence, routing_target, reasoning.
        Confidence < 0.7 is coerced to routing_target = 'fallback'.
        """
        if history is None:
            history = []

        # Build messages: last 5 history turns + current query
        messages = []
        for msg in history[-5:]:
            messages.append({
                "role": msg.role,
                "content": [{"text": msg.content}],
            })
        messages.append({"role": "user", "content": [{"text": query}]})

        request = {
            "modelId": self._model_id,
            "system": [{"text": _SYSTEM_PROMPT}],
            "messages": messages,
            "inferenceConfig": {
                "temperature": 0,
                "maxTokens": 150,
            },
        }

        try:
            response = await asyncio.to_thread(
                self._bedrock().converse, **request
            )
            response_text = response["output"]["message"]["content"][0]["text"]
        except Exception as exc:
            logger.error(
                "OrchestratorAgent: Bedrock call failed for query=%r: %s",
                query[:80],
                exc,
            )
            return RoutingDecision(
                intent="error",
                confidence=0.0,
                routing_target="fallback",
                reasoning="Bedrock call failed — routing to safe fallback",
            )

        # Parse JSON routing decision
        try:
            # Strip any markdown fences if model wraps response
            clean = response_text.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
                clean = clean.strip()
            decision = RoutingDecision.model_validate_json(clean)
        except Exception as exc:
            logger.error(
                "OrchestratorAgent: JSON parse failed: %s | raw=%r",
                exc,
                response_text[:200],
            )
            return RoutingDecision(
                intent="error",
                confidence=0.0,
                routing_target="fallback",
                reasoning="JSON parse error — routing to safe fallback",
            )

        # Enforce fallback for low-confidence decisions
        if decision.confidence < 0.7:
            logger.info(
                "OrchestratorAgent: confidence=%.2f < 0.7, coercing to fallback "
                "(original target=%s, intent=%s)",
                decision.confidence,
                decision.routing_target,
                decision.intent,
            )
            decision.routing_target = "fallback"

        return decision
