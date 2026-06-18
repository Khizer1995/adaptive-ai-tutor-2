from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Dict, Iterable, List, Optional


ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = ROOT / "logs"
DATA_DIR = ROOT / "data"
PROFILES_DIR = ROOT / "profiles"
OUTPUT_PATH = DATA_DIR / "eval_report.json"

METRICS_LOG = LOGS_DIR / "metrics_log.jsonl"
VALIDATION_LOG = LOGS_DIR / "validation_log.jsonl"
SURVEY_LOG = DATA_DIR / "survey_responses.jsonl"

BASE_BENCHMARKS = {
    "rag_latency_seconds": "147.63s",
    "crewai_latency_seconds": "90.15s",
    "validation_score": "qualitative only",
    "decision_iterations": "minimal",
}

USABILITY_ITEMS = {
    "usability_easy_to_use",
    "usability_clear_explanations",
    "usability_quiz_alignment",
    "usability_adapted_level",
    "usability_use_again",
}
ADAPTATION_ITEMS = {
    "usability_adapted_level",
    "trust_hints",
    "trust_learning_needs",
    "engagement_difficulty",
}
ENGAGEMENT_ITEMS = {
    "engagement_throughout",
    "engagement_difficulty",
    "engagement_progress",
}


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                records.append(parsed)
    return records


def read_profiles() -> List[Dict[str, Any]]:
    if not PROFILES_DIR.exists():
        return []

    profiles: List[Dict[str, Any]] = []
    for path in sorted(PROFILES_DIR.glob("*.json")):
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(parsed, dict):
            parsed["_profile_path"] = str(path.relative_to(ROOT))
            profiles.append(parsed)
    return profiles


def as_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def values(records: Iterable[Dict[str, Any]], key: str) -> List[float]:
    output: List[float] = []
    for record in records:
        number = as_float(record.get(key))
        if number is not None:
            output.append(number)
    return output


def summarize_numbers(numbers: List[float]) -> Dict[str, Any]:
    if not numbers:
        return {"mean": None, "std": None, "count": 0}
    return {
        "mean": round(mean(numbers), 4),
        "std": round(stdev(numbers), 4) if len(numbers) > 1 else 0.0,
        "count": len(numbers),
    }


def percent(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.2f}%"


def mean_std_text(summary: Dict[str, Any], unit: str = "") -> str:
    if summary["mean"] is None:
        return "N/A"
    return f"{summary['mean']:.4f} ± {summary['std']:.4f}{unit}"


def validation_scores(metrics: List[Dict[str, Any]], validations: List[Dict[str, Any]]) -> List[float]:
    metric_scores = values(metrics, "validation_score")
    if metric_scores:
        return metric_scores

    scores: List[float] = []
    for record in validations:
        direct = as_float(record.get("score"))
        if direct is not None:
            scores.append(direct)
            continue
        result = record.get("validation_result", {})
        if isinstance(result, dict):
            nested = as_float(result.get("score"))
            if nested is not None:
                scores.append(nested)
    return scores


def expected_scaffolding_direction(record: Dict[str, Any]) -> str:
    score = as_float(record.get("quiz_pass_rate"))
    if score is None:
        score = as_float(record.get("validation_score"))
    if score is None:
        return "unknown"
    if score < 0.5:
        return "increased_support"
    if score >= 0.75:
        return "advanced"
    return "maintained"


def scaffolding_accuracy(metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
    comparable = 0
    correct = 0
    for record in metrics:
        actual = str(record.get("scaffolding_direction") or "")
        expected = expected_scaffolding_direction(record)
        if not actual or expected == "unknown":
            continue
        comparable += 1
        if actual == expected:
            correct += 1

    return {
        "accuracy": round(correct / comparable, 4) if comparable else None,
        "correct": correct,
        "count": comparable,
        "rule": "quiz_pass_rate < 0.50 => increased_support; >= 0.75 => advanced; otherwise maintained",
    }


def assessment_pairs_from_profile(profile: Dict[str, Any]) -> List[Dict[str, float]]:
    pairs: List[Dict[str, float]] = []
    top_pre = as_float(profile.get("pretest_score"))
    top_post = as_float(profile.get("posttest_score"))
    if top_pre is not None and top_post is not None:
        pairs.append(
            {
                "pretest_score": top_pre,
                "posttest_score": top_post,
                "learning_gain": as_float(profile.get("learning_gain")) or round(top_post - top_pre, 4),
                "normalized_learning_gain": as_float(profile.get("normalized_learning_gain"))
                or normalized_gain(top_pre, top_post),
            }
        )

    assessment_scores = profile.get("assessment_scores", {})
    if not isinstance(assessment_scores, dict):
        return pairs

    for topic_data in assessment_scores.values():
        if not isinstance(topic_data, dict):
            continue
        for entry in topic_data.values():
            if not isinstance(entry, dict):
                continue
            pre = as_float(entry.get("pretest_score"))
            post = as_float(entry.get("posttest_score"))
            if pre is None or post is None:
                continue
            pair = {
                "pretest_score": pre,
                "posttest_score": post,
                "learning_gain": as_float(entry.get("learning_gain")) or round(post - pre, 4),
                "normalized_learning_gain": as_float(entry.get("normalized_learning_gain"))
                or normalized_gain(pre, post),
            }
            if pair not in pairs:
                pairs.append(pair)
    return pairs


def normalized_gain(pretest: float, posttest: float) -> float:
    denominator = 1.0 - pretest
    if denominator <= 0:
        return 0.0
    return round((posttest - pretest) / denominator, 4)


def learning_outcomes(profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
    participant_rows: List[Dict[str, float]] = []
    for profile in profiles:
        pairs = assessment_pairs_from_profile(profile)
        if not pairs:
            continue
        participant_rows.append(
            {
                "pretest_score": mean([pair["pretest_score"] for pair in pairs]),
                "posttest_score": mean([pair["posttest_score"] for pair in pairs]),
                "learning_gain": mean([pair["learning_gain"] for pair in pairs]),
                "normalized_learning_gain": mean([pair["normalized_learning_gain"] for pair in pairs]),
            }
        )

    return {
        "participants": len(participant_rows),
        "mean_pretest_score": summarize_numbers(values(participant_rows, "pretest_score"))["mean"],
        "mean_posttest_score": summarize_numbers(values(participant_rows, "posttest_score"))["mean"],
        "mean_learning_gain": summarize_numbers(values(participant_rows, "learning_gain"))["mean"],
        "mean_hake_normalized_gain": summarize_numbers(values(participant_rows, "normalized_learning_gain"))["mean"],
    }


def survey_dimension_mean(records: List[Dict[str, Any]], item_ids: set[str]) -> Optional[float]:
    participant_means: List[float] = []
    for record in records:
        responses = record.get("responses", {})
        if not isinstance(responses, dict):
            continue
        item_values = [
            number
            for item_id in item_ids
            if (number := as_float(responses.get(item_id))) is not None
        ]
        if item_values:
            participant_means.append(mean(item_values))
    if not participant_means:
        return None
    return round(mean(participant_means), 4)


def user_study(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "participants": len(records),
        "dimensions": {
            "usability": survey_dimension_mean(records, USABILITY_ITEMS),
            "adaptation": survey_dimension_mean(records, ADAPTATION_ITEMS),
            "engagement": survey_dimension_mean(records, ENGAGEMENT_ITEMS),
        },
    }


def system_metrics(metrics: List[Dict[str, Any]], validations: List[Dict[str, Any]]) -> Dict[str, Any]:
    rag_seconds = [number / 1000 for number in values(metrics, "rag_latency_ms")]
    crew_seconds = [number / 1000 for number in values(metrics, "crewai_latency_ms")]
    decisions = values(metrics, "decision_iterations")
    scaffolding = scaffolding_accuracy(metrics)
    return {
        "rag_latency_seconds": summarize_numbers(rag_seconds),
        "crewai_latency_seconds": summarize_numbers(crew_seconds),
        "validation_score": summarize_numbers(validation_scores(metrics, validations)),
        "decision_iterations": summarize_numbers(decisions),
        "scaffolding_accuracy": scaffolding,
        "base_paper_benchmarks": BASE_BENCHMARKS,
    }


def print_table(title: str, rows: List[List[str]]) -> None:
    print(f"\n{title}")
    if not rows:
        print("  No data available.")
        return
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    for index, row in enumerate(rows):
        line = " | ".join(cell.ljust(widths[column]) for column, cell in enumerate(row))
        print(line)
        if index == 0:
            print("-+-".join("-" * width for width in widths))


def build_report() -> Dict[str, Any]:
    metrics = read_jsonl(METRICS_LOG)
    validations = read_jsonl(VALIDATION_LOG)
    surveys = read_jsonl(SURVEY_LOG)
    profiles = read_profiles()

    return {
        "inputs": {
            "metrics_log": str(METRICS_LOG.relative_to(ROOT)),
            "validation_log": str(VALIDATION_LOG.relative_to(ROOT)),
            "survey_responses": str(SURVEY_LOG.relative_to(ROOT)),
            "profiles_dir": str(PROFILES_DIR.relative_to(ROOT)),
            "records": {
                "metrics": len(metrics),
                "validations": len(validations),
                "survey_responses": len(surveys),
                "profiles": len(profiles),
            },
        },
        "system_metrics": system_metrics(metrics, validations),
        "learning_outcomes": learning_outcomes(profiles),
        "user_study": user_study(surveys),
    }


def print_report(report: Dict[str, Any]) -> None:
    system = report["system_metrics"]
    print_table(
        "SYSTEM METRICS (vs base paper benchmarks)",
        [
            ["Metric", "Current", "Base Paper"],
            [
                "RAG latency",
                mean_std_text(system["rag_latency_seconds"], "s"),
                BASE_BENCHMARKS["rag_latency_seconds"],
            ],
            [
                "CrewAI latency",
                mean_std_text(system["crewai_latency_seconds"], "s"),
                BASE_BENCHMARKS["crewai_latency_seconds"],
            ],
            [
                "Validation score",
                mean_std_text(system["validation_score"]),
                BASE_BENCHMARKS["validation_score"],
            ],
            [
                "Decision iterations",
                "N/A" if system["decision_iterations"]["mean"] is None else f"{system['decision_iterations']['mean']:.4f}",
                BASE_BENCHMARKS["decision_iterations"],
            ],
            [
                "Scaffolding accuracy",
                percent(system["scaffolding_accuracy"]["accuracy"]),
                f"{system['scaffolding_accuracy']['correct']}/{system['scaffolding_accuracy']['count']} aligned",
            ],
        ],
    )

    learning = report["learning_outcomes"]
    print_table(
        f"LEARNING OUTCOMES (N={learning['participants']} participants)",
        [
            ["Metric", "Mean"],
            ["Mean pretest score", percent(learning["mean_pretest_score"])],
            ["Mean posttest score", percent(learning["mean_posttest_score"])],
            ["Mean learning gain", percent(learning["mean_learning_gain"])],
            ["Mean Hake normalized gain", percent(learning["mean_hake_normalized_gain"])],
        ],
    )

    study = report["user_study"]
    dimensions = study["dimensions"]
    print_table(
        f"USER STUDY (N={study['participants']})",
        [
            ["Dimension", "Mean Likert"],
            ["Usability", "N/A" if dimensions["usability"] is None else f"{dimensions['usability']:.4f} / 5"],
            ["Adaptation", "N/A" if dimensions["adaptation"] is None else f"{dimensions['adaptation']:.4f} / 5"],
            ["Engagement", "N/A" if dimensions["engagement"] is None else f"{dimensions['engagement']:.4f} / 5"],
        ],
    )


def main() -> None:
    report = build_report()
    print_report(report)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nExported report: {OUTPUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
