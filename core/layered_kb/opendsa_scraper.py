from __future__ import annotations

import hashlib
from typing import Dict, List

import requests
from bs4 import BeautifulSoup, Tag

from core.layered_kb.chunking import (
    concept_key,
    infer_content_type,
    infer_difficulty,
    normalize_topic,
    sanitize_text,
)
from core.layered_kb.schema import KBChunk


class OpenDSAScraper:
    def __init__(self, timeout_seconds: int = 15) -> None:
        self.timeout_seconds = timeout_seconds

    def scrape_urls(self, urls: List[str]) -> List[KBChunk]:
        chunks: List[KBChunk] = []
        for idx, url in enumerate(urls):
            chunks.extend(self._scrape_single(url, order_seed=idx * 1000))
        return chunks

    def _scrape_single(self, url: str, order_seed: int) -> List[KBChunk]:
        response = requests.get(url, timeout=self.timeout_seconds)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        container = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", class_="content")
            or soup.body
        )
        if container is None:
            return []

        sections = self._extract_sections(container)
        chunks: List[KBChunk] = []
        for i, section in enumerate(sections):
            title = section["title"]
            body = sanitize_text(section["content"])
            if not body:
                continue
            topic = normalize_topic(f"{title}\n{body}")
            concept = concept_key(title, body)
            ctype = infer_content_type(title, body)
            difficulty = infer_difficulty(body, source="opendsa")
            chunk_id = self._chunk_id(url, title, i)
            chunks.append(
                KBChunk(
                    chunk_id=chunk_id,
                    topic=topic,
                    concept=concept,
                    source="opendsa",
                    difficulty=difficulty,
                    content_type=ctype,
                    content=body,
                    source_priority=3,
                    source_ref=url,
                    layer="structured_backbone",
                    title=title,
                    order_index=order_seed + i,
                )
            )
        return chunks

    def _extract_sections(self, container: Tag) -> List[Dict[str, str]]:
        sections: List[Dict[str, str]] = []
        current_title = "Overview"
        current_lines: List[str] = []

        for node in container.find_all(
            ["h1", "h2", "h3", "p", "li", "pre", "code", "blockquote"], recursive=True
        ):
            text = node.get_text(" ", strip=True)
            if not text:
                continue
            if node.name in {"h1", "h2", "h3"}:
                if current_lines:
                    sections.append(
                        {"title": current_title, "content": "\n".join(current_lines)}
                    )
                current_title = text
                current_lines = []
                continue
            current_lines.append(text)

        if current_lines:
            sections.append({"title": current_title, "content": "\n".join(current_lines)})
        return sections

    @staticmethod
    def _chunk_id(source_ref: str, title: str, position: int) -> str:
        raw = f"{source_ref}|{title}|{position}".encode("utf-8")
        return hashlib.sha1(raw).hexdigest()

