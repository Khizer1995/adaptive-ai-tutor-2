from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List

import pdfplumber

from core.layered_kb.chunking import (
    concept_key,
    infer_content_type,
    infer_difficulty,
    normalize_topic,
    sanitize_text,
)
from core.layered_kb.schema import KBChunk


class PDFIngestionPipeline:
    def ingest_dir(self, raw_dir: str) -> List[KBChunk]:
        root = Path(raw_dir)
        pdf_files = sorted(root.glob("*.pdf"))
        chunks: List[KBChunk] = []
        for file_idx, pdf_path in enumerate(pdf_files):
            chunks.extend(self.ingest_pdf(pdf_path, order_seed=file_idx * 1000))
        return chunks

    def ingest_pdf(self, pdf_path: Path, order_seed: int = 0) -> List[KBChunk]:
        page_texts = self._extract_pages(pdf_path)
        cleaned_pages = self._remove_repeated_lines(page_texts)
        sections = self._semantic_sections(cleaned_pages)

        chunks: List[KBChunk] = []
        source_name = pdf_path.stem.lower().replace(" ", "_")
        for i, sec in enumerate(sections):
            title = sec["title"]
            body = sanitize_text(sec["content"])
            if len(body) < 40:
                continue
            topic = normalize_topic(f"{pdf_path.stem}\n{title}\n{body}")
            concept = concept_key(title, body)
            ctype = infer_content_type(title, body)
            difficulty = infer_difficulty(body, source="pdf")
            chunk_id = self._chunk_id(str(pdf_path), title, i)
            chunks.append(
                KBChunk(
                    chunk_id=chunk_id,
                    topic=topic,
                    concept=concept,
                    source=f"pdf_{source_name}",
                    difficulty=difficulty,
                    content_type=ctype,
                    content=body,
                    source_priority=2,
                    source_ref=str(pdf_path),
                    layer="enrichment",
                    title=title,
                    order_index=order_seed + i,
                )
            )
        return chunks

    def _extract_pages(self, pdf_path: Path) -> List[str]:
        pages: List[str] = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages.append(text)
        return pages

    def _remove_repeated_lines(self, page_texts: Iterable[str]) -> List[str]:
        line_counter: Counter[str] = Counter()
        page_lines: List[List[str]] = []
        for text in page_texts:
            lines = [self._normalize_line(line) for line in text.splitlines() if line.strip()]
            page_lines.append(lines)
            for line in set(lines):
                line_counter[line] += 1

        threshold = max(2, int(len(page_lines) * 0.5))
        repeated = {
            line
            for line, count in line_counter.items()
            if count >= threshold and len(line.split()) <= 12
        }

        cleaned: List[str] = []
        for lines in page_lines:
            keep = []
            for line in lines:
                if line in repeated:
                    continue
                if re.fullmatch(r"page\s*\d+(\s*of\s*\d+)?", line.lower()):
                    continue
                if re.fullmatch(r"\d+", line.strip()):
                    continue
                keep.append(line)
            cleaned.append("\n".join(keep))
        return cleaned

    def _semantic_sections(self, page_texts: Iterable[str]) -> List[Dict[str, str]]:
        sections: List[Dict[str, str]] = []
        current_title = "Overview"
        current_parts: List[str] = []

        for page in page_texts:
            for raw_line in page.splitlines():
                line = raw_line.strip()
                if not line:
                    continue

                if self._is_heading(line):
                    if current_parts:
                        sections.append(
                            {"title": current_title, "content": "\n".join(current_parts)}
                        )
                    current_title = line
                    current_parts = []
                    continue

                current_parts.append(line)

        if current_parts:
            sections.append({"title": current_title, "content": "\n".join(current_parts)})
        return sections

    @staticmethod
    def _normalize_line(line: str) -> str:
        return re.sub(r"\s+", " ", line).strip()

    @staticmethod
    def _is_heading(line: str) -> bool:
        if len(line) > 90:
            return False
        if re.match(r"^\d+(\.\d+)*\s+[A-Za-z]", line):
            return True
        words = line.split()
        title_case_ratio = sum(1 for w in words if w[:1].isupper()) / max(len(words), 1)
        if 1 <= len(words) <= 10 and title_case_ratio >= 0.6 and not line.endswith("."):
            return True
        return False

    @staticmethod
    def _chunk_id(source_ref: str, title: str, position: int) -> str:
        raw = f"{source_ref}|{title}|{position}".encode("utf-8")
        return hashlib.sha1(raw).hexdigest()

