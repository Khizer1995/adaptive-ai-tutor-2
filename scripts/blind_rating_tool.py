"""
scripts/blind_rating_tool.py
============================
Interactive CLI tool for conducting blind human evaluation of the AI Tutor
outputs. Raters score "Output A" vs "Output B" without knowing which system
produced which output (no_agent_baseline vs full_system). The randomization
key is saved separately and only revealed during aggregation.

Usage:
    python scripts/blind_rating_tool.py

Inputs:
    data/blind_comparison_packet.json  — side-by-side outputs per scenario

Outputs:
    data/blind_rating_results_{rater_name}_{timestamp}.json
        — per-scenario scores for this rater
    data/blind_rating_randomization_key_{timestamp}.json
        — A/B → baseline/full_system mapping (keep away from raters!)

Rating dimensions (each 1–5):
    • Pedagogical Clarity    — how clear and understandable the explanation is
    • Correctness            — how technically accurate the content is
    • Skill-Level Appropriateness — how well-matched the response is to the
                               student's proficiency level

Overall Preference: A | B | Tie

Session features:
    • Progress indicator ("Scenario X of N")
    • "back" command to revise the previous rating
    • "exit" command to save progress and quit (resumable later)
    • Input validation with helpful retry messages
    • Incremental auto-save after every scenario
"""

import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PACKET_PATH = DATA_DIR / "blind_comparison_packet.json"


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def clear_screen():
    """Clear the terminal (best-effort)."""
    os.system("cls" if os.name == "nt" else "clear")


def divider(char="=", width=72):
    print(char * width)


def print_header(title: str):
    divider()
    print(f"  {title}")
    divider()


def prompt_int(prompt_text: str, lo: int, hi: int) -> int:
    """Prompt until the user enters an integer in [lo, hi]. Returns the int."""
    while True:
        raw = input(prompt_text).strip()
        if raw.lower() in ("exit", "quit", "save"):
            raise KeyboardInterrupt("save_and_exit")
        if raw.lower() == "back":
            raise ValueError("back")
        try:
            val = int(raw)
            if lo <= val <= hi:
                return val
            print(f"  ✗  Please enter a number between {lo} and {hi}.")
        except ValueError:
            print(f"  ✗  Invalid input. Enter a number between {lo} and {hi}.")


def prompt_preference() -> str:
    """Prompt until the user enters A, B, or Tie. Returns 'A', 'B', or 'Tie'."""
    while True:
        raw = input("  Overall Preference (A / B / Tie): ").strip()
        if raw.lower() in ("exit", "quit", "save"):
            raise KeyboardInterrupt("save_and_exit")
        if raw.lower() == "back":
            raise ValueError("back")
        normalized = raw.upper()
        if normalized in ("A", "B"):
            return normalized
        if normalized in ("TIE", "T"):
            return "Tie"
        print("  ✗  Please enter A, B, or Tie.")


def prompt_continue() -> str:
    """
    After rating a scenario, ask the rater to continue, go back, or exit.
    Returns one of: 'continue', 'back', 'exit'.
    """
    valid = {"continue": "continue", "c": "continue",
             "back": "back", "b": "back",
             "exit": "exit", "save": "exit", "e": "exit"}
    while True:
        raw = input("\n[Continue / Back / Save & Exit]: ").strip().lower()
        if raw in valid:
            return valid[raw]
        print("  ✗  Please type  Continue,  Back,  or  Save & Exit.")


# ---------------------------------------------------------------------------
# Core session logic
# ---------------------------------------------------------------------------

def load_packet() -> list:
    """Load the blind comparison packet; abort with a clear message if missing."""
    if not PACKET_PATH.exists():
        print(f"\n[ERROR] Comparison packet not found at:\n  {PACKET_PATH}\n")
        print("Run  python scripts/generate_blind_comparison.py  first.")
        sys.exit(1)
    with open(PACKET_PATH, "r", encoding="utf-8") as f:
        packet = json.load(f)
    if not packet:
        print("[ERROR] Comparison packet is empty.")
        sys.exit(1)
    return packet


def build_randomization(packet: list, rng: random.Random) -> tuple:
    """
    Randomly assign 'Output A' / 'Output B' labels independently of the
    existing system_a / system_b in the packet.

    We read the *original* key from  data/blind_comparison_key.json  to know
    the true system behind each packet slot, then re-randomize freshly per
    rater session.

    Returns:
        randomized_packet  — list of dicts with keys:
                             scenario_id, concept, topic, subtopic,
                             student_level, student_last_score,
                             output_a, output_b
        rand_key           — dict mapping scenario_id → {
                                 "output_a": "full_system" | "no_agent_baseline",
                                 "output_b": "full_system" | "no_agent_baseline"
                             }
    """
    # Load existing key to know which packet slot is which system.
    key_path = DATA_DIR / "blind_comparison_key.json"
    if key_path.exists():
        with open(key_path, "r", encoding="utf-8") as f:
            orig_key = json.load(f).get("mapping", {})
    else:
        orig_key = {}

    randomized_packet = []
    rand_key = {}

    for scenario in packet:
        sid = scenario["scenario_id"]

        # Determine which label in the packet corresponds to which system.
        orig_mapping = orig_key.get(sid, {})
        packet_a_system = orig_mapping.get("system_a", "system_a")
        packet_b_system = orig_mapping.get("system_b", "system_b")

        # The actual text blocks from the packet.
        text_map = {
            packet_a_system: scenario["system_a"],
            packet_b_system: scenario["system_b"],
        }

        # Randomly decide which system becomes "Output A" for this rater.
        systems = list(text_map.keys())
        rng.shuffle(systems)
        new_a_system, new_b_system = systems[0], systems[1]

        randomized_packet.append({
            "scenario_id": sid,
            "concept": scenario.get("concept", ""),
            "topic": scenario.get("topic", ""),
            "subtopic": scenario.get("subtopic", ""),
            "student_level": scenario.get("student_level", ""),
            "student_last_score": scenario.get("student_last_score"),
            "output_a": text_map[new_a_system],
            "output_b": text_map[new_b_system],
        })
        rand_key[sid] = {
            "output_a": new_a_system,
            "output_b": new_b_system,
        }

    return randomized_packet, rand_key


def save_randomization_key(rand_key: dict, timestamp: str):
    """Persist the per-rater randomization key to disk."""
    key_file = DATA_DIR / f"blind_rating_randomization_key_{timestamp}.json"
    with open(key_file, "w", encoding="utf-8") as f:
        json.dump(
            {"generated_at": timestamp, "mapping": rand_key},
            f,
            ensure_ascii=False,
            indent=2,
        )
    return key_file


def save_results(results: list, rater_name: str, timestamp: str) -> Path:
    """Persist all collected ratings to disk. Returns the output path."""
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in rater_name)
    out_path = DATA_DIR / f"blind_rating_results_{safe_name}_{timestamp}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "rater": rater_name,
                "session_timestamp": timestamp,
                "ratings": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    return out_path


def rate_scenario(scenario: dict, index: int, total: int) -> dict:
    """
    Present one scenario to the rater and collect scores.

    Returns a rating dict, or raises:
        ValueError("back")         — rater wants to go back
        KeyboardInterrupt("save_and_exit")  — rater wants to quit
    """
    clear_screen()
    divider("-")
    print(f"  Scenario {index} of {total}")
    divider("-")

    sid = scenario["scenario_id"]
    level = scenario.get("student_level", "?")
    score = scenario.get("student_last_score")
    concept = scenario.get("concept", "?")
    subtopic = scenario.get("subtopic", "?")

    score_label = ""
    if score is not None:
        if score < 0.35:
            score_label = "  (struggling)"
        elif score > 0.75:
            score_label = "  (excelling)"

    print(f"  Scenario ID  : {sid}")
    print(f"  Concept      : {concept}")
    print(f"  Subtopic     : {subtopic}")
    print(f"  Student Level: {level}")
    if score is not None:
        print(f"  Last Score   : {score}{score_label}")
    divider("-")

    # ---- Output A ----
    print("\n=== OUTPUT A ===\n")
    print(scenario["output_a"])

    # ---- Output B ----
    print("\n=== OUTPUT B ===\n")
    print(scenario["output_b"])

    # ---- Rating prompts ----
    divider("-")
    print("\nRate OUTPUT A  (type 'back' to revise previous, 'exit' to save & quit)\n")

    criteria = [
        ("pedagogical_clarity", "Pedagogical Clarity",
         "How clear and understandable is the explanation?"),
        ("correctness", "Correctness",
         "How technically accurate is the content?"),
        ("appropriateness", "Skill-Level Appropriateness",
         "How well-matched is this to the student's level?"),
    ]

    scores_a = {}
    for key, label, desc in criteria:
        print(f"  {label}  —  {desc}")
        val = prompt_int(f"  {label} (1-5): ", 1, 5)
        scores_a[key] = val
        print()

    print("\nRate OUTPUT B\n")
    scores_b = {}
    for key, label, desc in criteria:
        print(f"  {label}  —  {desc}")
        val = prompt_int(f"  {label} (1-5): ", 1, 5)
        scores_b[key] = val
        print()

    print()
    preference = prompt_preference()

    return {
        "scenario_id": sid,
        "rated_at": datetime.now().isoformat(),
        "output_a_scores": scores_a,
        "output_b_scores": scores_b,
        "overall_preference": preference,
    }


# ---------------------------------------------------------------------------
# Resume logic
# ---------------------------------------------------------------------------

def find_resume_file(rater_name: str, timestamp: str) -> Path | None:
    """Look for an in-progress results file for this rater."""
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in rater_name)
    pattern = f"blind_rating_results_{safe_name}_*.json"
    candidates = sorted(DATA_DIR.glob(pattern))
    return candidates[-1] if candidates else None


def load_partial_results(path: Path) -> list:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("ratings", [])


# ---------------------------------------------------------------------------
# Main entry-point
# ---------------------------------------------------------------------------

def main():
    clear_screen()
    print_header("BLIND COMPARISON RATING TOOL")
    print("  Cognitive Adaptive AI Tutor — Human Evaluation")
    print("  Each output is shown without labels revealing which system made it.")
    divider()
    print()

    # Rater identification
    rater_name = input("  Rater Name: ").strip()
    if not rater_name:
        rater_name = "anonymous"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\n  Starting session: {timestamp}")

    # Load packet
    packet = load_packet()
    print(f"  Loaded {len(packet)} scenarios from comparison packet.\n")

    # Seed the per-session RNG (different every run for true blinding).
    rng = random.Random()
    randomized_packet, rand_key = build_randomization(packet, rng)

    # Save randomization key immediately (before any ratings are done)
    key_file = save_randomization_key(rand_key, timestamp)
    print(f"  [OK] Randomization key saved to:\n    {key_file}")
    print("  [!]  Keep this file away from raters until all scoring is complete!\n")

    total = len(randomized_packet)

    # Check for a prior partial session
    resume_path = find_resume_file(rater_name, timestamp)
    results: list = []
    start_index = 0

    # We can't resume across sessions because randomization differs per run.
    # Instead, check if there's an *existing* file for this rater from a
    # previous run (identified by the rater name regardless of timestamp).
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in rater_name)
    prior_files = sorted(DATA_DIR.glob(f"blind_rating_results_{safe_name}_*.json"))
    if prior_files:
        latest = prior_files[-1]
        print(f"  Found prior session file:\n    {latest}")
        resume = input("  Resume from that session? (y/n): ").strip().lower()
        if resume == "y":
            prior_data = load_partial_results(latest)
            done_ids = {r["scenario_id"] for r in prior_data}
            results = prior_data

            # Re-order randomized_packet so already-done scenarios come last
            remaining = [s for s in randomized_packet if s["scenario_id"] not in done_ids]
            done_scenarios = [s for s in randomized_packet if s["scenario_id"] in done_ids]
            randomized_packet = remaining + done_scenarios
            start_index = 0
            total = len(remaining)
            print(f"\n  Resuming: {len(done_ids)} already rated, {total} remaining.\n")
            if total == 0:
                print("  All scenarios already rated! Nothing left to do.")
                print(f"  Results are at:\n    {latest}")
                return

    input("  Press Enter to begin rating...\n")

    # ---- Rating loop ----
    i = start_index
    out_path = None

    while i < total:
        scenario = randomized_packet[i]
        display_num = len(results) + 1  # position in the overall session
        try:
            rating = rate_scenario(scenario, display_num, len(randomized_packet))
            results.append(rating)

            # Incremental save
            out_path = save_results(results, rater_name, timestamp)
            print(f"\n  [OK] Rating saved. ({len(results)} of {len(randomized_packet)} done)")

            if i + 1 == total:
                print("\n  [OK] All scenarios rated! Session complete.")
                break

            action = prompt_continue()
            if action == "exit":
                raise KeyboardInterrupt("save_and_exit")
            elif action == "back" and i > 0:
                # Roll back: remove last rating and go back one step
                results.pop()
                i -= 1
                continue

        except ValueError as exc:
            if str(exc) == "back" and i > 0:
                # "back" typed during rating — go back one scenario
                if results:
                    results.pop()
                i = max(0, i - 1)
                continue
            # Otherwise ignore spurious ValueError and re-prompt same scenario
            continue

        except KeyboardInterrupt:
            # Ctrl-C or typed "exit" — save and quit gracefully
            print("\n\n  Session interrupted. Saving progress...")
            if results:
                out_path = save_results(results, rater_name, timestamp)
                print(f"  ✓  Progress saved to:\n    {out_path}")
                print(f"  Randomization key at:\n    {key_file}")
            else:
                print("  (No ratings to save yet.)")
            print("\n  Run the tool again and choose to resume to continue.\n")
            sys.exit(0)

        i += 1

    # ---- Session summary ----
    if results:
        out_path = save_results(results, rater_name, timestamp)
        divider()
        print(f"\n  Session complete!  {len(results)} scenario(s) rated.")
        print(f"\n  Results saved to:\n    {out_path}")
        print(f"  Randomization key at:\n    {key_file}")
        divider()
        print()
        print("  Next steps:")
        print("  1. Have other raters run this tool independently.")
        print("  2. Once all raters are done, run:")
        print("       python scripts/aggregate_blind_ratings.py")
        print()


if __name__ == "__main__":
    main()
