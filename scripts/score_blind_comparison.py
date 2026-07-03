"""
scripts/score_blind_comparison.py
==================================
Once raters have filled in data/blind_comparison_ratings_template.csv (or a
copy of it), run this script to unblind and tally results against
data/blind_comparison_key.json.

Usage:
    python scripts/score_blind_comparison.py --ratings data/blind_comparison_ratings_template.csv

Outputs:
    Prints a summary to stdout:
      - mean scores per system (full_system vs no_agent_baseline) for each metric
      - overall preference win rate
    data/blind_comparison_results.json — machine-readable summary
"""

import argparse
import csv
import json
from pathlib import Path
from collections import defaultdict


def mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 4) if values else None


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ratings", default="data/blind_comparison_ratings_template.csv")
    parser.add_argument("--key", default="data/blind_comparison_key.json")
    parser.add_argument("--out", default="data/blind_comparison_results.json")
    args = parser.parse_args()

    key_data = json.load(open(args.key, "r", encoding="utf-8"))
    mapping = key_data["mapping"]

    scores_by_system = defaultdict(lambda: defaultdict(list))
    wins = defaultdict(int)
    ties = 0
    rows_used = 0

    with open(args.ratings, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            scenario_id = row.get("scenario_id", "").strip()
            if scenario_id not in mapping:
                continue
            system_of = mapping[scenario_id]  # {"system_a": ..., "system_b": ...}

            has_any_rating = any(
                row.get(col, "").strip()
                for col in (
                    "clarity_a_1to5",
                    "clarity_b_1to5",
                    "correctness_a_1to5",
                    "correctness_b_1to5",
                    "adaptiveness_a_1to5",
                    "adaptiveness_b_1to5",
                    "overall_preference_a_or_b_or_tie",
                )
            )
            if not has_any_rating:
                continue
            rows_used += 1

            for metric in ("clarity", "correctness", "adaptiveness"):
                score_a = to_float(row.get(f"{metric}_a_1to5"))
                score_b = to_float(row.get(f"{metric}_b_1to5"))
                if score_a is not None:
                    scores_by_system[system_of["system_a"]][metric].append(score_a)
                if score_b is not None:
                    scores_by_system[system_of["system_b"]][metric].append(score_b)

            preference = row.get("overall_preference_a_or_b_or_tie", "").strip().lower()
            if preference in ("a", "system a", "system_a"):
                wins[system_of["system_a"]] += 1
            elif preference in ("b", "system b", "system_b"):
                wins[system_of["system_b"]] += 1
            elif preference in ("tie", "t", ""):
                pass  # counted below via ties variable
            if preference in ("tie", "t"):
                ties += 1

    summary = {
        "rows_used": rows_used,
        "mean_scores_by_system": {
            system: {metric: mean(vals) for metric, vals in metrics.items()}
            for system, metrics in scores_by_system.items()
        },
        "overall_preference_wins": dict(wins),
        "ties": ties,
    }

    print("=" * 70)
    print("   Blind Comparison Results: full_system vs no_agent_baseline")
    print("=" * 70)
    print(f"Rated scenarios: {rows_used}")
    print("\nMean scores (1-5) by system:")
    for system, metrics in summary["mean_scores_by_system"].items():
        print(f"  {system}:")
        for metric, value in metrics.items():
            print(f"    {metric}: {value}")
    print("\nOverall preference wins:")
    for system, count in summary["overall_preference_wins"].items():
        print(f"  {system}: {count}")
    print(f"  ties: {ties}")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to {args.out}")


if __name__ == "__main__":
    main()
