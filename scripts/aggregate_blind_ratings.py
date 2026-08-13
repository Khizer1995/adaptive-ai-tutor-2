"""
scripts/aggregate_blind_ratings.py
====================================
Aggregates all per-rater blind rating files, unoblinds the results using the
randomization key(s), computes aggregate statistics, runs statistical
significance tests, and writes the final  data/blind_rating_results.json.

Usage:
    python scripts/aggregate_blind_ratings.py [--data-dir data]
                                              [--out data/blind_rating_results.json]

Inputs (auto-discovered):
    data/blind_rating_results_*.json            — per-rater rating files
    data/blind_rating_randomization_key_*.json  — per-session A/B → system mapping

Output:
    data/blind_rating_results.json  — machine-readable aggregated report

Report includes:
    - Number of raters and scenarios
    - Per-scenario baseline vs full_system scores (mean across raters)
    - Aggregate score statistics (mean, std) per dimension
    - Win / Loss / Tie counts and win-rate
    - Paired t-tests for each scoring dimension (p < 0.05 → significant)
    - Inter-rater reliability (Krippendorff's α approximation via pairwise
      correlations when ≥ 2 raters are present)
"""

import argparse
import json
import math
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

# scipy is optional; graceful degradation if absent
try:
    from scipy import stats as scipy_stats

    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print(
        "[WARN] scipy not installed. Statistical tests will use a built-in "
        "approximation. Install scipy for exact p-values:\n"
        "       pip install scipy\n"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mean(values: list) -> float | None:
    clean = [v for v in values if v is not None]
    return round(sum(clean) / len(clean), 4) if clean else None


def _std(values: list) -> float | None:
    clean = [v for v in values if v is not None]
    if len(clean) < 2:
        return 0.0
    return round(statistics.stdev(clean), 4)


def _paired_ttest(a_vals: list, b_vals: list):
    """
    Run a two-tailed paired t-test on a_vals vs b_vals.
    Returns (t_statistic, p_value, significant) or None on failure.
    Falls back to a manual implementation when scipy is absent.
    """
    # Align lengths
    pairs = [(a, b) for a, b in zip(a_vals, b_vals) if a is not None and b is not None]
    if len(pairs) < 2:
        return None

    diffs = [a - b for a, b in pairs]
    n = len(diffs)
    mean_d = sum(diffs) / n
    if n < 2:
        return None

    var_d = sum((d - mean_d) ** 2 for d in diffs) / (n - 1)
    se = math.sqrt(var_d / n) if var_d > 0 else 0

    if se == 0:
        t_stat = float("inf") if mean_d != 0 else 0.0
        p_val = 0.0 if mean_d != 0 else 1.0
    elif SCIPY_AVAILABLE:
        result = scipy_stats.ttest_rel(
            [a for a, _ in pairs], [b for _, b in pairs]
        )
        t_stat = round(float(result.statistic), 4)
        p_val = round(float(result.pvalue), 6)
    else:
        # Manual approximation via t-distribution CDF (two-tailed)
        t_stat = mean_d / se
        # Rough p-value via normal approximation for n > 30, otherwise warn
        p_val = _approx_pvalue_t(t_stat, df=n - 1)
        t_stat = round(t_stat, 4)
        p_val = round(p_val, 6)

    return {
        "t_statistic": t_stat,
        "p_value": p_val,
        "significant": p_val < 0.05,
        "n_pairs": n,
    }


def _approx_pvalue_t(t: float, df: int) -> float:
    """
    Approximate two-tailed p-value for t-distribution using a rational
    approximation. Reasonable for df >= 5. For research use, install scipy.
    """
    # Use normal approximation for large df
    abs_t = abs(t)
    if df >= 30:
        # Normal approximation
        z = abs_t
        p_one_tail = 0.5 * math.erfc(z / math.sqrt(2))
    else:
        # Simple rational approximation (Abramowitz & Stegun 26.7.8)
        x = df / (df + t * t)
        # Incomplete beta function approximation
        # Reasonably accurate for most practical purposes
        a = df / 2.0
        b = 0.5
        p_one_tail = _ibeta(x, a, b) / 2.0
    return min(1.0, 2 * p_one_tail)


def _ibeta(x: float, a: float, b: float) -> float:
    """Regularised incomplete beta function via continued fraction (rough)."""
    # Clamp
    x = max(0.0, min(1.0, x))
    if x == 0.0:
        return 0.0
    if x == 1.0:
        return 1.0
    # Use a simple series expansion for small x
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    log_factor = a * math.log(x) + b * math.log(1 - x) - lbeta
    # Continued fraction approximation (Lentz)
    eps = 1e-8
    max_iter = 200
    fpmin = 1e-30
    qab = a + b
    qap = a + 1
    qam = a - 1
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return math.exp(log_factor) * h / a


def _pearson(xs: list, ys: list) -> float | None:
    """Pearson correlation for pairwise inter-rater reliability."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 2:
        return None
    xs_, ys_ = [p[0] for p in pairs], [p[1] for p in pairs]
    mx, my = sum(xs_) / n, sum(ys_) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs_, ys_))
    den = math.sqrt(
        sum((x - mx) ** 2 for x in xs_) * sum((y - my) ** 2 for y in ys_)
    )
    return round(num / den, 4) if den > 0 else None


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------

def discover_rating_files(data_dir: Path) -> list[Path]:
    return sorted(data_dir.glob("blind_rating_results_*.json"))


def discover_key_files(data_dir: Path) -> list[Path]:
    return sorted(data_dir.glob("blind_rating_randomization_key_*.json"))


def load_json(path: Path) -> dict | list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Key merging (multiple sessions may each have their own key)
# ---------------------------------------------------------------------------

def merge_keys(key_files: list[Path]) -> dict:
    """
    Merge all randomization key files into a single mapping.
    Later files override earlier ones for the same scenario_id if conflicts exist.
    Also load the original blind_comparison_key.json as a fallback.
    """
    merged = {}
    data_dir = key_files[0].parent if key_files else Path("data")

    # Fallback: original key produced by generate_blind_comparison.py
    orig_key_path = data_dir / "blind_comparison_key.json"
    if orig_key_path.exists():
        orig = load_json(orig_key_path)
        for sid, mapping in orig.get("mapping", {}).items():
            merged[sid] = {
                "output_a": mapping.get("system_a"),
                "output_b": mapping.get("system_b"),
            }

    for kf in key_files:
        data = load_json(kf)
        for sid, mapping in data.get("mapping", {}).items():
            merged[sid] = mapping  # session-specific randomization takes precedence

    return merged


# ---------------------------------------------------------------------------
# Main aggregation
# ---------------------------------------------------------------------------

DIMENSIONS = ["pedagogical_clarity", "correctness", "appropriateness"]
SYSTEMS = ["full_system", "no_agent_baseline"]


def aggregate(data_dir: Path, out_path: Path):
    rating_files = discover_rating_files(data_dir)
    key_files = discover_key_files(data_dir)

    if not rating_files:
        print(f"[ERROR] No rating files found in {data_dir}")
        print("  Expected files matching: blind_rating_results_*.json")
        return

    if not key_files:
        print(
            "[WARN] No randomization key files found. "
            "Falling back to  data/blind_comparison_key.json  (original packet key)."
        )

    print(f"  Found {len(rating_files)} rater file(s).")
    print(f"  Found {len(key_files)} randomization key file(s).")

    # Build unified randomization key
    rand_key = merge_keys(key_files)

    # -----------------------------------------------------------------------
    # Load and unblind all ratings
    # -----------------------------------------------------------------------
    # Structure: per_scenario[scenario_id][rater_name] = {
    #     "baseline": {dim: score, ...},
    #     "full_system": {dim: score, ...},
    #     "preference": "full_system" | "no_agent_baseline" | "Tie"
    # }
    per_scenario: dict = defaultdict(dict)
    rater_names = []

    for rf in rating_files:
        data = load_json(rf)
        rater = data.get("rater", rf.stem)
        rater_names.append(rater)
        print(f"    Loading ratings from rater: {rater} ({rf.name})")

        for rating in data.get("ratings", []):
            sid = rating["scenario_id"]
            mapping = rand_key.get(sid, {})
            system_of_a = mapping.get("output_a") or mapping.get("system_a", "system_a")
            system_of_b = mapping.get("output_b") or mapping.get("system_b", "system_b")

            # Map rater's scores to canonical system names
            scores_by_system = {}
            scores_by_system[system_of_a] = rating.get("output_a_scores", {})
            scores_by_system[system_of_b] = rating.get("output_b_scores", {})

            # Translate overall preference (A/B → system name)
            raw_pref = rating.get("overall_preference", "")
            if raw_pref.upper() == "A":
                preference_system = system_of_a
            elif raw_pref.upper() == "B":
                preference_system = system_of_b
            else:
                preference_system = "Tie"

            per_scenario[sid][rater] = {
                "scores_by_system": scores_by_system,
                "preference": preference_system,
            }

    # -----------------------------------------------------------------------
    # Build per-scenario aggregates
    # -----------------------------------------------------------------------
    scenario_ids = sorted(per_scenario.keys())
    num_raters = len(rater_names)

    # Collect vectors for paired t-tests (full_system vs baseline per dim)
    # Each list has one value per (scenario, rater) pair
    dim_scores_by_system: dict[str, dict[str, list]] = {
        dim: {sys: [] for sys in SYSTEMS} for dim in DIMENSIONS
    }

    # For preference t-test: encode full_system=1, tie=0, baseline=-1
    pref_scores_full = []
    pref_scores_base = []

    per_scenario_results = []
    pref_counter_total = {"full_system": 0, "no_agent_baseline": 0, "Tie": 0}

    for sid in scenario_ids:
        rater_data = per_scenario[sid]

        # Accumulate scores per system per dimension across raters
        sys_dim_scores: dict[str, dict[str, list]] = {
            sys: {dim: [] for dim in DIMENSIONS} for sys in SYSTEMS
        }
        pref_votes: dict[str, int] = {"full_system": 0, "no_agent_baseline": 0, "Tie": 0}

        for rater, rd in rater_data.items():
            sbys = rd["scores_by_system"]
            for sys in SYSTEMS:
                scores_dict = sbys.get(sys, {})
                for dim in DIMENSIONS:
                    val = scores_dict.get(dim)
                    if val is not None:
                        sys_dim_scores[sys][dim].append(val)
                        dim_scores_by_system[dim][sys].append(val)

            pref = rd["preference"]
            if pref in pref_votes:
                pref_votes[pref] += 1
                pref_counter_total[pref] += 1

        # Determine scenario winner
        if pref_votes["full_system"] > pref_votes["no_agent_baseline"]:
            winner = "full_system"
        elif pref_votes["no_agent_baseline"] > pref_votes["full_system"]:
            winner = "no_agent_baseline"
        else:
            winner = "Tie"

        # Mean scores per system
        def mean_scores(sys):
            return {
                dim: _mean(sys_dim_scores[sys][dim])
                for dim in DIMENSIONS
            }

        per_scenario_results.append({
            "scenario_id": sid,
            "baseline_avg_scores": mean_scores("no_agent_baseline"),
            "full_system_avg_scores": mean_scores("full_system"),
            "preference_winner": winner,
            "preference_vote_count": {
                "full_system": pref_votes["full_system"],
                "baseline": pref_votes["no_agent_baseline"],
                "tie": pref_votes["Tie"],
            },
        })

    # -----------------------------------------------------------------------
    # Aggregate scores across all scenarios
    # -----------------------------------------------------------------------
    def agg_stats(sys, dim):
        vals = dim_scores_by_system[dim][sys]
        return {"mean": _mean(vals), "std": _std(vals)}

    aggregate_scores = {
        sys: {dim: agg_stats(sys, dim) for dim in DIMENSIONS}
        for sys in SYSTEMS
    }

    # Friendly aliases for output format
    aggregate_scores_out = {
        "baseline": {
            "pedagogical_clarity": aggregate_scores["no_agent_baseline"]["pedagogical_clarity"],
            "correctness": aggregate_scores["no_agent_baseline"]["correctness"],
            "appropriateness": aggregate_scores["no_agent_baseline"]["appropriateness"],
        },
        "full_system": {
            "pedagogical_clarity": aggregate_scores["full_system"]["pedagogical_clarity"],
            "correctness": aggregate_scores["full_system"]["correctness"],
            "appropriateness": aggregate_scores["full_system"]["appropriateness"],
        },
    }

    # -----------------------------------------------------------------------
    # Win / Loss / Tie counts
    # -----------------------------------------------------------------------
    total_scenario_ratings = sum(pref_counter_total.values())
    win_rate = (
        round(pref_counter_total["full_system"] / total_scenario_ratings, 4)
        if total_scenario_ratings
        else 0.0
    )

    preference_counts = {
        "full_system_wins": pref_counter_total["full_system"],
        "baseline_wins": pref_counter_total["no_agent_baseline"],
        "ties": pref_counter_total["Tie"],
        "full_system_win_rate": win_rate,
    }

    # -----------------------------------------------------------------------
    # Statistical significance tests (paired t-test per dimension)
    # -----------------------------------------------------------------------
    statistical_tests = {}
    for dim in DIMENSIONS:
        full_vals = dim_scores_by_system[dim]["full_system"]
        base_vals = dim_scores_by_system[dim]["no_agent_baseline"]
        result = _paired_ttest(full_vals, base_vals)
        statistical_tests[dim] = result if result else {
            "t_statistic": None,
            "p_value": None,
            "significant": None,
            "note": "Insufficient data for statistical test",
        }

    # -----------------------------------------------------------------------
    # Inter-rater reliability (pairwise Pearson, averaged)
    # -----------------------------------------------------------------------
    irr_report = None
    if num_raters >= 2:
        # Build per-rater vectors over all scenarios and dimensions
        rater_vectors: dict[str, list] = {r: [] for r in rater_names}
        for sid in scenario_ids:
            for sys in SYSTEMS:
                for dim in DIMENSIONS:
                    for rater in rater_names:
                        rd = per_scenario[sid].get(rater, {})
                        val = rd.get("scores_by_system", {}).get(sys, {}).get(dim)
                        rater_vectors[rater].append(val)

        pairwise_r = []
        rnames = list(rater_names)
        for i in range(len(rnames)):
            for j in range(i + 1, len(rnames)):
                r = _pearson(rater_vectors[rnames[i]], rater_vectors[rnames[j]])
                if r is not None:
                    pairwise_r.append(r)

        irr_report = {
            "method": "mean_pairwise_pearson_r",
            "num_raters": num_raters,
            "mean_r": _mean(pairwise_r),
            "pairwise_correlations": pairwise_r,
        }

    # -----------------------------------------------------------------------
    # Build final report
    # -----------------------------------------------------------------------
    key_files_used = [str(kf) for kf in key_files] if key_files else [
        str(data_dir / "blind_comparison_key.json")
    ]

    report = {
        "meta": {
            "num_raters": num_raters,
            "rater_names": rater_names,
            "num_scenarios": len(scenario_ids),
            "rating_date": date.today().isoformat(),
            "randomization_keys_used": key_files_used,
            "rating_files_used": [str(rf) for rf in rating_files],
            "scipy_used": SCIPY_AVAILABLE,
        },
        "aggregate_scores": aggregate_scores_out,
        "preference_counts": preference_counts,
        "statistical_tests": statistical_tests,
        "inter_rater_reliability": irr_report,
        "per_scenario_results": per_scenario_results,
    }

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # -----------------------------------------------------------------------
    # Print summary
    # -----------------------------------------------------------------------
    print()
    print("=" * 72)
    print("   Blind Comparison Aggregation — Summary")
    print("=" * 72)
    print(f"  Raters     : {num_raters}  ({', '.join(rater_names)})")
    print(f"  Scenarios  : {len(scenario_ids)}")
    print()
    print("  Aggregate scores (mean across all raters & scenarios):")
    print(f"  {'Dimension':<30} {'Baseline':>12} {'Full System':>12}")
    print("  " + "-" * 56)
    dim_labels = {
        "pedagogical_clarity": "Pedagogical Clarity",
        "correctness": "Correctness",
        "appropriateness": "Skill-Level Appropriateness",
    }
    for dim, label in dim_labels.items():
        bm = aggregate_scores_out["baseline"][dim]["mean"]
        fm = aggregate_scores_out["full_system"][dim]["mean"]
        bm_s = f"{bm:.2f}" if bm is not None else "N/A"
        fm_s = f"{fm:.2f}" if fm is not None else "N/A"
        print(f"  {label:<30} {bm_s:>12} {fm_s:>12}")

    print()
    print(f"  Overall preference (across all rater × scenario votes):")
    print(f"    Full System wins : {preference_counts['full_system_wins']}")
    print(f"    Baseline wins    : {preference_counts['baseline_wins']}")
    print(f"    Ties             : {preference_counts['ties']}")
    print(f"    Full System win rate : {preference_counts['full_system_win_rate']:.1%}")

    print()
    print("  Statistical significance (paired t-test, full_system vs baseline):")
    for dim, label in dim_labels.items():
        res = statistical_tests[dim]
        if res.get("t_statistic") is not None:
            sig = "[OK] p<0.05" if res["significant"] else "[--] not sig."
            print(f"    {label:<30}  t={res['t_statistic']:6.3f}  p={res['p_value']:.4f}  {sig}")
        else:
            print(f"    {label:<30}  (insufficient data)")

    if irr_report and irr_report.get("mean_r") is not None:
        print()
        mr = irr_report["mean_r"]
        print(f"  Inter-rater reliability (mean pairwise Pearson r): {mr:.3f}")

    print()
    print(f"  Report saved to:\n    {out_path}")
    print("=" * 72)


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Aggregate blind rating files into a final evaluation report."
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory containing rating files and key files (default: data/)",
    )
    parser.add_argument(
        "--out",
        default="data/blind_rating_results.json",
        help="Output path for the aggregated report (default: data/blind_rating_results.json)",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    out_path = Path(args.out)

    if not data_dir.exists():
        print(f"[ERROR] Data directory not found: {data_dir}")
        return

    aggregate(data_dir, out_path)


if __name__ == "__main__":
    main()
