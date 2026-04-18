from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from core.layered_kb.dependency_graph import build_topic_dependency_graph
from core.layered_kb.embeddings import EmbeddingProvider, build_embedder
from core.layered_kb.metadata import MetadataIntelligence
from core.layered_kb.opendsa_scraper import OpenDSAScraper
from core.layered_kb.pdf_ingestion import PDFIngestionPipeline
from core.layered_kb.schema import KBChunk
from core.layered_kb.vector_store import LayeredVectorStore


class LayeredKnowledgeBuilder:
    def __init__(
        self,
        vector_store: LayeredVectorStore | None = None,
        embedder: EmbeddingProvider | None = None,
    ) -> None:
        self.scraper = OpenDSAScraper()
        self.pdf_pipeline = PDFIngestionPipeline()
        self.metadata_intelligence = MetadataIntelligence()
        self.vector_store = vector_store or LayeredVectorStore()
        self.embedder = embedder or build_embedder("sentence-transformers")

    def build_from_sources(
        self,
        opendsa_urls: List[str],
        pdf_raw_dir: str = "data/raw",
        output_chunks_path: str = "data/processed/layered_chunks.json",
        output_graph_path: str = "data/processed/topic_dependency_graph.json",
    ) -> Dict[str, int]:
        structured_chunks = self.scraper.scrape_urls(opendsa_urls)
        enriched_chunks = self.pdf_pipeline.ingest_dir(pdf_raw_dir)

        all_chunks = self.metadata_intelligence.enrich(structured_chunks + enriched_chunks)
        self._persist_chunks_json(all_chunks, output_chunks_path)

        graph = build_topic_dependency_graph(all_chunks)
        self._persist_graph_json(graph, output_graph_path)

        embeddings = [self.embedder.embed(c.content) for c in all_chunks]
        self.vector_store.upsert_chunks(all_chunks, embeddings)

        return {
            "structured_backbone_chunks": len(structured_chunks),
            "enrichment_chunks": len(enriched_chunks),
            "total_chunks": len(all_chunks),
            "topics_in_graph": len(graph),
        }

    @staticmethod
    def _persist_chunks_json(chunks: List[KBChunk], output_path: str) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [c.to_payload() for c in chunks]
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def _persist_graph_json(graph: Dict[str, Dict[str, List[str]]], output_path: str) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(graph, indent=2), encoding="utf-8")

