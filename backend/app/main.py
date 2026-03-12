import datetime
import logging
import os
from base64 import b64decode
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status

from backend.app.api.chat import router as chat_router
from backend.app.monitoring import get_latency_buffer, publish_turn_metrics
from backend.app.orchestrator.runtime import build_pipeline
from backend.app.schemas.messages import WsClientMessage, WsServerMessage
from backend.app.security.auth import validate_websocket_token
from backend.app.security.rate_limit import limiter
from backend.app.services.conversation import ConversationSession, write_conversation_turn

logger = logging.getLogger(__name__)

app = FastAPI(title="Enterprise AI Voice Bot", version="0.1.0")
app.include_router(chat_router)
pipeline = build_pipeline()

_USE_MOCKS = os.getenv("USE_AWS_MOCKS", "true").lower() in {"1", "true", "yes"}


def _get_dynamo_client():
    """Return a boto3 DynamoDB client, or None if in mock mode."""
    if _USE_MOCKS:
        return None
    try:
        import boto3
        return boto3.client("dynamodb", region_name=os.getenv("AWS_REGION", "ap-south-1"))
    except Exception:
        logger.warning("Failed to create DynamoDB client; conversation tracking disabled")
        return None


_dynamo_client = _get_dynamo_client()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> dict[str, Any]:
    """Return per-stage latency percentiles (p50, p95, p99) for all pipeline stages.
    Values are sourced from the in-process LatencyBuffer singleton (Plan 01-04).
    """
    return get_latency_buffer().all_percentiles()


@app.get("/api/knowledge-stats")
async def knowledge_stats() -> dict:
    """FAQ knowledge base stats — real DynamoDB or mock."""
    if _USE_MOCKS:
        return {
            "total_chunks": 12,
            "total_documents": 3,
            "last_ingested": "2026-03-11T00:00:00Z",
            "source": "mock",
        }
    try:
        paginator = _dynamo_client.get_paginator("scan")
        all_items = []
        for page in paginator.paginate(
            TableName="voicebot_faqs",
            ProjectionExpression="source_doc",
        ):
            all_items.extend(page.get("Items", []))
        docs = {item["source_doc"]["S"] for item in all_items}
        return {
            "total_chunks": len(all_items),
            "total_documents": len(docs),
            "last_ingested": None,
            "source": "dynamodb",
        }
    except Exception as e:
        logger.warning(f"knowledge-stats DynamoDB error: {e}")
        return {"total_chunks": 0, "total_documents": 0, "last_ingested": None, "source": "error"}


@app.get("/api/session-stats")
async def session_stats() -> dict:
    """Conversation session summary — real DynamoDB or mock."""
    if _USE_MOCKS:
        return {
            "active_sessions": 2,
            "total_turns": 8,
            "slo_met_pct": 87.5,
            "source": "mock",
        }
    try:
        paginator = _dynamo_client.get_paginator("scan")
        all_items = []
        for page in paginator.paginate(
            TableName="voicebot_sessions",
            ProjectionExpression="session_id, slo_met",
        ):
            all_items.extend(page.get("Items", []))
        total_turns = len(all_items)
        active_sessions = len({i["session_id"]["S"] for i in all_items if "session_id" in i})
        slo_met = sum(1 for i in all_items if i.get("slo_met", {}).get("BOOL", False))
        pct = round((slo_met / total_turns * 100) if total_turns else 0.0, 1)
        return {
            "active_sessions": active_sessions,
            "total_turns": total_turns,
            "slo_met_pct": pct,
            "source": "dynamodb",
        }
    except Exception as e:
        logger.warning(f"session-stats DynamoDB error: {e}")
        return {"active_sessions": 0, "total_turns": 0, "slo_met_pct": 0.0, "source": "error"}


@app.get("/api/cloudwatch-latency")
async def cloudwatch_latency() -> dict:
    """Recent p50/p95/p99 turn latency — in-memory buffer first, CloudWatch fallback."""
    buf = get_latency_buffer()
    pcts = buf.all_percentiles()
    total = pcts.get("total", {})
    if total.get("p50") is not None:
        return {
            "p50_ms": total["p50"],
            "p95_ms": total["p95"],
            "p99_ms": total["p99"],
            "sample_count": total.get("count", 0),
            "source": "in-memory",
        }
    if not _USE_MOCKS:
        try:
            import boto3
            cw = boto3.client("cloudwatch", region_name=os.getenv("AWS_REGION", "ap-south-1"))
            now = datetime.datetime.utcnow()
            resp = cw.get_metric_statistics(
                Namespace="voicebot/latency",
                MetricName="TotalTurnLatency",
                StartTime=now - datetime.timedelta(hours=1),
                EndTime=now,
                Period=3600,
                Statistics=["Average"],
            )
            pts = resp.get("Datapoints", [])
            avg = pts[0]["Average"] if pts else None
            return {
                "p50_ms": avg,
                "p95_ms": None,
                "p99_ms": None,
                "sample_count": len(pts),
                "source": "cloudwatch",
            }
        except Exception as e:
            logger.warning(f"cloudwatch-latency error: {e}")
    return {"p50_ms": None, "p95_ms": None, "p99_ms": None, "sample_count": 0, "source": "no-data"}


@app.websocket("/ws")
async def voice_ws(websocket: WebSocket) -> None:
    try:
        token = await validate_websocket_token(websocket)
        limiter.check(f"/ws:{token}")
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    await websocket.send_json(WsServerMessage(type="ack", text="connected").model_dump())

    # One ConversationSession per WebSocket connection — tracks session_id and turn_number.
    # Conversation turns are written AFTER pipeline result is returned (pipeline.py stays pure).
    session = ConversationSession()

    try:
        while True:
            raw = await websocket.receive_json()
            incoming = WsClientMessage.model_validate(raw)
            if incoming.type == "text" and incoming.text:
                result = await pipeline.run_text_turn(incoming.text)
                publish_turn_metrics(
                    result=result,
                    redis_hit=False,   # TODO Phase 2: wire actual redis_hit from knowledge adapter
                    bm25_score=getattr(result, "top_score", 0.0),
                    query_expanded=False,  # TODO Phase 2: wire from knowledge adapter
                    cw_client=None,    # TODO Phase 3: wire actual CloudWatch client
                )
                await websocket.send_json(WsServerMessage(type="bot_text", text=result.response_text).model_dump())
                if _dynamo_client is not None:
                    try:
                        write_conversation_turn(
                            dynamo_client=_dynamo_client,
                            session=session,
                            user_input=incoming.text,
                            assistant_response=result.response_text,
                            pipeline_result=result,
                            rag_chunk_ids=result.chunk_ids or None,
                        )
                    except Exception:
                        logger.warning("Failed to write conversation turn to DynamoDB", exc_info=True)
            elif incoming.type == "audio_chunk" and incoming.audio_base64:
                audio_bytes = b64decode(incoming.audio_base64.encode("utf-8"))
                result = await pipeline.run_roundtrip(audio_bytes)
                publish_turn_metrics(
                    result=result,
                    redis_hit=False,   # TODO Phase 2: wire actual redis_hit from knowledge adapter
                    bm25_score=getattr(result, "top_score", 0.0),
                    query_expanded=False,  # TODO Phase 2: wire from knowledge adapter
                    cw_client=None,    # TODO Phase 3: wire actual CloudWatch client
                )
                await websocket.send_json(
                    WsServerMessage(type="partial_text", text=result.transcript).model_dump()
                )
                await websocket.send_json(
                    WsServerMessage(type="bot_text", text=result.response_text).model_dump()
                )
                await websocket.send_json(
                    WsServerMessage(
                        type="bot_audio_chunk",
                        audio_base64=result.response_audio.decode("utf-8"),
                    ).model_dump()
                )
                if _dynamo_client is not None:
                    try:
                        write_conversation_turn(
                            dynamo_client=_dynamo_client,
                            session=session,
                            user_input=result.transcript,
                            assistant_response=result.response_text,
                            pipeline_result=result,
                            rag_chunk_ids=result.chunk_ids or None,
                        )
                    except Exception:
                        logger.warning("Failed to write conversation turn to DynamoDB", exc_info=True)
            elif incoming.type == "end":
                await websocket.send_json(WsServerMessage(type="ack", text="closed").model_dump())
                await websocket.close()
                break
    except WebSocketDisconnect:
        return
