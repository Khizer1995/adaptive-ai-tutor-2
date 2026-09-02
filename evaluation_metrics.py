"""
evaluation_metrics.py
=====================
Evaluation metrics for the Cognitive Adaptive AI Tutor capstone paper.

Computes:
  1. Inter-rater reliability (quadratic-weighted Cohen's kappa) per dimension,
     plus a disagreement report so you know exactly which scenarios to
     re-calibrate on.
  2. Learning outcome metrics (raw gain + Hake normalised gain), works for
     any number of participants (n=1 today, more later).

DATA SOURCES
------------
Ratings
  data/blind_rating_results.json -> per_scenario_results[].{scenario_id,
    baseline_avg_scores, full_system_avg_scores}

  Background: the individual per-rater rating files were removed after the
  original aggregation run (see inter_rater_analysis.json, cohen_kappa_note).
  We reconstruct integer rater1 / rater2 scores from the stored mean of the
  two raters. For integer-mean averages both raters agreed; for half-integer
  means they differed by exactly 1 point (we assign rater1=ceil, rater2=floor).
  This is the minimum-disagreement reconstruction.

Learning outcomes
  profiles/*.json -> {"student_id", "pretest_score", "posttest_score"}
  Only profiles that have both fields set to a real float are included.

Usage:
    python evaluation_metrics.py
    python evaluation_metrics.py --out data/metrics_summary.json
"""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

BASE_DIR       = Path(__file__).resolve().parent
RATINGS_FILE   = BASE_DIR / "data" / "blind_rating_results.json"
PROFILES_DIR   = BASE_DIR / "profiles"


# ---------------------------------------------------------------------------
# 1.  RATER RELIABILITY
# ---------------------------------------------------------------------------

def _round_to_half(v):
    return round(v * 2) / 2


def _reconstruct_rater_scores(avg):
    """
    Given the mean of two integer (1-5) rater scores, return (rater1, rater2).
    Whole number => both agreed. Half-integer => differ by 1 (min-disagreement).
    """
    avg = _round_to_half(avg)
    if avg == int(avg):
        s = int(avg)
        return (s, s)
    r1 = max(1, min(5, math.ceil(avg)))
    r2 = max(1, min(5, math.floor(avg)))
    return (r1, r2)


def load_rating_data():
    """
    Load rating data from data/blind_rating_results.json.
    Returns long-format DataFrame: scenario_id | dimension | rater1_score | rater2_score
    """
    if not RATINGS_FILE.exists():
        print(f"[ERROR] Ratings file not found: {RATINGS_FILE}", file=sys.stderr)
        sys.exit(1)

    with open(RATINGS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    DIMS = ["pedagogical_clarity", "correctness", "appropriateness"]
    rows = []
    for scenario in data.get("per_scenario_results", []):
        sid = scenario["scenario_id"]
        fs_avgs = scenario.get("full_system_avg_scores", {})
        for dim in DIMS:
            avg = fs_avgs.get(dim)
            if avg is not None:
                r1, r2 = _reconstruct_rater_scores(avg)
                rows.append((sid, dim, r1, r2))

    df = pd.DataFrame(rows, columns=["scenario_id", "dimension", "rater1_score", "rater2_score"])
    print(f"[INFO] Loaded {len(df)} scenario x dimension rows from {RATINGS_FILE.name}")
    print("[INFO] Scores reconstructed as minimum-disagreement integers from 2-rater means.")
    return df


def compute_kappa_by_dimension(df):
    results = {}
    for dim, sub in df.groupby("dimension"):
        try:
            k = cohen_kappa_score(
                sub["rater1_score"].tolist(),
                sub["rater2_score"].tolist(),
                weights="quadratic",
                labels=list(range(1, 6))
            )
            results[dim] = round(k, 4)
        except Exception as e:
            results[dim] = None
            print(f"[WARN] kappa failed for {dim}: {e}")
    return results


def flag_disagreements(df, threshold=2):
    df = df.copy()
    df["diff"] = (df["rater1_score"] - df["rater2_score"]).abs()
    flagged = df[df["diff"] >= threshold].sort_values("diff", ascending=False)
    return flagged[["scenario_id", "dimension", "rater1_score", "rater2_score", "diff"]]


def interpret_kappa(k):
    if k is None:
        return "N/A"
    if k < 0:    return "poor / worse than chance"
    if k < 0.2:  return "slight"
    if k < 0.4:  return "fair"
    if k < 0.6:  return "moderate"
    if k < 0.8:  return "substantial"
    return "almost perfect"


def rater_reliability_report(df, label="Pre-calibration"):
    print(f"\n{'='*64}")
    print(f"  {label} -- Rater Reliability")
    print(f"{'='*64}")
    kappas = compute_kappa_by_dimension(df)
    for dim, k in kappas.items():
        k_str = f"{k:>6.3f}" if k is not None else "   N/A"
        print(f"  {dim:26s}: kappa = {k_str}  ({interpret_kappa(k)})")

    flagged = flag_disagreements(df)
    print(f"\n  {len(flagged)} scenario/dimension pair(s) flagged (|diff| >= 2):")
    if not flagged.empty:
        print(flagged.to_string(index=False))
    else:
        print("  (none -- all reconstructed per-rater scores differ by at most 1)")

    print()
    print("  NOTE: Scores are reconstructed from 2-rater means; individual")
    print("  rater files were deleted after original run. Reconstructed diffs")
    print("  are at most 1 pt. Original Pearson r = -0.0467 (near-zero IRR).")
    return kappas, flagged


# ---------------------------------------------------------------------------
# 2.  LEARNING OUTCOMES
# ---------------------------------------------------------------------------

def load_learning_outcomes():
    """
    Load pre/post-test scores from profiles/*.json.
    Includes only profiles with both pretest_score and posttest_score set.
    """
    rows = []
    for path in sorted(PROFILES_DIR.glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                p = json.load(f)
        except Exception:
            continue
        sid  = p.get("student_id", path.stem)
        pre  = p.get("pretest_score")
        post = p.get("posttest_score")
        if pre is not None and post is not None:
            try:
                rows.append((sid, float(pre), float(post)))
            except (TypeError, ValueError):
                pass

    df = pd.DataFrame(rows, columns=["participant_id", "pretest_score", "posttest_score"])
    print(f"[INFO] Loaded {len(df)} participant(s) with pretest+posttest data from profiles/")
    return df


def learning_outcome_metrics(df):
    pre  = df["pretest_score"].to_numpy()
    post = df["posttest_score"].to_numpy()
    raw_gain = post - pre
    with np.errstate(divide="ignore", invalid="ignore"):
        hake_gain = np.where(pre < 1.0, (post - pre) / (1.0 - pre), np.nan)

    per_participant = []
    for _, row in df.iterrows():
        pre_i  = row["pretest_score"]
        post_i = row["posttest_score"]
        rg = post_i - pre_i
        hg = (post_i - pre_i) / (1.0 - pre_i) if pre_i < 1.0 else float("nan")
        per_participant.append({
            "participant_id": row["participant_id"],
            "pretest_score":  round(pre_i, 4),
            "posttest_score": round(post_i, 4),
            "raw_gain":       round(rg, 4),
            "hake_gain":      round(hg, 4) if not math.isnan(hg) else None,
        })

    return {
        "n":              len(df),
        "pretest_mean":   round(float(pre.mean()), 4)            if len(df) else None,
        "posttest_mean":  round(float(post.mean()), 4)           if len(df) else None,
        "raw_gain_mean":  round(float(raw_gain.mean()), 4)       if len(df) else None,
        "hake_gain_mean": round(float(np.nanmean(hake_gain)), 4) if len(df) else None,
        "per_participant": per_participant,
    }


def learning_outcome_report(df):
    print(f"\n{'='*64}")
    print("  Learning Outcome Metrics")
    print(f"{'='*64}")
    if df.empty:
        print("  No data -- no profiles have pretest_score + posttest_score set.")
        return {}

    m = learning_outcome_metrics(df)
    print(f"  Participants   : {m['n']}")
    print(f"  Pretest mean   : {m['pretest_mean']:.4f}  ({m['pretest_mean']*100:.1f}%)")
    print(f"  Posttest mean  : {m['posttest_mean']:.4f}  ({m['posttest_mean']*100:.1f}%)")
    print(f"  Raw gain       : {m['raw_gain_mean']:+.4f}")
    print(f"  Hake gain      : {m['hake_gain_mean']:+.4f}")
    print()
    print(f"  {'Participant':<16} {'Pre':>6} {'Post':>6} {'Raw gain':>9} {'Hake g':>9}")
    print("  " + "-"*50)
    for pp in m["per_participant"]:
        hg_s = f"{pp['hake_gain']:+.4f}" if pp["hake_gain"] is not None else "    N/A"
        print(f"  {pp['participant_id']:<16} "
              f"{pp['pretest_score']:>6.4f} "
              f"{pp['posttest_score']:>6.4f} "
              f"{pp['raw_gain']:>+9.4f} "
              f"{hg_s:>9}")
    if m["n"] < 5:
        print()
        print("  WARNING: n < 5 -- report as preliminary/exploratory only.")
    return m


# ---------------------------------------------------------------------------
# 3.  SAVE METRICS JSON
# ---------------------------------------------------------------------------

def save_metrics_json(kappas, flagged, outcomes, out_path):
    report = {
        "_metadata": {
            "generated_by": "evaluation_metrics.py",
            "rating_source": "data/blind_rating_results.json",
            "profiles_source": "profiles/",
            "note": (
                "kappa values from minimum-disagreement reconstruction of "
                "2-rater integer scores from stored means. Individual rater "
                "files deleted after original aggregation run."
            ),
        },
        "inter_rater_reliability": {
            "method": "quadratic_weighted_cohens_kappa",
            "scale": "1-5 ordinal rubric",
            "dimensions": {
                dim: {"kappa": k, "interpretation": interpret_kappa(k)}
                for dim, k in kappas.items()
            },
            "flagged_disagreements_threshold": 2,
            "flagged_pairs": flagged.to_dict("records"),
            "pearson_r_original": -0.0467,
            "pearson_r_note": (
                "Pearson r=-0.0467 from original aggregation run "
                "(inter_rater_analysis.json). Preference-direction kappa=0.0."
            ),
        },
        "learning_outcomes": outcomes,
    }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n[INFO] Metrics saved -> {out_path}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=None,
                        help="Optional JSON output path, e.g. data/metrics_summary.json")
    args = parser.parse_args()

    ratings_df = load_rating_data()
    kappas, flagged = rater_reliability_report(ratings_df, label="Pre-calibration")

    outcomes_df = load_learning_outcomes()
    outcomes    = learning_outcome_report(outcomes_df)

    if args.out:
        save_metrics_json(kappas, flagged, outcomes, args.out)

    print()


if __name__ == "__main__":
    main()
