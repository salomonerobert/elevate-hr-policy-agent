#!/usr/bin/env python3
"""Eval runner for the HR Policy Agent — used in Lab 2 (evals & hillclimbing).

Grading is done entirely by an LLM JUDGE: it scores each answer against the rubric
in policy_eval.json across several dimensions (0/1/2), producing a score /100 and a
run-over-run delta so you can watch the score climb. See evals/RUBRICS.md.

(The old deterministic "floor" — substring / refusal-phrase checks — has been
removed. It gave false confidence on the gotcha cases: a substring like "prohibit"
matches both "is prohibited" and "is NOT prohibited", so a trap-failing answer could
still pass. The judge grades grounding against the evidence the agent actually
retrieved, which the floor could not do.)

Usage:
    # full rubric scoring
    uv run python evals/run_eval.py --mode okf --target agent

    # quick 3-case smoke subset while iterating (fewer judge calls)
    uv run python evals/run_eval.py --mode okf --target agent --subset smoke

    # score both brains side by side
    uv run python evals/run_eval.py --target agent --compare-modes

Judge model: set EVAL_JUDGE_MODEL (default gemini-3.6-flash — deliberately a
newer/stronger model than the agent's default gemini-3.5-flash, so the grader
doesn't share the agent's blind spots).
"""
import argparse
import json
import logging
import os
import re
import statistics
import sys
import time
import warnings
from datetime import datetime, timezone

# ADK emits an [EXPERIMENTAL] UserWarning ("FeatureName.JSON_SCHEMA_FOR_FUNC_DECL
# is enabled") whenever it builds tool function-declarations. It's an internal
# library feature flag, not something our code enables — silence it so it doesn't
# clutter the per-case logs. (The old "migrate to the async method" deprecations
# are gone at the source: agent.py now drives the async ADK APIs.)
warnings.filterwarnings("ignore", message=r".*JSON_SCHEMA_FOR_FUNC_DECL.*")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if REPO not in sys.path:
    sys.path.insert(0, REPO)

DIM_ORDER = ["correctness", "grounding", "reasoning", "abstention", "citation"]
LAST_RUN = os.path.join(HERE, "last_run.json")
HISTORY = os.path.join(HERE, "history.jsonl")

# Progress logging goes to STDERR so it never corrupts the scoreboard/report,
# which is printed to STDOUT. Use --verbose/-v to bump this to DEBUG.
log = logging.getLogger("eval")
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"))
log.addHandler(_handler)
log.setLevel(logging.INFO)


# --------------------------------------------------------------------------- #
# Agent wiring (same pattern as Lab 1)
# --------------------------------------------------------------------------- #
def load_agent(target: str):
    import agent.agent as runner
    if target == "solution":
        from solution.agent import root_agent
    else:
        root_agent = runner.root_agent
        if root_agent is None:
            sys.exit("agent/agent.py root_agent is None — implement it, or use --target solution.")
    runner.root_agent = root_agent
    return runner


# --------------------------------------------------------------------------- #
# The LLM judge (rubric scoring)
# --------------------------------------------------------------------------- #
def _summarize_index_payload(tool, payload):
    """If a payload is the concept *catalog* (list_concepts), return a short
    summary instead of its full text; otherwise return None.

    list_concepts is a table of contents — an answer should never be *grounded*
    in it, and inlining all ~150 concept titles+descriptions (tens of thousands
    of chars) would crowd the actually-retrieved policy sections out of the
    judge's context window (that budget is what `limit` guards). So we collapse
    it to a one-liner and let the real read_concept/RAG evidence use the window.
    """
    if not isinstance(payload, dict):
        return None
    concepts = payload.get("concepts")
    if tool == "list_concepts" or isinstance(concepts, list):
        n = len(concepts) if isinstance(concepts, list) else "?"
        return (f"catalog index only — {n} concept titles browsed. This is a "
                f"table of contents, NOT policy text: an answer must be grounded "
                f"in read_concept / RAG content, never in this list.")
    return None


def evidence_to_str(evidence: list, limit: int = 8000) -> str:
    """Flatten the retrieved-tool payloads into text for the judge."""
    if not evidence:
        return "(the agent retrieved nothing)"
    parts = []
    for e in evidence:
        tool = e.get("tool")
        payload = e.get("payload")
        summary = _summarize_index_payload(tool, payload)
        if summary is not None:
            parts.append(f"[tool: {tool}] {summary}")
        else:
            parts.append(f"[tool: {tool}] {json.dumps(payload, default=str)[:limit]}")
    return "\n\n".join(parts)[: limit * 2]


# The judge preamble now lives in the rubric block of the eval JSON
# (rubric.judge_instructions) so the ENTIRE rubric — cross-cutting rules and
# per-dimension anchors alike — is data-driven and editable without touching code.
# This constant is only a fallback if a rubric omits the field.
_FALLBACK_JUDGE_INSTRUCTIONS = (
    "You are a STRICT evaluator. Score ONLY the listed dimensions, each an integer "
    "0/1/2, using the 0/1/2 anchors below as the definition of each score. Do not "
    "reward confident tone. Return STRICT JSON only, no markdown fences, mapping each "
    'requested dimension to {"score": 0|1|2, "why": "one short line"}.'
)


def _retrieval_summary(evidence: list) -> str:
    """A short, human-readable note of WHAT the agent retrieved for a case:
    which concepts it actually read (read_concept → title) plus a count of any
    other retrieval calls (e.g. browsing the catalog with list_concepts, or RAG
    segments). Logged per case so a low grounding/correctness score can be traced
    to 'it never read the governing concept' rather than guessed at."""
    if not evidence:
        return "nothing"
    read, other = [], {}
    for e in evidence:
        tool = e.get("tool", "?")
        payload = e.get("payload")
        if tool == "read_concept" and isinstance(payload, dict):
            label = payload.get("title") or payload.get("resource") or payload.get("id")
            if not label:  # fall back to the "# 26.3 ..." heading in the content
                m = re.match(r"\s*#+\s*(.+)", str(payload.get("content", "")))
                label = m.group(1).strip() if m else "?"
            read.append(str(label))
        elif tool == "list_concepts" and isinstance(payload, dict):
            other["list_concepts"] = other.get("list_concepts", 0) + 1
        else:
            # RAG or unknown tool: surface a source/title if present, else count it
            if isinstance(payload, dict):
                label = payload.get("title") or payload.get("source") or payload.get("resource")
                if label:
                    read.append(str(label))
                    continue
            other[tool] = other.get(tool, 0) + 1
    parts = []
    if read:
        parts.append("read [" + "; ".join(read) + "]")
    parts += [f"{t}×{n}" for t, n in other.items()]
    return " | ".join(parts) if parts else "nothing"


def _dim_block(rubric, d):
    """Render one dimension's description + its 0/1/2 anchors for the judge."""
    dd = rubric["dimensions"][d]
    lines = [f"- {d}: {dd['desc']}"]
    for s in ("2", "1", "0"):
        anchor = dd.get("anchors", {}).get(s)
        if anchor:
            lines.append(f"    {s} = {anchor}")
    return "\n".join(lines)


def build_judge_prompt(case, rubric, answer, evidence_str):
    dims = case["dimensions"]
    dim_lines = "\n".join(_dim_block(rubric, d) for d in dims)
    gt = case.get("ground_truth_notes") or "(none)"
    gotcha = case.get("gotcha")
    gotcha_line = f"\nGOTCHA TO CATCH: {gotcha}" if gotcha else ""
    srcs = case.get("expected_sources") or []
    src_line = (
        f"\n=== ACCEPTABLE SOURCES (for the citation dimension) ===\n"
        f"A correct answer should cite the handbook section it used. Any of these "
        f"handbook sections is an acceptable citation: {srcs}. The handbook repeats "
        f"some topics across sections, so ANY section that genuinely supports the "
        f"answer counts; a missing, wrong, or fabricated citation does not.\n"
        if srcs else ""
    )
    instructions = rubric.get("judge_instructions") or _FALLBACK_JUDGE_INSTRUCTIONS
    return f"""{instructions}

=== QUESTION ===
{case['query']}

=== GROUND-TRUTH NOTES (what a correct answer must reflect) ==={gotcha_line}
{gt}
{src_line}
=== RETRIEVED EVIDENCE (what the agent actually retrieved) ===
{evidence_str}

=== AGENT ANSWER (verbatim) ===
{answer}

=== DIMENSIONS TO SCORE ===
{dim_lines}

Return JSON with exactly these keys: {dims}
"""


def _parse_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def _coerce_score(entry):
    """Normalize one dimension's judge output into (int_score, why).

    The judge is asked for {"score": 0|1|2, "why": "..."} per dimension, but it
    sometimes returns a bare number (or a numeric string) for a dimension instead.
    Accept every shape, clamp to 0..2, and never raise — a malformed dimension
    scores 0 rather than crashing the whole case.
    """
    why = ""
    val = entry
    if isinstance(entry, dict):
        why = str(entry.get("why", ""))
        val = entry.get("score", 0)
    try:
        score = int(val)
    except (TypeError, ValueError):
        score = 0
    return max(0, min(2, score)), why


# Substrings that mark a *transient* judge failure worth retrying. A permanent
# error (bad request, auth, model-not-found) is NOT here, so it re-raises fast and
# the case is scored 0 via the ⚠ ERRORED path rather than being retried pointlessly.
_TRANSIENT_JUDGE_ERRORS = (
    "429", "resource_exhausted", "rate limit", "quota",
    "503", "unavailable", "500", "internal", "deadline", "timeout",
)


def _judge_generate(client, model, prompt, attempts=4, base_delay=2.0):
    """Call the judge model once, retrying transient errors with exponential
    backoff. Without this, a single Vertex 429/503 on one case permanently
    dropped it to 0 — noise that a run-over-run comparison should not carry."""
    from google.genai import types

    config = types.GenerateContentConfig(temperature=0, response_mime_type="application/json")
    delay = base_delay
    for attempt in range(1, attempts + 1):
        try:
            return client.models.generate_content(model=model, contents=prompt, config=config)
        except Exception as e:  # noqa: BLE001
            msg = str(e).lower()
            transient = any(t in msg for t in _TRANSIENT_JUDGE_ERRORS)
            if not transient or attempt == attempts:
                raise
            log.warning("judge call transient error (attempt %d/%d): %s — retrying in %.0fs",
                        attempt, attempts, e, delay)
            time.sleep(delay)
            delay *= 2


def judge_case(case, rubric, answer, evidence_str, model, n=1):
    """Call the LLM judge n times; return {dim: median_score} + justifications."""
    from google import genai

    client = genai.Client()
    prompt = build_judge_prompt(case, rubric, answer, evidence_str)
    runs = []
    justifications = {}
    for _ in range(n):
        resp = _judge_generate(client, model, prompt)
        parsed = _parse_json(resp.text)
        scores = {}
        for d in case["dimensions"]:
            score, why = _coerce_score(parsed.get(d, {}))
            scores[d] = score
            justifications[d] = why
        runs.append(scores)
    # median_low keeps the result an actual observed integer score (0/1/2): with an
    # even n, plain statistics.median averages the two middle values (e.g. 1 and 2 ->
    # 1.5) and int() would truncate that to 1, biasing every split decision downward.
    # median_low is deterministic and breaks ties down, matching the harsh grader.
    median = {d: statistics.median_low([r[d] for r in runs]) for d in case["dimensions"]}
    return median, justifications


def score_case(case, rubric, dim_scores):
    """Weighted per-case percentage over the applicable dimensions, with the
    grounding gate (a fabricated answer can't score 'mostly right')."""
    num = den = 0
    for d in case["dimensions"]:
        w = rubric["dimensions"][d]["weight"]
        num += w * dim_scores[d]
        den += w * 2
    pct = num / den if den else 0.0
    if dim_scores.get("grounding") == 0:
        pct = min(pct, rubric.get("gates", {}).get("grounding_zero_caps_case_at", 0.40))
    return pct


# --------------------------------------------------------------------------- #
# Run one suite
# --------------------------------------------------------------------------- #
def run_suite(cases, rubric, runner, judge_model, n):
    results = []
    total = len(cases)
    for i, c in enumerate(cases, 1):
        log.info("[%d/%d] running case %s", i, total, c["id"])
        log.debug("query: %s", c["query"])
        try:
            # Each case gets its OWN session (session_id = case id) so cases are
            # isolated: without this every case shares one session and the agent
            # sees prior cases' Q&A in context — it can answer from memory instead
            # of retrieving (grounding then reads as 0 items), and results become
            # order-dependent. Per-case sessions make each run reproducible.
            answer, evidence = runner.run_query_traced(c["query"], session_id=c["id"])
        except Exception as e:  # noqa: BLE001
            log.error("case %s failed in agent: %s", c["id"], e)
            results.append({"id": c["id"], "error": str(e)})
            continue
        log.info("case %s retrieved %d item(s): %s",
                 c["id"], len(evidence or []), _retrieval_summary(evidence))
        log.debug("answer preview: %s", (answer or "")[:200])
        row = {"id": c["id"]}
        try:
            log.info("judging case %s with %s", c["id"], judge_model)
            dim_scores, why = judge_case(c, rubric, answer, evidence_to_str(evidence), judge_model, n)
            row["dims"] = dim_scores
            row["why"] = why
            row["pct"] = score_case(c, rubric, dim_scores)
            log.info("case %s scores %s -> %.0f%%", c["id"], dim_scores, row["pct"] * 100)
            for d, j in why.items():
                log.debug("case %s judge[%s]: %s", c["id"], d, j)
        except Exception as e:  # noqa: BLE001
            log.warning("case %s failed in judge: %s", c["id"], e)
            row["error"] = f"Judge error ({e})"
        results.append(row)
    return results


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def print_report(results, mode, target, rubric):
    # columns derived from the rubric (so an added dimension actually shows up)
    dim_order = list(rubric.get("dimensions", {}).keys()) or DIM_ORDER
    hdr = "case".ljust(30) + "".join(d[:4].rjust(6) for d in dim_order) + "   case%"
    print("\n" + hdr)
    print("-" * len(hdr))
    for r in results:
        if "error" in r:
            print(f"{r['id'][:29].ljust(30)}  ERROR: {r['error']}")
            continue
        cells = "".join((str(r["dims"][d]) if d in r.get("dims", {}) else "-").rjust(6) for d in dim_order)
        pct_str = f"{r['pct']*100:5.0f}" if "pct" in r else "  N/A"
        print(f"{r['id'][:29].ljust(30)}{cells}   {pct_str}")
    scored = [r for r in results if "pct" in r]
    errored = [r["id"] for r in results if "error" in r]
    # Errored cases (agent crash or judge failure) count as 0 — a failure, not an
    # omission. Dropping them would shrink the denominator and inflate the score,
    # hiding the very cases that need investigating.
    n = len(results)
    by_id = {r["id"]: r.get("pct", 0.0) for r in results}
    total = 100 * sum(by_id.values()) / n if n else 0.0
    print("-" * len(hdr))
    print(f"{'TOTAL'.ljust(30)}{''.join(' ' * 6 for _ in dim_order)}   {total:5.1f} / 100")
    if errored:
        print(f"⚠  ERRORED (scored 0 in TOTAL — investigate: agent crash or judge failure): {errored}")

    # anti-gaming alarm: a high case score built on ungrounded/hardcoded facts
    s2 = [r["id"] for r in scored if r["dims"].get("grounding") == 0]
    if s2:
        print(f"⚠  SUSPECT (GROUNDING=0 — likely hardcoded/ungrounded): {s2}")

    # badge (gates) — a missing/errored hard case counts as 0 (never a free pass)
    gates = rubric.get("gates", {})
    hard = gates.get("hard_cases", [])
    thr = gates.get("badge_min_on_hard_cases", 0.8)
    if hard:
        got = {h: by_id.get(h, 0.0) for h in hard}
        ok = all(v >= thr for v in got.values())
        fails = [h for h, v in got.items() if v < thr]
        print(f"BADGE (>= {int(thr*100)}% on hard cases {hard}): "
              f"{'✅ PASS' if ok else '❌ not yet'}"
              + (f" — below bar: {fails}" if fails else ""))
    return {"total": total, "per_case": by_id}


def show_delta_and_save(summary, mode, target):
    key = f"{mode}:{target}"
    prev = {}
    if os.path.exists(LAST_RUN):
        try:
            prev = json.load(open(LAST_RUN)).get(key, {})
        except Exception:  # noqa: BLE001
            prev = {}
    if prev:
        d = summary["total"] - prev.get("total", 0)
        arrow = "↑" if d > 0 else ("↓" if d < 0 else "=")
        print(f"\nDELTA vs last {key} run: {prev.get('total', 0):.1f} -> {summary['total']:.1f}  ({d:+.1f}) {arrow}")
        regressions = [
            cid for cid, p in summary["per_case"].items()
            if cid in prev.get("per_case", {}) and p < prev["per_case"][cid] - 1e-9
        ]
        if regressions:
            print(f"⚠  regressions: {regressions}")
    else:
        print(f"\n(baseline saved for {key} — re-run after a change to see the delta)")

    all_runs = {}
    if os.path.exists(LAST_RUN):
        try:
            all_runs = json.load(open(LAST_RUN))
        except Exception:  # noqa: BLE001
            all_runs = {}
    stamped = {**summary, "timestamp": datetime.now(timezone.utc).isoformat()}
    all_runs[key] = stamped
    json.dump(all_runs, open(LAST_RUN, "w"), indent=2)
    with open(HISTORY, "a") as fh:
        fh.write(json.dumps({"key": key, **stamped}) + "\n")
    log.info("saved baseline/delta for %s to %s (also appended to %s)", key, LAST_RUN, HISTORY)


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="HR Policy Agent eval runner")
    ap.add_argument("--mode", choices=["okf", "rag", "hybrid"], help="override RETRIEVAL_MODE")
    ap.add_argument("--target", choices=["solution", "agent"], default="agent")
    ap.add_argument("--eval-file", default=os.path.join(HERE, "policy_eval.json"))
    ap.add_argument("--subset", choices=["smoke", "full"], default="full")
    ap.add_argument("--judge-model", default=os.getenv("EVAL_JUDGE_MODEL", "gemini-3.6-flash"),
                    help="grader model; default is stronger than the agent so it doesn't share its blind spots")
    ap.add_argument("--self-consistency", type=int, default=1, help="judge N times, take median")
    ap.add_argument("--compare-modes", action="store_true", help="run okf and rag side by side")
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="verbose progress logging to stderr (DEBUG level)")
    args = ap.parse_args()

    if args.verbose:
        log.setLevel(logging.DEBUG)

    data = json.load(open(args.eval_file))
    rubric = data.get("rubric", {})
    if not rubric.get("judge_instructions"):
        log.warning("rubric has no 'judge_instructions' — using the thin built-in "
                    "fallback; add it to %s for full judge guidance", args.eval_file)
    cases = data["cases"]
    if args.subset == "smoke":
        cases = [c for c in cases if c.get("smoke")] or cases

    modes = ["okf", "rag"] if args.compare_modes else [args.mode or os.getenv("RETRIEVAL_MODE", "okf")]
    log.info("eval file=%s | cases=%d | subset=%s | target=%s | judge=%s | modes=%s",
             args.eval_file, len(cases), args.subset, args.target, args.judge_model, modes)
    summaries = {}
    for mode in modes:
        log.info("starting retrieval mode=%s", mode)
        os.environ["RETRIEVAL_MODE"] = mode
        # reload config + agent so the mode change takes effect
        for m in ("agent.config", "agent.agent"):
            sys.modules.pop(m, None)
        log.info("reloading agent/config for mode=%s (target=%s)", mode, args.target)
        runner = load_agent(args.target)
        print(f"\n===== mode={mode} | target={args.target} | judge={args.judge_model} | subset={args.subset} =====")
        results = run_suite(cases, rubric, runner, args.judge_model, args.self_consistency)
        summary = print_report(results, mode, args.target, rubric)
        if summary:
            summaries[mode] = summary
            log.info("mode=%s TOTAL %.1f / 100", mode, summary["total"])

    if not args.compare_modes and summaries:
        show_delta_and_save(summaries[modes[0]], modes[0], args.target)
    if args.compare_modes and len(summaries) == 2:
        print("\n===== okf vs rag =====")
        for cid in summaries["okf"]["per_case"]:
            o = summaries["okf"]["per_case"].get(cid, 0) * 100
            r = summaries["rag"]["per_case"].get(cid, 0) * 100
            print(f"{cid[:32].ljust(33)} okf {o:5.0f}   rag {r:5.0f}   Δ {o-r:+.0f}")
        print(f"{'TOTAL'.ljust(33)} okf {summaries['okf']['total']:5.1f}   rag {summaries['rag']['total']:5.1f}")


if __name__ == "__main__":
    main()
