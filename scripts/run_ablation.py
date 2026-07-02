import os
import json
import time
import builtins
import math
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bypassing interactive teacher review
builtins.input = lambda *args, **kwargs: "approve"

# Ensure we run exactly one cycle in the langgraph flow by overriding route_after_profile
import core.langgraph_flow
core.langgraph_flow.route_after_profile = lambda state: "end_learning"

from core.decision_engine import AblationConfig
from core.langgraph_flow import build_adaptive_graph
from core.metrics_collector import _scaffolding_direction
from core.layered_kb.retrieval import AdaptiveRetriever


def cosine_similarity(v1, v2):
    dot = sum(x * y for x, y in zip(v1, v2))
    norm1 = sum(x * x for x in v1) ** 0.5
    norm2 = sum(x * x for x in v2) ** 0.5
    if norm1 > 0 and norm2 > 0:
        return dot / (norm1 * norm2)
    return 0.0


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


def safe_serialize(obj):
    """Safely serialize objects to JSON, converting non-serializable elements to strings."""
    if isinstance(obj, dict):
        return {k: safe_serialize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [safe_serialize(x) for x in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    else:
        return str(obj)


def main():
    print("=" * 70)
    print("   Cognitive Adaptive AI Tutor — Pipeline Ablation Study")
    print("=" * 70)

    # Paths
    fixtures_path = Path("data/ablation_fixtures.json")
    report_path = Path("data/ablation_report.json")
    raw_logs_path = Path("data/ablation_raw_logs.json")

    # Load fixtures
    if not fixtures_path.exists():
        print(f"Error: Fixtures file not found at {fixtures_path}")
        return
    
    with open(fixtures_path, "r", encoding="utf-8") as f:
        scenarios = json.load(f)
    print(f"Loaded {len(scenarios)} scenarios from fixtures.")

    # Instantiate adaptive retriever to reuse embedder for relevance metrics
    retriever = AdaptiveRetriever()
    embedder = retriever.embedder

    # Configurations definition
    configs = {
        "full_system": AblationConfig(use_arbitration=True, use_mastery_rerank=True, use_validation=True),
        "no_arbitration": AblationConfig(use_arbitration=False, use_mastery_rerank=True, use_validation=True),
        "no_mastery_rerank": AblationConfig(use_arbitration=True, use_mastery_rerank=False, use_validation=True),
        "no_validation": AblationConfig(use_arbitration=True, use_mastery_rerank=True, use_validation=False),
    }

    report_data = {"configurations": {}}
    all_raw_logs = []

    # Iterate over configurations
    for config_name, ablation_config in configs.items():
        print(f"\nRunning configuration: {config_name}...")
        print("-" * 50)
        
        # Build the dynamic graph with the current ablation config
        graph = build_adaptive_graph(ablation_config)
        
        config_runs = []
        
        # Run scenarios
        for idx, scenario in enumerate(scenarios):
            scenario_id = scenario["scenario_id"]
            concept = scenario["concept"]
            ideal_chunk_content = scenario["ideal_chunk_content"]
            profile = scenario["student_profile"].copy()

            print(f"  [{idx+1}/{len(scenarios)}] Running {scenario_id}...")

            # Initialize pipeline state
            initial_state = {
                "student_state": profile,
                "decision": {},
                "macro_decision": {},
                "crew_output": {},
                "crew_proposals": [],
                "execution_feedback": {},
                "decision_trace": [],
                "arbitration_trace": {},
                "rag_status": {},
                "teacher_review": {}
            }

            # Run with timing
            start_time = time.perf_counter()
            try:
                final_state = graph.invoke(initial_state)
                latency = round(time.perf_counter() - start_time, 4)
            except Exception as e:
                print(f"    [ERROR] Failed to run scenario {scenario_id}: {e}")
                continue

            # Process decisions
            macro_decision = final_state.get("macro_decision", {}) or {}
            micro_decision = final_state.get("decision", {}) or {}
            crew_output = final_state.get("crew_output", {}) or {}

            # 1. Scaffolding Direction & Accuracy
            actual_dir = _scaffolding_direction(micro_decision, macro_decision)
            
            # Expected based on input quiz_pass_rate / last_score
            score = profile.get("last_score", 0.0)
            if score < 0.5:
                expected_dir = "increased_support"
            elif score >= 0.75:
                expected_dir = "advanced"
            else:
                expected_dir = "maintained"
                
            scaffold_acc = 1.0 if actual_dir == expected_dir else 0.0

            # 2. Decision Iterations
            dec_iters = len(final_state.get("decision_trace", []))

            # 3. Retrieval Relevance
            rag_chunks = crew_output.get("rag_chunk_records", []) or crew_output.get("rag_chunks", [])
            max_sim = 0.0
            
            if ideal_chunk_content and rag_chunks:
                ideal_emb = embedder.embed(ideal_chunk_content)
                for chunk in rag_chunks:
                    chunk_text = ""
                    if isinstance(chunk, dict):
                        chunk_text = chunk.get("content") or chunk.get("text") or ""
                    else:
                        chunk_text = str(chunk)
                    
                    if chunk_text.strip():
                        chunk_emb = embedder.embed(chunk_text)
                        sim = cosine_similarity(ideal_emb, chunk_emb)
                        if sim > max_sim:
                            max_sim = sim

            # 4. Validation Catch Rate
            validation_status = crew_output.get("validation_status", "passed")
            validation_failed = 1.0 if validation_status == "failed" else 0.0

            # Per-scenario trial record
            run_record = {
                "scenario_id": scenario_id,
                "macro_decision": macro_decision.get("macro_action"),
                "micro_decision": micro_decision.get("action"),
                "selected_proposal_owner": crew_output.get("owner_agent"),
                "validation_status": validation_status,
                "scaffolding_accuracy": scaffold_acc,
                "decision_iterations": dec_iters,
                "retrieval_relevance": round(max_sim, 4),
                "latency_seconds": latency
            }
            config_runs.append(run_record)

            # Record raw logs
            all_raw_logs.append({
                "scenario_id": scenario_id,
                "configuration": config_name,
                "final_state": safe_serialize(final_state)
            })

        # Calculate Aggregate Metrics
        scaffold_accs = [r["scaffolding_accuracy"] for r in config_runs]
        dec_iters_list = [r["decision_iterations"] for r in config_runs]
        relevances = [r["retrieval_relevance"] for r in config_runs]
        latencies = [r["latency_seconds"] for r in config_runs]
        val_failures = [1.0 if r["validation_status"] == "failed" else 0.0 for r in config_runs]

        metrics = {
            "scaffolding_accuracy": {
                "mean": round(mean(scaffold_accs), 4),
                "stddev": round(stddev(scaffold_accs), 4)
            },
            "decision_iterations": {
                "mean": round(mean(dec_iters_list), 4),
                "stddev": round(stddev(dec_iters_list), 4)
            },
            "retrieval_relevance": {
                "mean": round(mean(relevances), 4),
                "stddev": round(stddev(relevances), 4)
            },
            "validation_catch_rate": round(mean(val_failures), 4) if config_name == "full_system" else None,
            "response_latency": {
                "mean": round(mean(latencies), 4),
                "stddev": round(stddev(latencies), 4)
            }
        }

        report_data["configurations"][config_name] = {
            "metrics": metrics,
            "scenarios": config_runs
        }

        print(f"Finished {config_name} runs.")
        print(f"Scaffolding Accuracy: {metrics['scaffolding_accuracy']['mean']}")
        print(f"Retrieval Relevance:  {metrics['retrieval_relevance']['mean']}")
        print(f"Mean Latency:         {metrics['response_latency']['mean']}s")

    # Save outputs
    print("\nSaving ablation study results...")
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    print(f"Report saved to {report_path}")

    with open(raw_logs_path, "w", encoding="utf-8") as f:
        json.dump(all_raw_logs, f, ensure_ascii=False, indent=2)
    print(f"Raw logs saved to {raw_logs_path}")

    print("\nAblation Study Completed Successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()
