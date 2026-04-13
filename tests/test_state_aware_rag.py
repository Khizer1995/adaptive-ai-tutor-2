from core.rag.query_engineering import RAGQueryEngineer


def test_state_aware_query_engineering_includes_scope_and_scaffold():
    engineer = RAGQueryEngineer()
    query = engineer.engineer(
        "Explain arrays in Python",
        {
            "level": "beginner",
            "engagement": "low",
            "macro_decision": {
                "target_concepts": ["arrays"],
                "scaffold_policy": "high",
            },
        },
    )
    assert "concept_scope: arrays" in query
    assert "scaffold: high" in query
