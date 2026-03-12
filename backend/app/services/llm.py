from __future__ import annotations

from abc import ABC, abstractmethod

from backend.app.services.aws_clients import AwsClientBundle
from backend.app.safety.guardrails import build_response_system_prompt


class LLMAdapter(ABC):
    @abstractmethod
    async def generate(self, text: str, system_context: str = "") -> str:
        raise NotImplementedError


class MockLLMAdapter(LLMAdapter):
    async def generate(self, text: str, system_context: str = "") -> str:
        return f"assistant:{text}"


class AwsBedrockAdapter(LLMAdapter):
    def __init__(self, clients: AwsClientBundle, model_id: str | None = None) -> None:
        self._clients = clients
        self._model_id = model_id or "anthropic.claude-3-haiku-20240307-v1:0"

    async def generate(self, text: str, system_context: str = "") -> str:
        if not text:
            return ""
        return f"aws-assistant:{text}"


class RAGLLMAdapter(LLMAdapter):
    """
    Extends LLMAdapter with RAG context retrieval before every Bedrock call.
    Injects top-3 FAQ chunks into Bedrock Converse API "system" prompt field.
    Per CONTEXT.md locked decision: context in system prompt, NOT prepended to user message.
    """

    def __init__(self, knowledge_adapter, bedrock_client, model_id: str) -> None:
        self._knowledge = knowledge_adapter
        self._bedrock = bedrock_client
        self._model_id = model_id

    async def generate(self, query: str, system_context: str = "") -> str:
        import asyncio
        # Step 1: Retrieve top-3 FAQ chunks
        knowledge_result = await self._knowledge.retrieve(query, top_k=3)

        # Step 2: Build system prompt with FAQ context and source attribution
        if knowledge_result.chunks:
            faq_context = "\n\n".join([
                f"[Source: {src}]\n{chunk}"
                for chunk, src in zip(knowledge_result.chunks, knowledge_result.sources)
            ])
            rag_system_prompt = (
                "You are a helpful Jackson County government assistant. "
                "Answer questions using ONLY the official FAQ information provided below. "
                "Always cite the source document when giving information.\n\n"
                f"=== Official Jackson County FAQ Information ===\n{faq_context}\n"
                "=== End of FAQ Information ===\n\n"
                "If the answer is not in the FAQ information, say so clearly and suggest "
                "the resident visit jacksongov.org or call the relevant department."
            )
        else:
            rag_system_prompt = (
                "You are a helpful Jackson County government assistant. "
                "I could not find relevant FAQ information for this query. "
                "Tell the user you cannot find specific information and suggest they "
                "visit jacksongov.org or call 816-881-3000."
            )

        # Step 3: Apply guardrail rules to system prompt
        rag_system_prompt = build_response_system_prompt(rag_system_prompt)

        # Step 4: Call Bedrock Converse API with system prompt injection
        request: dict = {
            "modelId": self._model_id,
            "system": [{"text": rag_system_prompt}],
            "messages": [{"role": "user", "content": [{"text": query}]}],
        }
        response = await asyncio.to_thread(
            self._bedrock.converse, **request
        )
        return response["output"]["message"]["content"][0]["text"]
