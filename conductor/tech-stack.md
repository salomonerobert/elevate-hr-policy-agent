# Technology Stack: Elevate HR Policy Agent

## Core Architecture
- **Language**: Python 3.11+
- **Dependency Management**: `uv`
- **Agent Framework**: Google Agent Development Kit (`google-adk`) powered by Gemini LLM

## Retrieval Systems
- **Track A (RAG)**: Google Vertex AI Search (`google-cloud-discoveryengine`), Google Cloud Storage, Terraform (>= 1.5)
- **Track B (OKF)**: Direct concept traversal using Open Knowledge Format markdown bundles (`knowledge/`)

## Utilities & Tooling
- **Parsing**: `pypdf`, `pyyaml`, `python-dotenv`
- **Quality & Linting**: `ruff`, `mypy`, `codespell`
- **CLI & Evaluation**: `google-agents-cli`, `evals/` test runner
