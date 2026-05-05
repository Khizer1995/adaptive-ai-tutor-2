from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup

from core.curriculum_config import OPENDSA_PAGE_MAP
from core.logging_utils import get_logger
from core.layered_kb.retrieval import AdaptiveRetriever


class HybridRetriever:
    def __init__(self) -> None:
        self.layered = AdaptiveRetriever()
        self.logger = get_logger("hybrid_retriever", "rag.log")
        self.cache_dir = Path("data/opendsa_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.error_log = Path("logs/retrieval_errors.jsonl")
        self.cache_ttl_seconds = 24 * 60 * 60

    @staticmethod
    def _subtopic_key(student_state: Dict[str, Any], topic: str) -> str:
        return str(student_state.get("current_subtopic") or f"{topic}_introduction")

    def _fetch_opendsa(self, subtopic: str) -> Dict[str, Any]:
        page = OPENDSA_PAGE_MAP.get(subtopic)
        if not page:
            return {"prose": "", "code_blocks": [], "tables": []}

        cache_path = self.cache_dir / f"{subtopic}.json"
        if cache_path.exists():
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            if time.time() - float(payload.get("fetched_at", 0)) < self.cache_ttl_seconds:
                return payload.get("data", {})

        url = f"https://opendsa-server.cs.vt.edu/ODSA/Books/Everything/html/{page}.html"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        root = soup.select_one("#main-content") or soup

        prose = "\n\n".join(
            p.get_text(" ", strip=True)
            for p in root.select("p")
            if p.get_text(" ", strip=True)
        )
        code_blocks = [
            node.get_text("\n", strip=True)
            for node in root.select("pre, code")
            if node.get_text("\n", strip=True)
        ][:4]
        tables = [
            node.get_text(" ", strip=True)
            for node in root.select("table")
            if node.get_text(" ", strip=True)
        ][:2]
        data = {"prose": prose, "code_blocks": code_blocks, "tables": tables}
        cache_path.write_text(
            json.dumps({"fetched_at": time.time(), "data": data}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return data

    def _log_fetch_error(self, subtopic: str, err: Exception) -> None:
        self.error_log.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": time.time(),
            "subtopic": subtopic,
            "error": str(err),
        }
        with self.error_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    @staticmethod
    def _blend(pdf_chunks: List[str], opendsa_text: str, mastery: float) -> List[str]:
        if mastery < 0.4:
            pdf_take, web_take = 7, 3
        elif mastery <= 0.7:
            pdf_take, web_take = 5, 5
        else:
            pdf_take, web_take = 3, 7

        selected_pdf = pdf_chunks[:pdf_take]
        selected_web: List[str] = []
        if opendsa_text:
            parts = [p.strip() for p in opendsa_text.split("\n\n") if p.strip()]
            selected_web = parts[:web_take]
        return selected_pdf + selected_web

    @staticmethod
    def prompt_guidance(mastery: float) -> str:
        if mastery < 0.4:
            return (
                "Explain this in very simple terms with analogies. "
                "Avoid jargon. Use a real-world example first."
            )
        if mastery <= 0.7:
            return (
                "Give a clear explanation with one example and "
                "show the core operations step by step."
            )
        return (
            "Give a concise explanation focused on "
            "implementation details, edge cases, and complexity analysis."
        )

    def retrieve_context(
        self,
        query: str,
        topic: str,
        student_state: Dict[str, Any],
        k: int = 6,
        allowed_chunk_ids: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        mastery = float(
            student_state.get("knowledge_state", {})
            .get("concepts", {})
            .get(topic, {})
            .get("mastery", student_state.get("last_score", 0.4))
        )
        layered_state = {
            "topic": topic,
            "student_mastery": mastery,
            "confidence": float(student_state.get("knowledge_state", {}).get("concepts", {}).get(topic, {}).get("confidence", 0.5)),
            "learning_trend": "steady",
        }
        where = {"chunk_id": {"$in": allowed_chunk_ids}} if allowed_chunk_ids else None
        pdf_records = self.layered.retrieve(query=query, student_state=layered_state, k=max(6, k), where=where)
        pdf_chunks = [str(item.get("content", "")).strip() for item in pdf_records if str(item.get("content", "")).strip()]

        subtopic = self._subtopic_key(student_state, topic)
        opendsa_data: Dict[str, Any] = {"prose": "", "code_blocks": [], "tables": []}
        try:
            opendsa_data = self._fetch_opendsa(subtopic)
        except Exception as exc:
            self._log_fetch_error(subtopic, exc)
            self.logger.warning(f"opendsa_fetch_failed subtopic={subtopic} error={exc}")

        web_text = "\n\n".join(
            [opendsa_data.get("prose", "")]
            + [f"Code:\n{c}" for c in opendsa_data.get("code_blocks", [])]
            + [f"Table:\n{t}" for t in opendsa_data.get("tables", [])]
        ).strip()
        merged = self._blend(pdf_chunks, web_text, mastery)

        records: List[Dict[str, Any]] = []
        for idx, txt in enumerate(merged):
            records.append(
                {
                    "chunk_id": f"hybrid_{idx}",
                    "content": txt,
                    "metadata": {
                        "source": "merged",
                        "prompt_guidance": self.prompt_guidance(mastery),
                    },
                }
            )
        return records
