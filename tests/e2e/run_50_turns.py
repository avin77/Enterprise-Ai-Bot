"""
tests/e2e/run_50_turns.py
Run N test voice turns against the ECS WebSocket endpoint and record results.

Usage:
    python tests/e2e/run_50_turns.py --host 65.0.116.5 --port 8000 --turns 50 --output results.json

Prerequisites:
    pip install websockets
"""
from __future__ import annotations
import argparse
import asyncio
import datetime
import json
import time
from pathlib import Path


async def run_turn(ws_url: str, question: str, token: str = "test-token") -> dict:
    """Send one text turn via WebSocket and measure latency."""
    try:
        import websockets
    except ImportError:
        raise ImportError("Run: pip install websockets")

    start = time.perf_counter()
    try:
        async with websockets.connect(
            f"{ws_url}?token={token}",
            open_timeout=10,
            close_timeout=5,
        ) as ws:
            await asyncio.wait_for(ws.recv(), timeout=10)  # discard ack
            await ws.send(json.dumps({"type": "text", "text": question}))
            raw = await asyncio.wait_for(ws.recv(), timeout=30)
            elapsed_ms = (time.perf_counter() - start) * 1000
            response = json.loads(raw)
            return {
                "question": question,
                "answer": response.get("text", ""),
                "latency_ms": round(elapsed_ms, 1),
                "slo_met": elapsed_ms < 1500,
                "status": "ok",
                "error": None,
            }
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "question": question,
            "answer": None,
            "latency_ms": round(elapsed_ms, 1),
            "slo_met": False,
            "status": "error",
            "error": str(e),
        }


def _percentile(sorted_values: list[float], p: int) -> float | None:
    if not sorted_values:
        return None
    idx = min(int(len(sorted_values) * p / 100), len(sorted_values) - 1)
    return sorted_values[idx]


async def run_test(host: str, port: int, turns: int, output: str, token: str) -> None:
    questions_path = Path(__file__).parent / "sample_questions.json"
    with open(questions_path) as f:
        all_questions = json.load(f)

    questions = (all_questions * ((turns // len(all_questions)) + 1))[:turns]
    ws_url = f"ws://{host}:{port}/ws"

    print(f"Running {turns} turns against {ws_url}")
    print(f"Started: {datetime.datetime.now().isoformat()}\n")

    results = []
    for i, question in enumerate(questions, 1):
        result = await run_turn(ws_url, question, token)
        results.append(result)
        flag = "OK " if result["status"] == "ok" else "ERR"
        slo = "SLO " if result["slo_met"] else "SLOW"
        print(f"  [{i:02d}/{turns}] {flag} {slo} {result['latency_ms']:.0f}ms -- {question[:60]}")

    ok_count = sum(1 for r in results if r["status"] == "ok")
    slo_count = sum(1 for r in results if r["slo_met"])
    latencies = sorted(r["latency_ms"] for r in results if r["status"] == "ok")

    summary = {
        "total_turns": turns,
        "success_count": ok_count,
        "error_count": turns - ok_count,
        "slo_met_count": slo_count,
        "slo_met_pct": round(slo_count / turns * 100, 1),
        "latency_p50_ms": _percentile(latencies, 50),
        "latency_p95_ms": _percentile(latencies, 95),
        "latency_p99_ms": _percentile(latencies, 99),
        "estimated_cost_usd": round(ok_count * 0.016, 4),
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }

    with open(output, "w") as f:
        json.dump({"summary": summary, "turns": results}, f, indent=2)

    print(f"\n{'='*60}")
    print(f"RESULTS: {ok_count}/{turns} success | SLO: {summary['slo_met_pct']}%")
    print(f"Latency -- p50: {summary['latency_p50_ms']}ms | p95: {summary['latency_p95_ms']}ms")
    print(f"Est. cost: ${summary['estimated_cost_usd']:.4f} ({ok_count} turns x $0.016/turn)")
    print(f"Saved: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run N voice turns against ECS WebSocket")
    parser.add_argument("--host", default="65.0.116.5")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--turns", type=int, default=50)
    parser.add_argument("--output", default="results.json")
    parser.add_argument("--token", default="test-token")
    args = parser.parse_args()
    asyncio.run(run_test(args.host, args.port, args.turns, args.output, args.token))


if __name__ == "__main__":
    main()
