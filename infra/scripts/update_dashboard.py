#!/usr/bin/env python
"""
Update voice-bot-mvp-operations CloudWatch dashboard with Phase 1 metrics.
Adds 5 widgets to the existing 10-widget Phase 0 dashboard.

Usage:
    python infra/scripts/update_dashboard.py          # dry run (USE_AWS_MOCKS=true)
    USE_AWS_MOCKS=false python infra/scripts/update_dashboard.py  # live update
"""
import json
import os
import sys

DASHBOARD_NAME = "voice-bot-mvp-operations"
REGION = "ap-south-1"

# 5 new Phase 1 widgets appended to existing dashboard
PHASE1_WIDGETS = [
    {
        "type": "metric", "x": 0, "y": 18, "width": 12, "height": 6,
        "properties": {
            "title": "Turn Latency -- p50/p95 per Stage (ms)",
            "view": "timeSeries", "stat": "p95", "period": 60,
            "region": REGION,
            "metrics": [
                ["voicebot/latency", "ASRLatency",       "Environment", "prod", {"label": "ASR p95",   "stat": "p95"}],
                ["voicebot/latency", "RAGLatency",       "Environment", "prod", {"label": "RAG p95",   "stat": "p95"}],
                ["voicebot/latency", "LLMLatency",       "Environment", "prod", {"label": "LLM p95",   "stat": "p95"}],
                ["voicebot/latency", "TTSLatency",       "Environment", "prod", {"label": "TTS p95",   "stat": "p95"}],
                ["voicebot/latency", "TotalTurnLatency", "Environment", "prod", {"label": "Total p95", "stat": "p95", "color": "#d62728"}],
            ],
            "annotations": {"horizontal": [{"value": 1500, "label": "SLO 1500ms", "color": "#d62728"}]},
        }
    },
    {
        "type": "metric", "x": 12, "y": 18, "width": 12, "height": 6,
        "properties": {
            "title": "Total Turn Latency -- p50 vs p95 (ms)",
            "view": "timeSeries", "period": 60, "region": REGION,
            "metrics": [
                ["voicebot/latency", "TotalTurnLatency", "Environment", "prod", {"label": "Total p50", "stat": "p50"}],
                ["voicebot/latency", "TotalTurnLatency", "Environment", "prod", {"label": "Total p95", "stat": "p95"}],
                ["voicebot/latency", "TotalTurnLatency", "Environment", "prod", {"label": "Total p99", "stat": "p99"}],
            ],
            "annotations": {"horizontal": [{"value": 1500, "label": "SLO", "color": "#d62728"}]},
        }
    },
    {
        "type": "metric", "x": 0, "y": 24, "width": 8, "height": 6,
        "properties": {
            "title": "RAG Cache Hits vs Misses",
            "view": "timeSeries", "stat": "Sum", "period": 300, "region": REGION,
            "metrics": [
                ["voicebot/rag", "CacheHits",   "Environment", "prod", {"label": "Cache Hits",   "color": "#2ca02c"}],
                ["voicebot/rag", "CacheMisses",  "Environment", "prod", {"label": "Cache Misses", "color": "#ff7f0e"}],
                ["voicebot/rag", "FallbackToDirectBM25", "Environment", "prod", {"label": "Redis Fallback", "color": "#d62728"}],
            ],
        }
    },
    {
        "type": "metric", "x": 8, "y": 24, "width": 8, "height": 6,
        "properties": {
            "title": "BM25 Top Score (RAG Relevance)",
            "view": "timeSeries", "stat": "Average", "period": 60, "region": REGION,
            "metrics": [
                ["voicebot/rag", "BM25TopScore", "Environment", "prod", {"label": "BM25 Score avg"}],
            ],
        }
    },
    {
        "type": "metric", "x": 16, "y": 24, "width": 8, "height": 6,
        "properties": {
            "title": "SLO Violations + Turns Completed",
            "view": "timeSeries", "stat": "Sum", "period": 300, "region": REGION,
            "metrics": [
                ["voicebot/conversations", "TurnsCompleted", "Environment", "prod", {"label": "Turns",          "color": "#1f77b4"}],
                ["voicebot/conversations", "SLOViolations",  "Environment", "prod", {"label": "SLO Violations", "color": "#d62728"}],
            ],
        }
    },
]


def add_phase1_widgets(dry_run: bool = True) -> dict:
    """
    Fetch existing dashboard, append Phase 1 widgets, put back.
    dry_run=True: print new body, do not call AWS.
    """
    if dry_run:
        # Build a synthetic body (no existing widgets in dry run)
        body = {"widgets": []}
    else:
        import boto3
        cw = boto3.client("cloudwatch", region_name=REGION)
        resp = cw.get_dashboard(DashboardName=DASHBOARD_NAME)
        body = json.loads(resp["DashboardBody"])

    # Append Phase 1 widgets (preserves existing)
    body["widgets"].extend(PHASE1_WIDGETS)

    if dry_run:
        print(f"DRY RUN -- would add {len(PHASE1_WIDGETS)} widgets to {DASHBOARD_NAME}")
        print(json.dumps({"new_widgets": PHASE1_WIDGETS}, indent=2))
        return body

    # Live update
    import boto3
    cw = boto3.client("cloudwatch", region_name=REGION)
    cw.put_dashboard(
        DashboardName=DASHBOARD_NAME,
        DashboardBody=json.dumps(body),
    )
    print(f"Dashboard {DASHBOARD_NAME} updated: +{len(PHASE1_WIDGETS)} Phase 1 widgets")
    url = (
        f"https://console.aws.amazon.com/cloudwatch/home"
        f"?region={REGION}#dashboards:name={DASHBOARD_NAME}"
    )
    print(f"View at: {url}")
    return body


if __name__ == "__main__":
    use_mocks = os.getenv("USE_AWS_MOCKS", "true").lower() in {"1", "true", "yes"}
    add_phase1_widgets(dry_run=use_mocks)
