# Cognitive Adaptive AI Tutor - Complete Implementation Context

## Executive Summary

This is a production-ready AI-driven adaptive learning system for Python programming education. The system uses a sophisticated multi-agent architecture orchestrated by LangGraph, with RAG-enhanced content generation, hierarchical decision-making, and persistent student modeling. It adapts teaching strategies in real-time based on student performance, engagement, and learning trends.

---

## System Architecture

### Core Technology Stack
- **LangGraph**: Graph-based workflow orchestration with conditional routing
- **CrewAI**: Multi-agent coordination framework
- **ChromaDB**: Vector database for semantic search
- **Google Gemini 2.0 Flash Lite**: Primary LLM for content generation
- **Groq**: Secondary LLM for fast quiz generation
- **sentence-transformers**: Local embeddings (all-MiniLM-L6-v2)
- **pypdf**: PDF text extraction for curriculum ingestion

### High-Level Architecture Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    LANGGRAPH ORCHESTRATION                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  File Manager → Macro Decision → Micro Decision            │
│                        ↓                                    │
│                  Education Crew                             │
│                  (3 agents)                                 │
│           