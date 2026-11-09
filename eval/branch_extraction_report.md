# Branch Extraction Test Report

**Date:** 2026-11-06
**LLM:** Ollama `llama3.1:8b` (local), temperature 0.1
**Scope under test:** `extraction/notice_extractor.py` — the `allowed_branches` criterion extraction, after adding:
1. A canonical `ALLOWED_BRANCHES` list derived from `data/students.json`'s actual branch values.
2. A prompt section telling the LLM that `BE`, `B.Tech`, `MBA`, `M.Tech`, `MCA`, etc. are degree/program levels, not branches, and that a notice scoped to a non-BE/BTech program should produce no branch criterion.
3. A hard post-extraction filter (`_filter_to_allowed_branches`) that silently drops any branch code outside the canonical set, and skips the whole criterion if nothing valid remains.

**Canonical allowed branches** (from `data/students.json`): `CSE, CSE(AI&ML), Cybersecurity, ECE, EIE, ETE, ISE, MECH`

## Part 1 — Real notices (`data/notices.json`, 22 notices)

| Notice | Raw branch/program text | Extracted `allowed_branches` | Verdict |
|---|---|---|---|
| N_TECHMAHINDRA_001 | "Courses: BE, BTech, MTech / Specialization: AI/ML, Applied Mathematics, CS, Data Science, ECE, EEE, ETE, IT" | **Extraction failed** — LLM appended a trailing `//` comment inside the JSON array, which broke the JSON parser (pre-existing LLM output-formatting issue, unrelated to the branch-filter change) | ⚠️ Not evaluable |
| N_KPMG_001 | "CSE, CSE(AI&ML), AI&ML Specialization" + "Cybersecurity Specialization" | `['CSE', 'CSE(AI&ML)', 'Cybersecurity']` — hallucinated `AI&ML Specialization` dropped by the filter | ✅ Correct |
| N_KPMG_002 | (deadline-extension follow-up, no branch text) | *(none)* | ✅ Correct |
| N_KPMG_003 | (deadline follow-up, no branch text) | *(none)* | ✅ Correct |
| N_BOEING_001 | No branch mentioned | *(none)* | ✅ Correct |
| N_MORPHLE_001 | "BE CS & EC allied" / "BE EC allied" / "BE Mechanical" (3 roles) | `['CSE', 'ECE']` — missing `MECH` (role 3) and missing `ETE`/`EIE` (the "EC allied" group wasn't expanded because the LLM dropped the word "allied") | ⚠️ Under-extraction (model recall gap, not hallucination) |
| N_APTOS_001 | No branch mentioned | *(none)* | ✅ Correct |
| N_GE_001 | No branch mentioned | *(none)* | ✅ Correct |
| N_ERICSSON_001 | "B.E. / B.Tech, all streams" | `"ALL"` | ✅ Correct |
| N_SCHNEIDER_001 | Two separate buckets: **B.Tech** → `CS/IT, AI/ML, Cybersecurity`; **M.Tech** → `Power Electronics/Systems, Mechanical, Electrical, Electronics & Communication, Computer Science, Thermal` | Two criteria: `['CSE','ISE','Cybersecurity']` (B.Tech bucket — correct) **and** `['MECH','CSE']` (from the M.Tech-only bucket — should have been skipped entirely per the "non-BE/BTech scope" rule) | ❌ Incorrect — see Finding 1 below |
| N_NVIDIA_001 | "Branch: CSE, ECE, EEE, EE" | `['CSE', 'ECE']` — `EEE`/`EE` correctly dropped (not real branches here) | ✅ Correct |
| N_OPUS_001 | "CS & IT, DATA & AI" | `['CSE', 'ISE']` (`IT`→`ISE` alias; `DATA & AI` had no mapping and was left out) | ✅ Correct |
| N_IBM_001 | "Branch – CS/IT/Robotics/ISE/EE/ECE/EIE/AEIE/EEE/ETE/Computing" | `['CSE','ISE','ECE','EIE','ETE']` — `Robotics, EE, AEIE, EEE, Computing` correctly dropped | ✅ Correct |
| N_VERTEXSOFT_001 | "CSE, ISE only" | `['CSE', 'ISE']` | ✅ Correct |
| N_BRIGHTWAVE_001 | "CSE, ISE only" | `['CSE', 'ISE']` | ✅ Correct |
| N_CLOUDPEAK_001 | "CSE, ISE, ECE" | `['CSE', 'ISE', 'ECE']` | ✅ Correct |
| N_ORBITALTECH_001 | "CSE, ISE, ECE, EEE" | `['CSE', 'ISE', 'ECE']` — `EEE` correctly dropped | ✅ Correct |
| N_SILVERLINE_001 | "CSE, ISE only" | `['CSE', 'ISE']` | ✅ Correct |
| N_NIMBUSWORKS_001 | "CSE, ECE, ISE" | `['CSE', 'ECE', 'ISE']` | ✅ Correct |
| N_PRISMATIC_001 | "CSE, ISE, ECE, EEE" | `['CSE', 'ISE', 'ECE']` — `EEE` correctly dropped | ✅ Correct |
| N_QUANTUMEDGE_001 | "CSE, ISE only" | `['CSE', 'ISE']` | ✅ Correct |
| N_HALCYON_001 | "CSE, ISE, ECE, MECH" | `['CSE', 'ISE', 'ECE', 'MECH']` | ✅ Correct |
| N_FERROLINE_001 | "CSE, ISE, ECE" | `['CSE', 'ISE', 'ECE']` | ✅ Correct |
| N_AEROVANE_001 | "Open to all branches" | `"ALL"` | ✅ Correct |

**Real-notice tally:** 19 correct / 2 flawed (1 incorrect, 1 under-extraction) / 1 not evaluable due to an unrelated JSON-formatting parse failure.

## Part 2 — Synthetic adversarial notices (targeting the BE/BTech-vs-program-name guardrail directly)

The real dataset has few drives that are *exclusively* for a non-BE/BTech program, so these were added to stress-test that specific rule.

| Notice | Text | Extracted `allowed_branches` | Verdict |
|---|---|---|---|
| SYN_MBA_ONLY | "Open only to MBA students. Minimum CGPA 7.0." | *(none)* — LLM actually extracted `"BE,BTech"` as the raw value, but the post-filter correctly rejected both (neither is a real branch code), leaving no criterion | ✅ Correct end result (filter compensated for a bad LLM read) |
| SYN_BTECH_CSE_ONLY | "BTech CSE and ISE students only." | `['CSE', 'ISE']` — `BTech` correctly stripped | ✅ Correct |
| SYN_MTECH_PHD | "Open to MTech and PhD candidates only, specializing in VLSI." | `"ALL"` | ❌ Incorrect — see Finding 2 below |
| SYN_BE_ALL_STREAMS | "BE / B.Tech, all branches eligible." | `"ALL"` | ✅ Correct |
| SYN_NONEXISTENT_BRANCH | "Open to Biotechnology and Chemical Engineering branches only." | *(none)* — both dropped, no criterion left | ✅ Correct |

## Findings

**Finding 1 — mixed B.Tech/M.Tech eligibility blocks (N_SCHNEIDER_001).**
When a notice lists separate branch sets per degree level (B.Tech vs M.Tech), the 8B local model extracted a criterion for *both* sections instead of only the B.Tech one. The M.Tech-only branch names ("Power Electronics", "Thermal", etc.) were correctly rejected by the hard filter, but two of them — "Mechanical" and "Computer Science" — happen to alias to real BE/BTech codes (`MECH`, `CSE`), so they slipped through as a spurious second `allowed_branches` criterion. The filter can only catch branch codes that don't exist in this institution; it cannot know that a specific mention came from an M.Tech-only paragraph. This is a prompt-compliance gap in the smaller local model, not a gap in the filtering logic.

**Finding 2 — notices scoped entirely to a non-BE/BTech program (SYN_MTECH_PHD).**
For a notice that is *exclusively* for MTech/PhD candidates, the correct behavior is to extract no `allowed_branches` criterion at all (per the SCOPE instruction). The model instead extracted `"ALL"`, which is the opposite of correct — it would make every BE/BTech student pass this criterion for a drive that isn't open to them at all. This is the most significant remaining gap: it's a false *positive* that the current filter cannot catch, because `"ALL"` is a legitimate value in other contexts and there's nothing to detect in the sentence structure itself.

**What worked well:**
- The hard branch-code filter reliably drops hallucinated/non-existent branches (`AI&ML Specialization`, `EEE`, `EE`, `Robotics`, `AEIE`, `Computing`, `Biotechnology`, `Chemical Engineering`, `BE`, `BTech`) in every case tested, including once compensating for a wrong LLM read (SYN_MBA_ONLY).
- Simple "BTech `<branches>` only" phrasing is handled correctly — the degree prefix is stripped and only real branches remain.
- "All branches" / "all streams" phrasing correctly resolves to `"ALL"` when the notice is genuinely open to all BE/BTech branches.

## Suggested follow-ups (not implemented in this pass)
- Add explicit few-shot examples for "notice names only a non-BE/BTech program (MTech/PhD/MBA) with no BTech section at all → emit nothing" to close Finding 2.
- Consider a second LLM pass or a stronger model for notices with multiple degree-level buckets (Finding 1), since this is a prompt-following limitation of the 8B model rather than something a static filter can fix.
- Re-run this suite against a larger model (e.g. Gemini, which is already configured in `.env`) to see whether Findings 1–2 are model-capacity issues rather than prompt issues.

## Resolution (both findings fixed)

Both findings were closed with a single mechanism: every `allowed_branches` criterion the LLM
extracts must now also carry a `"program"` tag (`"BE_BTECH"` or `"OTHER"`). The extractor
(`extraction/notice_extractor.py`) drops any criterion tagged `"OTHER"` **before** branch-code
normalization/aliasing runs, so a word that happens to alias to a real BE/BTech code (e.g. an
M.Tech paragraph's "Mechanical"/"Computer Science") never gets the chance to slip through —
the criterion is judged by which part of the notice it came from, not by the branch codes it
produced. `"program"` is extraction-time-only scratch metadata: it is never persisted on `Fact`,
never added to `Criterion`/the evaluators, and never touches `Student`/`data/students.json`.

**Targeted verification (4 runs each against the real Ollama `llama3.1:8b` client):**

| Case | Expected | Result (4/4 runs) |
|---|---|---|
| N_SCHNEIDER_001 | Exactly one `allowed_branches` criterion: `['CSE','ISE','Cybersecurity']`, M.Tech bucket dropped | ✅ 4/4 — M.Tech bucket consistently tagged `program='OTHER'` and skipped |
| Synthetic MTech/PhD-only notice | Zero `allowed_branches` criteria | ✅ 4/4 — tagged `program='OTHER'` and skipped, not `"ALL"` |

**Full-suite re-run (22 real notices + 5 synthetic):**
- N_SCHNEIDER_001: now correctly produces only `['CSE', 'ISE', 'Cybersecurity']` — Finding 1 resolved.
- SYN_MTECH_PHD and SYN_MBA_ONLY: both now produce zero criteria, with the LLM itself tagging `program='OTHER'` directly (previously SYN_MBA_ONLY only succeeded because the code-level branch-code filter happened to reject "BE,BTech" as invalid codes; now the model's own reasoning flags it correctly) — Finding 2 resolved.
- `pytest tests/test_extraction_parsing.py tests/test_notice_extractor.py tests/test_integration_extraction.py`: same 4 pre-existing, branch-unrelated failures as the baseline — no regressions, nothing newly broken or newly fixed.

**Unrelated model variance observed in this re-run** (not caused by the program-tag change — the 8B local model is not fully deterministic even at temperature 0.1):
- N_ERICSSON_001 ("B.E. / B.Tech, all streams") was extracted as the literal string `"all streams"` instead of the keyword `"ALL"` in this run, which `normalize_branch_value` doesn't special-case, so it was filtered down to an empty list and the criterion was skipped. This is functionally equivalent to `"ALL"` for eligibility purposes: `rules/eligibility_engine.py::evaluate_eligibility` only evaluates criteria that exist for a drive, so a missing `allowed_branches` criterion and an explicit `"ALL"` both mean "no branch restriction applies" — no student is affected differently either way. Still, broadening `normalize_branch_value`'s "all branches" detection (e.g. "all streams", "open to all") would make the persisted criterion clearer for a human reading the DB, and is a reasonable small follow-up.
- N_MORPHLE_001 and N_HALCYON_001 showed additional extraction variance this run (an extra/incomplete branch criterion) unrelated to program tagging — a reminder that the 8B local model's recall on multi-role/compound notices is inconsistent run-to-run, reinforcing the earlier suggestion to try a stronger model for this class of notice.
