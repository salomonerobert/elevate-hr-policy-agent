# Evaluation

`policy_eval.json` holds golden cases (reused from `elevate-hr-agent`'s
`rag_eval_golden` set, plus gotchas and refusals) **and** the grading rubric.
`run_eval.py` runs them through the agent and grades with an **LLM judge**: each
answer is scored against the rubric across 5 dimensions → a score **/100**, a
scoreboard, and a run-over-run delta.

> The old deterministic "floor" (substring / refusal-phrase checks) has been
> removed. It gave false confidence on the gotcha cases — a substring like
> `prohibit` matches both "is prohibited" and "is **not** prohibited", so a
> trap-failing answer could still pass. The judge grades *grounding* against the
> evidence the agent actually retrieved, which the floor could not do.

See **`RUBRICS.md`** for the scorecard, and **`../LAB_EVALS.md`** (Lab 2) for the
full measure → diagnose → improve workflow.

## Quick start

```bash
# full rubric scoring — grades YOUR implementation in agent/
uv run python evals/run_eval.py --mode okf --target agent

# fast 3-case smoke subset while iterating (fewer judge calls)
uv run python evals/run_eval.py --mode okf --target agent --subset smoke

# both brains side by side
uv run python evals/run_eval.py --target agent --compare-modes
```

Both answer generation and grading need model credentials (`GEMINI_API_KEY` or
Vertex AI configured in `.env`). The judge defaults to `gemini-3.6-flash` — a
stronger model than the agent (`gemini-3.5-flash`) so it doesn't share the agent's
blind spots; override with `EVAL_JUDGE_MODEL`. RAG mode additionally needs a
provisioned Vertex data store (see `rag/README.md`).

`--target solution` grades the reference agent (available to instructors on the
`instructor` branch). Per-run state (`last_run.json`, `history.jsonl`) is git-ignored.

## The interesting cases

- `host_gift_card_gotcha` and `room_salon_gotcha` are **gotchas**: a value under a
  spending limit does not make a *prohibited category* (gift cards, adult
  entertainment) allowed. Note whether each brain gets these right — deliberate OKF
  navigation often beats semantic RAG chunks here.
- `out_of_domain` (write code) and `ungrounded_policy` (pet adoption) must be
  **refused**, not fabricated.
