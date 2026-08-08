"""
scripts/generate_blind_comparison.py
=====================================
Builds a blinded human-rating packet comparing the No-Agent-System Baseline
against the full multi-agent system, on the same fixtures.

Prereqs (run these first):
    python scripts/run_ablation.py     # produces data/ablation_raw_logs.json
                                        # (contains the "full_system" configuration)
    python scripts/run_baseline.py     # produces data/baseline_raw_logs.json

Usage:
    python scripts/generate_blind_comparison.py [--seed 42]

Outputs:
    data/blind_comparison_packet.json  — for raters. Each scenario shows the
                                          topic/subtopic + "System A" / "System B"
                                          content, with NO indication of which
                                          is which.
    data/blind_comparison_key.json     — answer key mapping A/B back to
                                          baseline vs full_system per scenario.
                                          Keep this OUT of the raters' hands
                                          until scoring is complete.
    data/blind_comparison_ratings_template.csv
                                        — a CSV raters fill in by hand.
"""

import argparse
import csv
import json
import random
from pathlib import Path


def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run the corresponding script first (see module docstring)."
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42, help="Seed controlling A/B randomization.")
    args = parser.parse_args()

    fixtures_path = Path("data/ablation_fixtures.json")
    full_system_path = Path("data/ablation_raw_logs.json")
    baseline_path = Path("data/baseline_raw_logs.json")

    packet_path = Path("data/blind_comparison_packet.json")
    key_path = Path("data/blind_comparison_key.json")
    csv_path = Path("data/blind_comparison_ratings_template.csv")

    fixtures = load_json(fixtures_path)
    full_system_logs = load_json(full_system_path)
    baseline_logs = load_json(baseline_path)

    # Index full_system content by scenario_id (learning_path text from crew_output).
    full_system_by_scenario = {}
    for record in full_system_logs:
        if record.get("configuration") != "full_system":
            continue
        scenario_id = record["scenario_id"]
        crew_output = (record.get("final_state", {}) or {}).get("crew_output", {}) or {}
        full_system_by_scenario[scenario_id] = str(crew_output.get("learning_path", "")).strip()

    # Index baseline content by scenario_id.
    baseline_by_scenario = {
        record["scenario_id"]: str(record.get("content", "")).strip()
        for record in baseline_logs
    }

    rng = random.Random(args.seed)
    packet = []
    key = {"seed": args.seed, "mapping": {}}

    skipped = []
    for scenario in fixtures:
        scenario_id = scenario["scenario_id"]
        full_text = full_system_by_scenario.get(scenario_id, "")
        baseline_text = baseline_by_scenario.get(scenario_id, "")

        if not full_text or not baseline_text:
            skipped.append(scenario_id)
            continue

        profile = scenario.get("student_profile", {})
        # Randomly decide which label (A/B) gets the full system vs baseline.
        full_is_a = rng.random() < 0.5
        system_a_text = full_text if full_is_a else baseline_text
        system_b_text = baseline_text if full_is_a else full_text

        packet.append(
            {
                "scenario_id": scenario_id,
                "concept": scenario.get("concept"),
                "topic": profile.get("current_topic"),
                "subtopic": profile.get("current_subtopic"),
                "student_level": profile.get("level"),
                "student_last_score": profile.get("last_score"),
                "system_a": system_a_text,
                "system_b": system_b_text,
            }
        )
        key["mapping"][scenario_id] = {
            "system_a": "full_system" if full_is_a else "no_agent_baseline",
            "system_b": "no_agent_baseline" if full_is_a else "full_system",
        }

    with open(packet_path, "w", encoding="utf-8") as f:
        json.dump(packet, f, ensure_ascii=False, indent=2)
    print(f"Blind rating packet saved to {packet_path} ({len(packet)} scenarios)")

    with open(key_path, "w", encoding="utf-8") as f:
        json.dump(key, f, ensure_ascii=False, indent=2)
    print(f"Answer key saved to {key_path} — keep this away from raters until scoring is done.")

    # Simple CSV rating template for human raters.
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "scenario_id",
                "rater_name",
                "clarity_a_1to5",
                "clarity_b_1to5",
                "correctness_a_1to5",
                "correctness_b_1to5",
                "adaptiveness_a_1to5",
                "adaptiveness_b_1to5",
                "overall_preference_a_or_b_or_tie",
                "notes",
            ]
        )
        for row in packet:
            writer.writerow([row["scenario_id"], "", "", "", "", "", "", "", "", ""])
    print(f"Rating CSV template saved to {csv_path}")

    if skipped:
        print(f"\nSkipped {len(skipped)} scenario(s) missing content on one side: {skipped}")


if __name__ == "__main__":
    main()
