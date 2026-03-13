"""
ResponseAgent — grounded answer synthesis using Claude Sonnet.

Phase 1.5: Final agent in the pipeline. Takes retrieved chunks + user query
and synthesizes a grounded voice-friendly response.

Grounding rules (enforced in system prompt):
- ONLY state facts from provided context chunks
- Cite source document: "According to [source_doc], ..."
- No bullet points or numbered lists (voice delivery)
- Keep under 3 sentences
- max_tokens=300 for voice-friendly length
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from backend.app.agents.retrieval import ChunkResult
from backend.app.agents.types import Message
from backend.app.safety.guardrails import build_response_system_prompt
from backend.app.services.aws_clients import AwsClientBundle

logger = logging.getLogger(__name__)

# Sonnet for response synthesis — richer reasoning, grounded citations
_RESPONSE_MODEL = "anthropic.claude-sonnet-4-20250514-v1:0"

_BASE_SYSTEM_PROMPT = """\
You are a helpful Jackson County Government voice assistant.
Answer questions ONLY using the context chunks provided below.

GROUNDING RULES:
1. ONLY state facts that appear in the provided context chunks. Do not add information.
2. ALWAYS cite the source document for every factual claim:
   "According to [source_doc], ..."
3. If the context does not answer the question, say:
   "I don't have that specific information. You can contact Jackson County at 816-881-3000."
4. Do NOT use bullet points or numbered lists — this is a voice response.
5. Keep your response under 3 sentences for voice delivery.
6. Do not ask follow-up questions.
"""


class ResponseAgent:
    """Synthesizes a grounded voice response from retrieved FAQ chunks.

    Parameters
    ----------
    aws_clients:
        AwsClientBundle providing access to bedrock_runtime.
    """

    def __init__(self, aws_clients: AwsClientBundle) -> None:
        self._clients = aws_clients
        self._model_id = _RESPONSE_MODEL

    def _bedrock(self):
        """Lazy access to bedrock-runtime client."""
        return self._clients.bedrock_runtime

    def _build_system_prompt(self) -> str:
        """Build system prompt with grounding rules + Phase 2 guardrails."""
        return build_response_system_prompt(_BASE_SYSTEM_PROMPT)

    def _format_chunks(self, chunks: list[ChunkResult]) -> str:
        """Format chunk list for injection into user message."""
        if not chunks:
            return "[No context chunks available]"
        parts = []
        for chunk in chunks:
            parts.append(f"[CHUNK: {chunk.source_doc} | {chunk.text}]")
        return "\n\n".join(parts)

    async def synthesize(
        self,
        query: str,
        chunks: list[ChunkResult],
        history: Optional[list[Message]] = None,
    ) -> str:
        """Synthesize a grounded response from retrieved chunks.

        Parameters
        ----------
        query:
            The user's question.
        chunks:
            Retrieved FAQ chunks from RetrievalAgent.
        history:
            Recent conversation turns (last 5 used for context).

        Returns
        -------
        Grounded response string. Falls back to safe error message on Bedrock failure.
        """
        if history is None:
            history = []

        system_prompt = self._build_system_prompt()
        chunks_text = self._format_chunks(chunks)

        # Build user message with embedded context chunks
        user_content = (
            f"CONTEXT CHUNKS:\n{chunks_text}\n\n"
            f"USER QUESTION: {query}"
        )

        # Build messages: last 5 history turns + current user message
        messages = []
        for msg in history[-5:]:
            messages.append({
                "role": msg.role,
                "content": [{"text": msg.content}],
            })
        messages.append({"role": "user", "content": [{"text": user_content}]})

        request = {
            "modelId": self._model_id,
            "system": [{"text": system_prompt}],
            "messages": messages,
            "inferenceConfig": {
                "temperature": 0,
                "maxTokens": 300,  # Hard limit for voice-friendly output
            },
        }

        try:
            response = await asyncio.to_thread(
                self._bedrock().converse, **request
            )
            return response["output"]["message"]["content"][0]["text"]
        except Exception as exc:
            logger.error(
                "ResponseAgent: Bedrock call failed for query=%r: %s",
                query[:80],
                exc,
            )
            return "I'm having trouble processing that request. Please try again."
