"""
scripts/run_baseline.py
========================
Runs the No-Agent-System Baseline (core/baseline_agent.py) over the same
fixtures used by scripts/run_ablation.py, so the two can be compared later
on identical inputs.

Usage:
    python scripts/run_baseline.py

Outputs:
    data/baseline_raw_logs.json  — one record per scenario (full content)
    data/baseline_report.json    — aggregate timing stats
"""

import json
import math
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from core.baseline_agent import NoAgentBaseline


def mean(values):
    if not values:
        return 0.0
    return sum(values) / len(values)


def stddev(values):
    if len(values) <= 1:
        return 0.0
    m = mean(values)
    variance = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def main():
    print("=" * 70)
    print("   Cognitive Adaptive AI Tutor — No-Agent-System Baseline")
    print("=" * 70)

    fixtures_path = Path("data/ablation_fixtures.json")
    raw_logs_path = Path("data/baseline_raw_logs.json")
    report_path = Path("data/baseline_report.json")

    if not fixtures_path.exists():
        print(f"Error: Fixtures file not found at {fixtures_path}")
        return

    with open(fixtures_path, "r", encoding="utf-8") as f:
        scenarios = json.load(f)
    print(f"Loaded {len(scenarios)} scenarios from fixtures.")

    baseline = NoAgentBaseline()
    records = []

    for idx, scenario in enumerate(scenarios):
        scenario_id = scenario["scenario_id"]
        print(f"  [{idx + 1}/{len(scenarios)}] Running {scenario_id}...")
        try:
            record = baseline.generate(scenario)
        except Exception as exc:
            print(f"    [ERROR] Failed to run scenario {scenario_id}: {exc}")
            continue
        records.append(record)

    latencies = [r["latency_seconds"] for r in records]
    empty_count = sum(1 for r in records if not r["content"])

    report = {
        "configuration": "no_agent_baseline",
        "scenario_count": len(records),
        "empty_response_count": empty_count,
        "metrics": {
            "response_latency": {
                "mean": round(mean(latencies), 4),
                "stddev": round(stddev(latencies), 4),
            }
        },
        "scenarios": [
            {
                "scenario_id": r["scenario_id"],
                "latency_seconds": r["latency_seconds"],
                "content_length": len(r["content"]),
            }
            for r in records
        ],
    }

    with open(raw_logs_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"Raw logs saved to {raw_logs_path}")

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Report saved to {report_path}")

    print(f"\nMean latency: {report['metrics']['response_latency']['mean']}s")
    print("Baseline run completed.")
    print("=" * 70)


if __name__ == "__main__":
    main()
