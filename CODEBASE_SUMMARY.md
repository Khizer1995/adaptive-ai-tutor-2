# 🧠 Cognitive Adaptive AI Tutor - Complete Codebase Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [RAG Pipeline](#rag-pipeline)
5. [Data Models](#data-models)
6. [Scripts & Utilities](#scripts--utilities)
7. [Output Examples](#output-examples)
8. [Team Responsibilities](#team-responsibilities)

---

## System Overview

**Project Type**: AI-Driven Adaptive Learning System for Python Programming

**Tech Stack**:
- **LangGraph**: Graph-based workflow orchestration
- **CrewAI**: Multi-agent coordination
- **ChromaDB**: Vector database for RAG
- **Google Gemini 2.0 Flash Lite**: LLM for content generation
- **sentence-transformers**: Local embeddings (all-MiniLM-L6-v2)
- **pypdf**: PDF text extraction

**Purpose**: Create a personalized, adaptive tutoring system that:
- Analyzes student performance in real-time
- Adjusts teaching style, difficulty, and content dynamically
- Tracks progress across 9 Python programming topics
- Uses RAG to ground responses in curriculum content
- Maintains persistent student profiles

---

## Architecture

### High-Level Flow
```
┌─────────────────┐
│ Student Profile │
│  (JSON File)    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│              LANGGRAPH ADAPTIVE FLOW                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐                                      │
│  │   Decision   │──────┐                               │
│  │    Engine    │      │                               │
│  └──────────────┘      │                               │
│         │              │                               │
│         ▼              ▼                               │
│  ┌──────────────┐  ┌──────────────┐                   │
│  │  Education   │  │   Monitor    │                   │
│  │    Crew      │  │    Agent     │                   │
│  └──────┬───────┘  └──────┬───────┘                   │
│         │                 │                            │
│         ▼                 │                            │
│  ┌──────────────┐         │                            │
│  │  Validation  │         │                            │
│  │    Agent     │         │                            │
│  └──────┬───────┘         │                            │
│         │                 │                            │
│         └────────┬────────┘                            │
│                  │                                     │
│                  ▼                                     │
│         ┌────────────────┐                             │
│         │ Continue Loop? │                             │
│         │ (score < 0.85) │                             │
│         └────────────────┘                             │
│                                                         │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│ Updated Profile │
│  (Persisted)    │
└─────────────────┘
```

### Education Crew Internal Structure
```
┌──────────────────────────────────────┐
│        EDUCATION CREW                │
├──────────────────────────────────────┤
│                                      │
│  ┌────────────────────────────────┐ │
│  │      TutorAgent                │ │
│  │  - RAG Retrieval (ChromaDB)    │ │
│  │  - Query Engineering           │ │
│  │  - Gemini LLM Synthesis        │ │
│  │  - Curriculum Management       │ │
│  └────────────────────────────────┘ │
│                                      │
│  ┌────────────────────────────────┐ │
│  │    PracticalAgent              │ │
│  │  - Adaptive Quiz Generation    │ │
│  │  - Difficulty Scaling          │ │
│  │  - Style-Based Questions       │ │
│  └────────────────────────────────┘ │
│                                      │
│  ┌────────────────────────────────┐ │
│  │  TeacherPersonaAgent           │ │
│  │  - Teaching Style Selection    │ │
│  │  - Persona Adaptation          │ │
│  └────────────────────────────────┘ │
│                                      │
└──────────────────────────────────────┘
```

---

## Core Components

### 1. `core/langgraph_flow.py` - Workflow Orchestrator

**Purpose**: Defines the state graph that orchestrates the entire adaptive learning workflow.

**Key Components**:
