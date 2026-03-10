"""
In-application resource monitoring and metrics collection.
Provides real-time CPU and memory tracking for optimization insights.
Phase 1 addition: Per-stage CloudWatch latency metrics (publish_turn_metrics, LatencyBuffer).
"""

import logging
import os
import time
from collections import deque
from datetime import datetime
from typing import Any, Optional

import psutil


class ResourceMonitor:
    """Monitor application resource usage."""

    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.start_time = time.time()
        self.metrics = {
            "startup_memory_mb": self.get_memory_mb(),
            "startup_time": datetime.now().isoformat(),
        }

    def get_memory_mb(self) -> float:
        """Get current memory usage in MB."""
        return self.process.memory_info().rss / 1024 / 1024

    def get_cpu_percent(self) -> float:
        """Get CPU usage percentage (0-100)."""
        return self.process.cpu_percent(interval=0.1)

    def get_uptime_seconds(self) -> float:
        """Get application uptime in seconds."""
        return time.time() - self.start_time

    def get_connection_count(self) -> int:
        """Get number of open connections."""
        return len(self.process.connections(kind="inet"))

    def snapshot(self) -> dict:
        """Get current resource snapshot."""
        return {
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": int(self.get_uptime_seconds()),
            "memory_mb": round(self.get_memory_mb(), 2),
            "cpu_percent": round(self.get_cpu_percent(), 2),
            "connections": self.get_connection_count(),
        }

    def check_constraints(self) -> Optional[str]:
        """Check if resources are constrained. Returns warning message or None."""
        memory_mb = self.get_memory_mb()

        # Warn if using >80% of 512MB
        if memory_mb > 400:
            return f"⚠️  Memory critical: {memory_mb:.0f}MB / 512MB allocated (80%+)"

        # Warn if using >70% of 512MB
        if memory_mb > 350:
            return f"⚠️  Memory high: {memory_mb:.0f}MB / 512MB allocated (70%+)"

        return None


# Global monitor instance
_monitor: Optional[ResourceMonitor] = None


def get_monitor() -> ResourceMonitor:
    """Get or create the global monitor."""
    global _monitor
    if _monitor is None:
        _monitor = ResourceMonitor()
    return _monitor


def log_startup_info():
    """Log startup resource information."""
    monitor = get_monitor()
    print(f"\n=== Application Startup ===")
    print(f"Memory: {monitor.metrics['startup_memory_mb']:.1f} MB")
    print(f"Allocated: 512 MB (Fargate 256 CPU + 512 MB)")
    print(f"Available: {512 - monitor.metrics['startup_memory_mb']:.1f} MB for processing")
    print(f"============================\n")


def log_resource_snapshot(label: str = ""):
    """Log current resource snapshot."""
    monitor = get_monitor()
    snapshot = monitor.snapshot()
    constraint_warning = monitor.check_constraints()

    prefix = f"[{label}] " if label else ""
    print(f"{prefix}Resources - Mem: {snapshot['memory_mb']}MB, CPU: {snapshot['cpu_percent']}%, Conn: {snapshot['connections']}")

    if constraint_warning:
        print(f"  {constraint_warning}")

    return snapshot


# ---------------------------------------------------------------------------
# Phase 1: Per-stage latency metrics (publish_turn_metrics + LatencyBuffer)
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

_SLO_MS = 1500.0  # Phase 1 SLO target


class LatencyBuffer:
    """
    Rolling in-process buffer for per-stage p50/p95/p99 latency percentiles.
    Module-level singleton — shared across requests in same process.
    Max 1000 turns rolling window.
    """

    STAGES = ("asr", "rag", "llm", "tts")

    def __init__(self, maxlen: int = 1000) -> None:
        self._data: dict[str, deque] = {s: deque(maxlen=maxlen) for s in self.STAGES}

    def record(self, result: Any) -> None:
        """Record a PipelineResult's stage timings."""
        for stage in self.STAGES:
            ms = getattr(result, f"{stage}_ms", 0.0)
            self._data[stage].append(float(ms))

    def percentiles(self, stage: str) -> dict[str, float]:
        """Return p50, p95, p99 for stage. Returns zeros if buffer empty."""
        if stage not in self.STAGES:
            raise ValueError(f"Unknown stage: {stage}. Valid: {self.STAGES}")
        data = sorted(self._data[stage])
        if not data:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
        n = len(data)
        return {
            "p50": data[int(n * 0.50)],
            "p95": data[min(int(n * 0.95), n - 1)],
            "p99": data[min(int(n * 0.99), n - 1)],
        }

    def all_percentiles(self) -> dict[str, dict[str, float]]:
        return {s: self.percentiles(s) for s in self.STAGES}


# Module-level singleton — one buffer per process (per ECS task)
_latency_buffer = LatencyBuffer()


def get_latency_buffer() -> LatencyBuffer:
    return _latency_buffer


def publish_turn_metrics(
    result: Any,
    redis_hit: bool,
    bm25_score: float,
    query_expanded: bool,
    cw_client: Optional[Any] = None,
    env: str = "prod",
) -> None:
    """
    Record turn in in-process buffer and publish to CloudWatch.
    Fire-and-forget: NEVER raises. CloudWatch failure must not fail voice turn.
    No-op for CloudWatch when USE_AWS_MOCKS=true or cw_client=None.
    Always records in local LatencyBuffer regardless.
    """
    # Always record in local buffer (regardless of CloudWatch availability)
    _latency_buffer.record(result)

    use_mocks = os.getenv("USE_AWS_MOCKS", "true").lower() in {"1", "true", "yes"}
    if cw_client is None or use_mocks:
        return  # No CloudWatch in mock/local mode — that's fine

    dims = [{"Name": "Environment", "Value": env}]
    total_ms = (
        getattr(result, "asr_ms", 0.0)
        + getattr(result, "rag_ms", 0.0)
        + getattr(result, "llm_ms", 0.0)
        + getattr(result, "tts_ms", 0.0)
    )

    try:
        # Namespace: voicebot/latency — all 5 per-stage metrics in one call
        cw_client.put_metric_data(
            Namespace="voicebot/latency",
            MetricData=[
                {"MetricName": "ASRLatency", "Value": getattr(result, "asr_ms", 0.0), "Unit": "Milliseconds", "Dimensions": dims},
                {"MetricName": "RAGLatency", "Value": getattr(result, "rag_ms", 0.0), "Unit": "Milliseconds", "Dimensions": dims},
                {"MetricName": "LLMLatency", "Value": getattr(result, "llm_ms", 0.0), "Unit": "Milliseconds", "Dimensions": dims},
                {"MetricName": "TTSLatency", "Value": getattr(result, "tts_ms", 0.0), "Unit": "Milliseconds", "Dimensions": dims},
                {"MetricName": "TotalTurnLatency", "Value": total_ms, "Unit": "Milliseconds", "Dimensions": dims},
            ],
        )
    except Exception as exc:
        logger.warning("CloudWatch latency publish failed: %s", exc)
        return  # NEVER propagate

    try:
        # Namespace: voicebot/rag — cache and BM25 quality signals
        rag_metrics = [
            {"MetricName": "CacheHits" if redis_hit else "CacheMisses", "Value": 1, "Unit": "Count", "Dimensions": dims},
            {"MetricName": "BM25TopScore", "Value": bm25_score, "Unit": "None", "Dimensions": dims},
        ]
        if query_expanded:
            rag_metrics.append({"MetricName": "QueryExpandedHits", "Value": 1, "Unit": "Count", "Dimensions": dims})
        if not redis_hit:
            rag_metrics.append({"MetricName": "FallbackToDirectBM25", "Value": 1, "Unit": "Count", "Dimensions": dims})
        cw_client.put_metric_data(Namespace="voicebot/rag", MetricData=rag_metrics)
    except Exception as exc:
        logger.warning("CloudWatch RAG metrics publish failed: %s", exc)

    try:
        # Namespace: voicebot/conversations — SLO tracking
        conv_metrics = [{"MetricName": "TurnsCompleted", "Value": 1, "Unit": "Count", "Dimensions": dims}]
        if total_ms >= _SLO_MS:
            conv_metrics.append({"MetricName": "SLOViolations", "Value": 1, "Unit": "Count", "Dimensions": dims})
        cw_client.put_metric_data(Namespace="voicebot/conversations", MetricData=conv_metrics)
    except Exception as exc:
        logger.warning("CloudWatch conversations metrics publish failed: %s", exc)
