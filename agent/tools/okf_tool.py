"""Track B — OKF retrieval tools.

The agent uses these to *navigate* the Open Knowledge Format bundle in knowledge/:
first list what concepts exist, then read the most relevant one. No vector DB.
"""
import os
import re
import yaml

from .. import config

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
RESERVED = {"index.md", "log.md"}


def _parse_frontmatter(text: str):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except Exception:
        data = {}
    body = text[m.end():]
    return data, body


def list_concepts() -> dict:
    """List the policy concepts available in the OKF bundle.

    Returns:
        {"concepts": [{"id": str, "title": str, "description": str}, ...]}
        where `id` is the concept path without the .md suffix,
        e.g. "leave/bereavement-leave".
    """
    concepts = []
    knowledge_dir = os.path.abspath(config.KNOWLEDGE_DIR)
    for dirpath, _dirs, files in os.walk(knowledge_dir):
        for name in sorted(files):
            if not name.endswith(".md") or name in RESERVED:
                continue
            full_path = os.path.join(dirpath, name)
            rel_path = os.path.relpath(full_path, knowledge_dir)
            concept_id = os.path.splitext(rel_path)[0].replace("\\", "/")
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    text = f.read()
                frontmatter, _ = _parse_frontmatter(text)
                title = frontmatter.get("title") or concept_id
                description = frontmatter.get("description") or ""
                concepts.append({
                    "id": concept_id,
                    "title": title,
                    "description": description,
                })
            except Exception:
                continue
    concepts.sort(key=lambda x: x["id"])
    return {"concepts": concepts}


def read_concept(concept_id: str) -> dict:
    """Read one OKF concept's content and citation.

    Args:
        concept_id: e.g. "03-other-compassionate-unpaid-leaves/3.1-bereavement-leave-global" (no .md).

    Returns:
        {"content": str, "title": str, "resource": str | None}
        where `content` is the markdown body (after the frontmatter) and
        `resource` is the frontmatter `source` (or `resource`) reference if present.
    """
    knowledge_dir = os.path.abspath(config.KNOWLEDGE_DIR)
    clean_id = concept_id.strip().removesuffix(".md").lstrip("/")
    target_path = os.path.normpath(os.path.join(knowledge_dir, f"{clean_id}.md"))

    # Path traversal guard
    if not (target_path == knowledge_dir or target_path.startswith(knowledge_dir + os.sep)):
        return {
            "content": f"Access denied: path '{concept_id}' attempts to escape knowledge directory.",
            "title": "",
            "resource": None,
        }

    if not os.path.isfile(target_path):
        return {
            "content": f"Concept '{concept_id}' not found. Call list_concepts to see valid concept ids.",
            "title": "",
            "resource": None,
        }

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            text = f.read()
        frontmatter, body = _parse_frontmatter(text)
        title = frontmatter.get("title") or clean_id
        resource = frontmatter.get("source") or frontmatter.get("resource")
        return {
            "content": body.strip(),
            "title": title,
            "resource": resource,
        }
    except Exception as e:
        return {
            "content": f"Error reading concept '{concept_id}': {e}",
            "title": "",
            "resource": None,
        }
