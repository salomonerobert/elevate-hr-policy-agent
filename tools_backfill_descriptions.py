#!/usr/bin/env python3
"""Backfill a `description:` frontmatter field into existing OKF concept files.

Adds one line per concept file, computed by tools_build_okf.make_description from
the file's OWN body — it does NOT regenerate bodies from the PDF, so the verbatim
handbook text is untouched and the diff is exactly one line per file. Idempotent:
files that already carry a description are skipped, so it is safe to re-run.

Usage:
    python tools_backfill_descriptions.py            # dry run (report only)
    python tools_backfill_descriptions.py --write
"""
import argparse
import json
import os

from tools_build_okf import make_description  # import is side-effect-free (main is guarded)

REPO = os.path.dirname(os.path.abspath(__file__))
KN = os.path.join(REPO, "knowledge")
RESERVED = {"index.md", "log.md"}


def split_frontmatter(text):
    """Return (fm_lines, body) for a `---\\n...\\n---\\n` block, else (None, None)."""
    if not text.startswith("---\n"):
        return None, None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, None
    return text[4:end].splitlines(), text[end + 5:]


def process(path, write):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    fm, body = split_frontmatter(text)
    if fm is None:
        return "no-frontmatter"
    if any(line.startswith("description:") for line in fm):
        return "already"
    desc = make_description(body)
    if not desc:
        return "empty"
    # insert after `title:` if present, else after `type:`, matching build order
    idx = next((i for i, line in enumerate(fm) if line.startswith("title:")), None)
    if idx is None:
        idx = next((i for i, line in enumerate(fm) if line.startswith("type:")), -1)
    fm.insert(idx + 1, f"description: {json.dumps(desc)}")
    if write:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("---\n" + "\n".join(fm) + "\n---\n" + body)
    return "updated"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write files (default: dry run)")
    args = ap.parse_args()
    counts = {}
    for dirpath, _dirs, files in os.walk(KN):
        for name in sorted(files):
            if not name.endswith(".md") or name in RESERVED:
                continue
            r = process(os.path.join(dirpath, name), args.write)
            counts[r] = counts.get(r, 0) + 1
    print(("WROTE" if args.write else "DRY-RUN"), counts)


if __name__ == "__main__":
    main()
