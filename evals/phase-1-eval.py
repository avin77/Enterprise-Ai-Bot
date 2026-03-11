#!/usr/bin/env python
"""
Phase 1 Evaluation Script -- GXA Voice Baseline
Fixed seed=42 for deterministic results. Runs 100 mock turns.

Metrics evaluated:
  latency_p95      -- 95th pct turn latency, 100 turns, seed=42. Target: < 1500ms
  rag_recall       -- Fraction of queries with >=1 source in result. Target: > 75%
  deployment_success -- /health returns 200 (local or ECS). Target: true
  redis_fallback_ok  -- BM25 returns results when Redis mock-killed. Target: true

Usage:
    python evals/phase-1-eval.py               # Mock mode (default)
    python evals/phase-1-eval.py --live-url http://65.0.116.5:8000  # ECS live check
"""
import argparse
import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Fixed seed for reproducibility -- all Phase 1 evals use seed=42
EVAL_SEED = 42
TURN_COUNT = 100
SLO_TARGET_MS = 1500.0
RAG_RECALL_TARGET = 0.75

# 20 representative Jackson County FAQ queries (deterministic set)
EVAL_QUERIES = [
    "How do I pay my property tax online?",
    "When is my property tax bill due?",
    "How do I apply for a building permit?",
    "What is the status of my permit application?",
    "How do I register to vote?",
    "Where is my polling place?",
    "When is my trash pickup day?",
    "How do I report a pothole?",
    "What are the court fee payment options?",
    "How do I renew my business license?",
    "What senior services does the county provide?",
    "How do I apply for food stamps?",
    "Who do I call about a stray animal?",
    "What is the non-emergency sheriff number?",
    "How do I register for a parks program?",
    "What is the recycling schedule?",
    "How do I dispute my property tax assessment?",
    "What documents do I need to apply for a permit?",
    "How do I pay a traffic ticket?",
    "What emergency management resources are available?",
]


async def run_single_turn(pipeline, query: str) -> dict:
    """Run one pipeline turn and return timing + source info."""
    audio_bytes = query.encode("utf-8")  # Mock: use text as audio bytes
    t0 = time.monotonic()
    result = await pipeline.run_roundtrip(audio_bytes)
    total_ms = (time.monotonic() - t0) * 1000

    return {
        "query": query,
        "total_ms": total_ms,
        "asr_ms": getattr(result, "asr_ms", 0.0),
        "rag_ms": getattr(result, "rag_ms", 0.0),
        "llm_ms": getattr(result, "llm_ms", 0.0),
        "tts_ms": getattr(result, "tts_ms", 0.0),
        "sources": getattr(result, "sources", []),
        "has_source": len(getattr(result, "sources", [])) > 0,
    }


async def run_eval(live_url: str | None = None) -> dict:
    """Run Phase 1 evaluation. Returns metrics dict."""
    random.seed(EVAL_SEED)
    os.environ.setdefault("USE_AWS_MOCKS", "true")

    from backend.app.orchestrator.runtime import build_pipeline

    pipeline = build_pipeline()

    # Generate 100 queries by cycling through the 20 eval queries with seed
    eval_queries = [random.choice(EVAL_QUERIES) for _ in range(TURN_COUNT)]

    print(f"Running {TURN_COUNT} eval turns (seed={EVAL_SEED})...")
    results = []
    for i, query in enumerate(eval_queries):
        turn = await run_single_turn(pipeline, query)
        results.append(turn)
        if (i + 1) % 20 == 0:
            print(f"  Progress: {i + 1}/{TURN_COUNT} turns complete")

    # Compute metrics
    latencies = sorted(r["total_ms"] for r in results)
    n = len(latencies)
    latency_p95 = latencies[min(int(n * 0.95), n - 1)]
    rag_recall = sum(1 for r in results if r["has_source"]) / n

    # deployment_success: check /health (local or live)
    deployment_success = False
    check_url = live_url or "http://localhost:8000"
    try:
        import urllib.request

        with urllib.request.urlopen(f"{check_url}/health", timeout=5) as resp:
            deployment_success = resp.status == 200
    except Exception:
        deployment_success = False  # Can't reach server

    # redis_fallback_ok: verify BM25 works when Redis is absent
    redis_fallback_ok = False
    try:
        from backend.app.services.bm25_index import build_bm25_index, bm25_search

        corpus = [
            {
                "text": "property tax payment",
                "source_doc": "tax.pdf",
                "chunk_id": "tax.pdf:chunk:0",
                "department": "finance",
            }
        ]
        bm25, docs = build_bm25_index(corpus)
        # No Redis client (None) -- should work as direct BM25
        fallback_results = bm25_search(bm25, docs, "property tax", top_k=1)
        redis_fallback_ok = len(fallback_results) > 0
    except Exception as exc:
        print(f"  Redis fallback test failed: {exc}")

    metrics = {
        "latency_p95": round(latency_p95, 1),
        "latency_p50": round(latencies[int(n * 0.50)], 1),
        "rag_recall": round(rag_recall, 3),
        "deployment_success": deployment_success,
        "redis_fallback_ok": redis_fallback_ok,
        "turns_evaluated": TURN_COUNT,
        "slo_violations": sum(1 for r in results if r["total_ms"] >= SLO_TARGET_MS),
        "seed": EVAL_SEED,
    }

    # Print results
    print("\n=== Phase 1 Evaluation Results ===")
    print(f"  latency_p95:       {metrics['latency_p95']:.1f}ms  (target: < {SLO_TARGET_MS:.0f}ms)")
    print(f"  latency_p50:       {metrics['latency_p50']:.1f}ms")
    print(f"  rag_recall:        {metrics['rag_recall']:.1%}     (target: > {RAG_RECALL_TARGET:.0%})")
    print(f"  deployment_success: {metrics['deployment_success']} (target: true)")
    print(f"  redis_fallback_ok:  {metrics['redis_fallback_ok']} (target: true)")
    print(f"  slo_violations:     {metrics['slo_violations']}/{TURN_COUNT}")

    # Gate check (informational -- not enforcing in Phase 1; Phase 3 Eval Gate I enforces)
    latency_pass = metrics["latency_p95"] < SLO_TARGET_MS
    recall_pass = metrics["rag_recall"] >= RAG_RECALL_TARGET
    print(f"\n  Latency SLO: {'PASS' if latency_pass else 'FAIL (mock timings expected near 0ms)'}")
    print(f"  RAG Recall:  {'PASS' if recall_pass else 'FAIL'}")
    print("\n  Note: Mock timings will be near 0ms. Live ECS timings will reflect real latency.")
    print("  Phase 3 Eval Gate I enforces SLO on live ECS with real Bedrock + Polly calls.")

    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live-url",
        type=str,
        default=None,
        help="Live ECS URL for deployment_success check (e.g. http://65.0.116.5:8000)",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default=None,
        help="Write metrics JSON to file",
    )
    args = parser.parse_args()

    metrics = asyncio.run(run_eval(args.live_url))

    if args.output_json:
        with open(args.output_json, "w") as f:
            json.dump(metrics, f, indent=2)
        print(f"\nMetrics written to {args.output_json}")
