import argparse
from pathlib import Path
from typing import List

from core.layered_kb.builder import LayeredKnowledgeBuilder


DEFAULT_OPEN_DSA_URLS = [
    "https://opendsa-server.cs.vt.edu/ODSA/Books/Everything/html/ListArray.html",
    "https://opendsa-server.cs.vt.edu/ODSA/Books/Everything/html/BinarySearch.html",
    "https://opendsa-server.cs.vt.edu/ODSA/Books/Everything/html/Queue.html",
    "https://opendsa-server.cs.vt.edu/ODSA/Books/Everything/html/QueueLinked.html",
]


def load_urls(url_file: str | None) -> List[str]:
    if not url_file:
        return DEFAULT_OPEN_DSA_URLS
    path = Path(url_file)
    if not path.exists():
        return DEFAULT_OPEN_DSA_URLS
    urls = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [u for u in urls if u and not u.startswith("#")]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build layered DSA knowledge base.")
    parser.add_argument("--opendsa-urls-file", default="data/raw/opendsa_urls.txt")
    parser.add_argument("--pdf-dir", default="data/raw")
    args = parser.parse_args()

    urls = load_urls(args.opendsa_urls_file)
    builder = LayeredKnowledgeBuilder()
    stats = builder.build_from_sources(opendsa_urls=urls, pdf_raw_dir=args.pdf_dir)
    print("Layered KB build complete:")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()

