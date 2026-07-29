# Understanding `run_eval.py` — the LLM-as-Judge harness (a first-timer's walkthrough)

New to this lab? Read this once before you run anything. It explains **what the eval
script actually does**, so the scoreboard in `LAB_EVALS.md` reads as signal, not noise.
(For the *scoring rules* themselves, see `RUBRICS.md`. This doc is the *mechanics*.)

---

## 1. Why an eval at all?

You built an HR Policy Agent in Lab 1. "It seems to work" is not a number, and you
can't improve what you can't measure. This script turns *"is my agent good?"* into a
**score out of 100** you can watch move as you change things.

The naive way to grade is substring matching — "does the answer contain `14`?" That's
a trap: `prohibit` matches both *"is prohibited"* and *"is **not** prohibited"*, so a
wrong answer can pass. That old "floor" check was deliberately removed. Instead,
grading is done by **another LLM acting as a judge** that reads the question, the
known-correct notes, what the agent retrieved, and the answer, then scores against a
rubric.

The whole lab is one loop, and this script is the "measure" step:

```
measure  →  diagnose  →  improve  →  measure again ...
(run_eval)  (read the    (change ONE   (did the
             low dim)     lever)         number climb?)
```

---

## 2. Anatomy of one eval case

Cases live in `policy_eval.json` under `"cases"`. A "gotcha" trap case has:

- **`id`** — unique name; also used as the **session id** when run, and the
  scoreboard's left-column label.
- **`smoke`** — `true` ⇒ included in the quick 3-case `--subset smoke` loop.
- **`query`** — the question sent to your agent, verbatim.
- **`ground_truth_notes`** — the correct answer in prose. **Not** shown to the agent —
  it's given to the *judge*.
- **`expected_sources`** — handbook sections a good answer could cite; used only for
  the `citation` dimension (any genuinely-supporting section counts).
- **`gotcha`** — the trap to catch, fed to the judge (omitted on plain
  lookups/refusals).
- **`dimensions`** — which rubric dimensions apply to *this* case. A refusal case lists
  only `["abstention","grounding"]`; unlisted dimensions aren't scored or counted.

---

## 3. End-to-end: what one run does

**A. Load** the JSON → splits into `rubric` (dimensions + anchors + weights, gates,
`judge_instructions`) and `cases`. `--subset smoke` filters to smoke cases; it picks
retrieval mode(s) and loads your agent (`--target agent`) or the reference
(`--target solution`).

**B. Run each case in its OWN session:**

```python
answer, evidence = runner.run_query_traced(c["query"], session_id=c["id"])
```

`evidence` is the list of `{"tool", "payload"}` from each retrieval call — *exactly
what the agent read*. **Isolation matters:** if all cases shared one session, the agent
would see earlier cases in context and answer from memory instead of retrieving
(grounding → 0, results order-dependent). Per-case sessions make runs reproducible. A
crash on one case is caught and recorded, not fatal, and a one-line `read [...]`
summary logs *what* it retrieved.

**C. The judge scores each dimension 0/1/2** in one call. The prompt is assembled
entirely from the JSON: the `judge_instructions` preamble + query + ground-truth notes
+ gotcha + acceptable sources + retrieved evidence + verbatim answer + each dimension's
description and its **0/1/2 anchors**. The judge returns `{"score", "why"}` per
dimension. It's a **stronger, different model** (`gemini-3.6-flash` vs the agent's
`gemini-3.5-flash`) at `temperature=0`; malformed output scores 0 rather than crashing
(clamped 0–2). `--self-consistency N` takes the median of N judge calls
(`median_low` breaks ties down).

**D. Roll up to a case %:**

```
case % = Σ(weight × score) / Σ(weight × 2)   over applicable dimensions only
```

Weights: correctness 3, grounding 3, reasoning 3, abstention 2, citation 1. The
denominator sums only the case's dimensions, so weights renormalize per case.
**Grounding gate:** if `grounding == 0`, the case is capped at **40%** — a confident
fabrication is never "mostly right."

**E. The report:**

- **`TOTAL / 100`** — mean of all case %s; **every** case counts (errored ones
  included).
- **`⚠ ERRORED`** — agent/judge failures, scored **0** (not dropped — dropping would
  inflate the score).
- **`⚠ SUSPECT (GROUNDING=0)`** — anti-gaming alarm: the score rests on ungrounded
  facts (the fingerprint of hardcoding).
- **`BADGE`** — pass = **≥80% on the hard cases** (gotchas + refusals, listed in
  `rubric.gates.hard_cases`); a missing/errored hard case counts 0.
- **`DELTA vs last run`** — compares to `last_run.json` for the same `mode:target`,
  flags regressions.

```
case                            corr  grou  reas  abst  cita   case%
room_salon_gotcha                  1     2     0     -     1      45
--------------------------------------------------------------
TOTAL                                                    72.3 / 100
BADGE (>= 80% on hard cases [...]): ❌ below bar: ['room_salon_gotcha']
DELTA vs last okf:agent run: 68.0 -> 72.3  (+4.3) ↑
```

(A `-` = dimension not applicable here, **not** a zero.)

---

## 4. Reading a row → what to fix

The **low dimension names the kind of fix**:

| Low dimension | Meaning | Lever |
|---|---|---|
| **reasoning** (gotcha) | found the limit, missed the prohibition | prompt/retrieval — check prohibitions before limits |
| **grounding** | inventing facts not retrieved | prompt — "answer only from retrieved text" |
| **correctness** | missed a sub-question/number | prompt — answer every part + show calc |
| **abstention** | answered what it should refuse | prompt — strengthen refusal rule |
| **citation** | missing/wrong source | prompt/tool — fix citation, ensure source in tool output |

---

## 5. Commands you'll actually run

```bash
uv run python evals/run_eval.py --mode okf --target agent            # baseline
uv run python evals/run_eval.py --mode okf --target agent --subset smoke   # fast loop
uv run python evals/run_eval.py --target agent --compare-modes       # okf vs rag
uv run python evals/run_eval.py --mode okf --target agent --self-consistency 3
uv run python evals/run_eval.py --mode okf --target agent --verbose  # judge "why" + retrieval detail
uv run python evals/run_eval.py --mode okf --target agent \
  --eval-file evals/policy_eval_heldout.json                         # the reveal (run once)
```

Logs go to **stderr**, the scoreboard to **stdout**, so you can redirect the report
cleanly.

---

## 6. Gotchas that trip up first-timers

- **The judge needs its own credentials** — a `404`/auth "from the judge" is a
  creds/`--judge-model` issue, not your agent.
- **Errored cases count as 0**, not skipped — dropping them would inflate the score.
- **Scores wobble run-to-run** — the agent is nondeterministic; trust full runs, use
  `--self-consistency`, don't over-read a ±1–2 wiggle.
- **Grounding is graded against what was retrieved, not against truth** — a
  true-but-unretrieved claim still scores grounding 0 ("plausible" ≠ "supported").
- **`⚠ SUSPECT (GROUNDING=0)` is a warning, not a win** — it's the fingerprint of
  teaching-to-the-test.
- **A `-` is "not applicable," not zero.**
- **The rubric is data, not code** — anchors/weights/gates/judge-instructions all live
  in `policy_eval.json`; retune the grader without touching Python.

---

*Next: `RUBRICS.md` for the scoring dimensions, then `LAB_EVALS.md` for the
hillclimbing exercises.*
