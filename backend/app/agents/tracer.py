"""
Agent trace event emission and intent confusion matrix tracking.

Trace events flow to CloudWatch Logs via Python logging (ECS awslogs driver).
Trace events contain metadata only — no PII user query/response text.

CloudWatch Logs Insights queries:
    fields @timestamp, intent, intent_confidence, routing_target, fallback_triggered
    | filter event_type = "agent_trace"
    | stats count() by intent
    | sort count desc

    fields @timestamp, intent, fallback_triggered, total_latency_ms
    | filter event_type = "agent_trace" and fallback_triggered = true
    | stats count() as fallback_count, avg(total_latency_ms) as avg_latency

    fields @timestamp, grounding_signal, grounded
    | filter event_type = "agent_trace"
    | stats count() by grounding_signal
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Logger: ECS awslogs driver picks up all stdout/stderr via Python logging.
# voicebot.traces → distinct log stream for CloudWatch Logs Insights queries.
logger = logging.getLogger("voicebot.traces")


# ---------------------------------------------------------------------------
# TraceEvent dataclass
# ---------------------------------------------------------------------------

@dataclass
class TraceEvent:
    """
    Metadata-only trace event emitted after each voice turn.

    No PII fields: user_query and response_text are NOT included.
    Intent label, routing decisions, token counts, latencies, doc IDs only.
    """
    event_type: str = "agent_trace"
    session_id: str = ""
    turn_id: str = ""
    intent: str = ""
    intent_confidence: float = 0.0
    routing_target: str = "retrieval"         # retrieval | tool | fallback
    retrieved_doc_ids: List[str] = field(default_factory=list)
    llm_prompt_tokens: int = 0                # cumulative across all agent calls
    llm_response_tokens: int = 0
    llm_latency_ms: int = 0                   # total LLM time, not including retrieval
    tool_calls: List[dict] = field(default_factory=list)  # tool name + result, no sensitive data
    total_latency_ms: int = 0                 # full turn time
    grounded: bool = True                     # response cites sources
    grounding_signal: str = "unknown"         # has_source_attribution | no_sources | ambiguous
    fallback_triggered: bool = False
    timestamp: str = ""                       # ISO 8601 with Z, set at emit time


# ---------------------------------------------------------------------------
# emit_trace_event
# ---------------------------------------------------------------------------

async def emit_trace_event(
    session_id: str,
    turn_id: str,
    intent: str,
    intent_confidence: float,
    routing_target: str,
    retrieved_doc_ids: List[str],
    llm_prompt_tokens: int,
    llm_response_tokens: int,
    llm_latency_ms: int,
    tool_calls: List[dict],
    total_latency_ms: int,
    fallback_triggered: bool,
    grounded: bool = True,
    grounding_signal: str = "unknown",
) -> None:
    """
    Emit a metadata-only trace event to CloudWatch Logs via Python logging.

    Call via asyncio.create_task(emit_trace_event(...)) for fire-and-forget.
    Never raises — logging failures are swallowed to avoid crashing voice turns.

    Args:
        session_id: Caller session identifier (no PII).
        turn_id: Unique turn identifier (UUID).
        intent: Detected intent label (e.g. property_tax, utility_services).
        intent_confidence: Float 0-1 from orchestrator routing decision.
        routing_target: One of "retrieval", "tool", "fallback".
        retrieved_doc_ids: List of source document IDs from retrieval stage.
        llm_prompt_tokens: Cumulative input tokens across all Bedrock calls.
        llm_response_tokens: Cumulative output tokens across all Bedrock calls.
        llm_latency_ms: Total time spent in Bedrock calls (ms).
        tool_calls: List of {tool_name, result} dicts — no user data.
        total_latency_ms: Full turn latency from input to TTS (ms).
        fallback_triggered: True if confidence < 0.7 forced retrieval fallback.
        grounded: True if response contains source attribution.
        grounding_signal: Descriptor for how grounding was determined.
    """
    try:
        event = TraceEvent(
            session_id=session_id,
            turn_id=turn_id,
            intent=intent,
            intent_confidence=intent_confidence,
            routing_target=routing_target,
            retrieved_doc_ids=retrieved_doc_ids,
            llm_prompt_tokens=llm_prompt_tokens,
            llm_response_tokens=llm_response_tokens,
            llm_latency_ms=llm_latency_ms,
            tool_calls=tool_calls,
            total_latency_ms=total_latency_ms,
            grounded=grounded,
            grounding_signal=grounding_signal,
            fallback_triggered=fallback_triggered,
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        logger.info(json.dumps(asdict(event)))
    except Exception as exc:
        # Best-effort: logging failures must not crash voice processing
        try:
            logger.error("emit_trace_event failed: %s", exc)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# IntentConfusionMatrix
# ---------------------------------------------------------------------------

class IntentConfusionMatrix:
    """
    Track and compute per-intent precision and recall from eval runs.

    Precision: Of all turns where the model predicted intent X, how many were correct?
               precision = TP / (TP + FP)

    Recall: Of all turns with gold label intent X, how many did the model predict correctly?
            recall = TP / (TP + FN)

    Usage:
        matrix = IntentConfusionMatrix()
        matrix.add_prediction("turn1", predicted="property_tax", gold_label="property_tax")
        matrix.add_prediction("turn2", predicted="utility_services", gold_label="utility_services")
        matrix.add_prediction("turn3", predicted="property_tax", gold_label="permits")  # wrong
        metrics = matrix.compute_metrics()
        # {"property_tax": {"precision": 0.5, "recall": 1.0, ...}, ...}
    """

    def __init__(self) -> None:
        self.gold_labels: Dict[str, str] = {}       # turn_id → expected intent
        self.predictions: Dict[str, str] = {}        # turn_id → predicted intent

    def add_prediction(
        self,
        turn_id: str,
        predicted: str,
        gold_label: Optional[str] = None,
    ) -> None:
        """
        Record a prediction for a turn.

        Args:
            turn_id: Unique turn identifier.
            predicted: Model's predicted intent label.
            gold_label: Ground-truth intent label (required for metrics).
                        If None, prediction is recorded but won't contribute to metrics.
        """
        self.predictions[turn_id] = predicted
        if gold_label is not None:
            self.gold_labels[turn_id] = gold_label

    def compute_metrics(self) -> Dict[str, Dict[str, float]]:
        """
        Compute per-intent precision and recall.

        Returns:
            Dict mapping intent label → {precision, recall, f1, support_gold, support_pred}
        """
        # Only consider turns with both gold label and prediction
        evaluated_turns = [
            t for t in self.predictions
            if t in self.gold_labels
        ]

        if not evaluated_turns:
            return {}

        # Accumulate per-intent counts
        tp: Dict[str, int] = defaultdict(int)   # correct predictions
        fp: Dict[str, int] = defaultdict(int)   # predicted X but gold != X
        fn: Dict[str, int] = defaultdict(int)   # gold was X but predicted != X
        gold_support: Dict[str, int] = defaultdict(int)
        pred_support: Dict[str, int] = defaultdict(int)

        for turn_id in evaluated_turns:
            pred = self.predictions[turn_id]
            gold = self.gold_labels[turn_id]
            pred_support[pred] += 1
            gold_support[gold] += 1
            if pred == gold:
                tp[pred] += 1
            else:
                fp[pred] += 1
                fn[gold] += 1

        # Collect all intent labels seen
        all_intents = set(gold_support.keys()) | set(pred_support.keys())

        result: Dict[str, Dict[str, float]] = {}
        for intent in all_intents:
            p_denom = tp[intent] + fp[intent]
            r_denom = tp[intent] + fn[intent]
            precision = tp[intent] / p_denom if p_denom > 0 else 0.0
            recall = tp[intent] / r_denom if r_denom > 0 else 0.0
            f1_denom = precision + recall
            f1 = 2 * precision * recall / f1_denom if f1_denom > 0 else 0.0
            result[intent] = {
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
                "support_gold": gold_support[intent],
                "support_pred": pred_support[intent],
            }

        return result

    def publish_to_cloudwatch(
        self,
        region: str = "ap-south-1",
        namespace: str = "voicebot/agents",
    ) -> None:
        """
        Publish per-intent precision/recall metrics to CloudWatch.

        Fire-and-forget: never raises. Intended to be called after eval runs.
        No-op when boto3 unavailable or CloudWatch call fails.

        Args:
            region: AWS region for CloudWatch client.
            namespace: CloudWatch namespace (default: voicebot/agents).
        """
        metrics_data = self.compute_metrics()
        if not metrics_data:
            return

        try:
            import boto3
            cw = boto3.client("cloudwatch", region_name=region)
            metric_data = []
            for intent, m in metrics_data.items():
                dims = [{"Name": "Intent", "Value": intent}]
                metric_data.extend([
                    {
                        "MetricName": f"IntentPrecision",
                        "Dimensions": dims,
                        "Value": m["precision"],
                        "Unit": "None",
                    },
                    {
                        "MetricName": f"IntentRecall",
                        "Dimensions": dims,
                        "Value": m["recall"],
                        "Unit": "None",
                    },
                    {
                        "MetricName": f"IntentF1",
                        "Dimensions": dims,
                        "Value": m["f1"],
                        "Unit": "None",
                    },
                ])
            # CloudWatch allows max 20 MetricData items per call
            for i in range(0, len(metric_data), 20):
                cw.put_metric_data(
                    Namespace=namespace,
                    MetricData=metric_data[i:i + 20],
                )
            logger.info(
                json.dumps({
                    "event_type": "confusion_matrix_published",
                    "intents": list(metrics_data.keys()),
                    "namespace": namespace,
                })
            )
        except Exception as exc:
            try:
                logger.warning("IntentConfusionMatrix CloudWatch publish failed: %s", exc)
            except Exception:
                pass
