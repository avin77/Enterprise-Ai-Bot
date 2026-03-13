import logging
import os

from backend.app.agents.llm_adapter import AgentLLMAdapter
from backend.app.orchestrator.pipeline import VoicePipeline
from backend.app.services.asr import ASRAdapter, AwsTranscribeAdapter, MockASRAdapter
from backend.app.services.aws_clients import build_aws_clients
from backend.app.services.knowledge import DynamoKnowledgeAdapter, MockKnowledgeAdapter
from backend.app.services.llm import AwsBedrockAdapter, LLMAdapter, MockLLMAdapter, RAGLLMAdapter
from backend.app.services.tts import AwsPollyAdapter, MockTTSAdapter, TTSAdapter

logger = logging.getLogger(__name__)


def _use_mocks() -> bool:
    return os.getenv("USE_AWS_MOCKS", "true").lower() in {"1", "true", "yes"}


def _use_agents() -> bool:
    """Return True if USE_AGENTS env var is set to a truthy value.

    Rollback: set USE_AGENTS=false to instantly revert to RAGLLMAdapter
    without a code redeploy.
    """
    return os.getenv("USE_AGENTS", "false").lower() in {"1", "true", "yes"}


def build_pipeline() -> VoicePipeline:
    """Build the VoicePipeline with the appropriate LLM adapter.

    Adapter selection (in priority order):
    1. If USE_AWS_MOCKS=true (default): MockLLMAdapter — no real AWS calls
    2. Else if USE_AGENTS=true: AgentLLMAdapter — multi-agent routing (Phase 1.5)
    3. Else: RAGLLMAdapter — Phase 1 BM25 + Bedrock (stable fallback)
    """
    clients = build_aws_clients()

    if _use_mocks():
        asr: ASRAdapter = MockASRAdapter()
        llm: LLMAdapter = MockLLMAdapter()
        tts: TTSAdapter = MockTTSAdapter()
        knowledge = MockKnowledgeAdapter()
        logger.info("build_pipeline: USE_AWS_MOCKS=true — using mock adapters")
    else:
        asr = AwsTranscribeAdapter(clients)
        tts = AwsPollyAdapter(clients)
        knowledge = DynamoKnowledgeAdapter(
            table_name=os.getenv("KNOWLEDGE_TABLE", "voicebot-faq-knowledge"),
            region=os.getenv("AWS_REGION", "ap-south-1"),
            redis_url=os.getenv("REDIS_URL"),
        )

        use_agents = _use_agents()
        if use_agents:
            logger.info(
                "build_pipeline: USE_AGENTS=true — building AgentLLMAdapter "
                "(multi-agent routing enabled)"
            )
            llm = AgentLLMAdapter(knowledge, clients)
        else:
            logger.info(
                "build_pipeline: USE_AGENTS=false — building RAGLLMAdapter "
                "(Phase 1 RAG mode)"
            )
            llm = RAGLLMAdapter(
                knowledge_adapter=knowledge,
                bedrock_client=clients.bedrock_runtime,
                model_id=os.getenv(
                    "LLM_MODEL_ID",
                    "anthropic.claude-3-5-haiku-20241022-v1:0",
                ),
            )

    return VoicePipeline(asr=asr, llm=llm, tts=tts, knowledge=knowledge)

