# Product Definition: Elevate HR Policy Agent

## Overview
Project Elevate is a conversational HR Policy Assistant designed for Altostrat Singapore. It answers employee policy questions accurately, grounded strictly in the *Altostrat Singapore Employee Policy Handbook & Conduct Guidelines* (a 52-page handbook), with explicit citations. The agent is built to eliminate HR support bottlenecks while mitigating compliance risks by refusing out-of-domain or ungrounded questions.

## Core Features & Goals
- **Grounded Q&A**: Answers employee questions regarding leave, expenses, business courtesies, conduct, and privacy using strictly handbook facts.
- **Dual Retrieval Architectures**:
  - **Track A (RAG)**: Integrates Google Vertex AI Search over the handbook PDF for semantic retrieval.
  - **Track B (OKF)**: Direct agent navigation through Google's Open Knowledge Format cross-linked markdown bundle.
- **Strict Citation & Refusal**: Provides explicit policy citations and politely declines to answer non-handbook or unanswerable questions instead of guessing.
- **ADK Architecture**: Implemented as a single Google ADK `LlmAgent` using Gemini with tool calling capabilities (`okf_tool.py` and `rag_tool.py`).

## Target Audience
- Altostrat Singapore employees (full-time staff, interns, and extended workforce).
- HR Administrators and Developers evaluating RAG vs. OKF retrieval patterns.
