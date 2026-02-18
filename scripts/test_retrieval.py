from core.rag.retriever import Retriever

if __name__ == "__main__":

    retriever = Retriever()

    results = retriever.retrieve(
        "Explain Python variables for beginner level",
        k=3
    )

    print("\n--- Retrieved Chunks ---\n")

    for idx, chunk in enumerate(results):
        print(f"\nChunk {idx+1}:\n")
        print(chunk)
        print("\n-------------------------\n")
