from core.layered_kb.retrieval import AdaptiveRetriever


def main() -> None:
    retriever = AdaptiveRetriever()

    query = "Explain stack operations with examples"
    student_state = {
        "topic": "stack",
        "student_mastery": 0.62,
        "confidence": 0.59,
        "learning_trend": "fluctuating",
    }
    results = retriever.retrieve(query=query, student_state=student_state, k=4)
    for i, r in enumerate(results, start=1):
        meta = r["metadata"]
        print(f"{i}. score={r['score']} source={meta.get('source')} type={meta.get('type')}")
        print(f"   concept={meta.get('concept')} difficulty={meta.get('difficulty')}")
        print(f"   {r['content'][:160]}...")


if __name__ == "__main__":
    main()

