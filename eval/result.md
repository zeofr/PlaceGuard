# PlaceGuard Evaluation Results

## Full 100-case run (2026-11-06)

**Status: this is the full experiment** — all 100 cases in `data/gold_set.json`, all 34 unique
sources, real Ollama `llama3.1:8b` pipeline, no mocking. Supersedes the 30-case validation pass
below, which only existed to de-risk this run.

### Headline comparison (`eval/compare_baselines.py`)

| System | Accuracy | Macro-F1 | Hallucination | Temporal | Provenance | P95 Latency |
|---|---:|---:|---:|---:|---:|---:|
| LLM-only (Baseline A) | 65.0% | 43.1% | N/A | N/A | N/A | 1,174.5 ms |
| **PlaceGuard** | **81.0%** | **85.1%** | N/A* | 7/12 = 58.3% | 9/10 = 90.0% | 84,610.0 ms |

*Hallucination rate not measured this run — `--with-explanation` was skipped by decision (would
roughly double the already-long local-LLM runtime); see "What's still outstanding" below.

### PlaceGuard detail (`eval/run_eval.py`, 100 cases)

- **Eligibility accuracy: 81/100 = 81.0%** (confusion matrix below). H1 holds directionally
  (PlaceGuard clearly outperforms the bare LLM baseline, 81.0% vs 65.0%), but accuracy dropped
  from the 30-case subset's 100% once the full 34-source/100-case set exposed real bugs — see
  "New findings" below. These are genuine defects, not evaluation-harness artifacts.
- **Per-class**: ELIGIBLE 88.89% F1 (95.24% precision / 83.33% recall), INELIGIBLE 88.89% F1
  (80.00% precision / 100% recall), UNKNOWN 90.00% F1 (100% precision / 81.82% recall). Macro-F1
  85.1%, computed on only the 91 non-error cases (9 cases errored out entirely — see below).
- **Temporal-conflict accuracy: 7/12 = 58.3%** — down sharply from the validation pass's 8/8. Needs
  a closer look at which of the 12 temporal cases regressed (not yet root-caused in this pass).
- **Provenance accuracy: 9/10 = 90.0%** — consistent with the validation pass's 88.9% (one
  structurally similar miss).
- **Confusion matrix** (rows=actual, cols=predicted, excludes the 9 ERROR cases):

  |            | ELIGIBLE | INELIGIBLE | UNKNOWN |
  |---|---:|---:|---:|
  | ELIGIBLE   | 40 | 8 | 0 |
  | INELIGIBLE | 0 | 32 | 0 |
  | UNKNOWN    | 2 | 0 | 9 |

- **Accuracy by channel**: mixed 34/34 = 100%, email 47/62 = 75.8%, whatsapp 0/4 = 0% (all 4
  WhatsApp-channel cases are among the 9 hard errors below — DRIVE_IBM's graduation_year criterion).
- **Latency**: extraction mean 56.4s / P95 84.6s per case (local `llama3.1:8b` on CPU/local
  hardware — architectural stages themselves are sub-millisecond, same as the validation pass).

### Baseline A — LLM-only (`eval/baseline_llm_only.py`, 100 cases)

**65/100 = 65.0% accuracy, Macro-F1 43.1%.** Directionally consistent with the 30-case pass
(53.3%/38.9%) — the full run narrows the gap somewhat but PlaceGuard still leads by 16 points of
accuracy and 42 points of Macro-F1, supporting H1/H2/H3.

### Retrieval — Recall@K (`eval/eval_retrieval.py`, full 100-case set, 45 unique sources)

| Recall@3 | Recall@5 | Recall@10 |
|---:|---:|---:|
| 100.0% | 100.0% | 100.0% |

Still saturated even with the full source set — the `drive_id` metadata filter does the real work
here, so this metric isn't very discriminating for this architecture (noted previously).

### New findings (surfaced only by running the full 100-case / 34-source set)

These are genuine defects the 30-case subset happened not to exercise. None are artifacts of the
evaluation harness itself. **Not fixed in this pass** — flagging for a decision on priority.

**Finding A — unregistered criterion types crash the whole case (9/100 cases, all become ERROR).**
`rules/eligibility_engine.py` calls `get_evaluator(criterion.criterion_type)` for every extracted
criterion with no fallback; if the LLM emits a criterion type with no registered evaluator, the
whole case raises instead of degrading gracefully. Two distinct types triggered this:
- `graduation_year` (DRIVE_IBM, CASE_074/075/076/077 — all 4 of the WhatsApp-channel cases) — the
  notice says "Graduation Year: 2027", and the LLM extracted it as a criterion, but `Student` (see
  `data/students.json`) has no graduation-year field at all, so there's no way to evaluate this
  even if an evaluator existed. This likely needs to be an explicitly-excluded criterion type (like
  `registration_link` is already treated as metadata-only in `eligibility_engine.py`), not something
  to build a new evaluator for, unless graduation year becomes a tracked student attribute.
- `no_backlogs` (DRIVE_ERICSSON, CASE_090-094) — semantically this is just `max_backlogs: 0` by a
  different name; the LLM used a synonym that isn't in `CRITERION_TYPE_ALIASES`
  (`extraction/notice_extractor.py`), which already handles other synonym drift (e.g.
  `min_tenth_pct` → `min_10th_pct`). Adding `'no_backlogs': 'max_backlogs'` (with the value forced
  to `0`) would fix this specific case; the deeper issue is that `evaluate_eligibility` has no safety
  net for the next unknown synonym the LLM invents.

**Finding B — the `"ALL"` sentinel value is never recognized by the branch evaluators, so
"open to all branches" drives reject every student (CASE_048, CASE_050, CASE_100 — all DRIVE_AEROVANE).**
Extraction correctly produces `allowed_branches = "ALL"` for "Open to all branches" notices (this
is working as designed — see `eval/branch_extraction_report.md`). But neither
`rules/evaluators/branch.py` nor `rules/evaluators/allowed_branches.py` special-cases the string
`"ALL"` — `allowed_branches.py` does `raw.split(",")` on it, producing `["ALL"]`, and no real branch
code is ever equal to the string `"ALL"`, so every student fails this criterion. This is the
opposite of the intended behavior (a drive explicitly open to every branch currently rejects every
student). Pre-existing bug, not introduced by the branch-extraction work from earlier this session —
that work only touches which branches get into the list, not how the evaluator reads `"ALL"`.

**Finding C — `BRANCH_ALIASES` requires an exact string match, so phrasing drift inside a value
silently drops branches that should have matched.** CASE_053 (KPMG, student branch `Cybersecurity`)
and CASE_067 (Schneider, student branch `CSE(AI&ML)`) were both incorrectly predicted INELIGIBLE.
In this run the LLM extracted KPMG's two role-specific eligibility lines as two separate
`allowed_branches` criteria (`"CSE,CSE(AI&ML),AI&ML Specialization"` and
`"Cybersecurity Specialization"`) instead of merging them into one. The second normalized to an
*empty* list — `"cybersecurity specialization"` doesn't exact-match the `"cybersecurity"` key in
`BRANCH_ALIASES` (`extraction/notice_extractor.py`) — and got skipped by the empty-list guard added
earlier this session. Because both criteria use `list_operation: "replace"` for the same
drive/criterion_type/scope, reconciliation (`reconciliation/temporal_provenance_engine.py`) keeps
only one of the two same-rank, same-timestamp facts, so the branch the second criterion was
*supposed* to contribute (`Cybersecurity`) never makes it into the final list at all — even though
the extraction itself got the KPMG notice right when tested in isolation (see
`eval/branch_extraction_report.md`'s Part 1 table). Two independent contributing factors: (1) the
LLM doesn't always merge all of a notice's branch-eligible roles into one criterion, and (2)
`BRANCH_ALIASES`'s exact-match lookup has no fuzzy/substring fallback for phrasing like
`"<branch> Specialization"`.

### Findings A/B/C — fixed (2026-11-07)

All three findings were fixed in `extraction/notice_extractor.py`, `rules/eligibility_engine.py`,
`rules/evaluators/branch.py`, and `rules/evaluators/allowed_branches.py`. Four full re-runs
tracked the recovery:

| Run | Accuracy | Macro-F1 | Notes |
|---|---:|---:|---|
| Original full run | 81/100 = 81.0% | 85.1% | 9 ERROR cases (Finding A), AEROVANE always fails (Finding B), KPMG/Schneider/Opus/IBM branch under-extraction (Finding C) |
| + Findings A/B/C (merge fix) | 85/100 = 85.0% | 85.1% | 0 ERROR cases — Finding A fully fixed. AEROVANE now passes — Finding B fully fixed. Branch misses got *worse* in count (more cases now reach a real verdict instead of ERROR) because the merge fix alone didn't address the deeper root cause below |
| + Finding C2 (alias-suffix fuzzy match) | 92/100 = 92.0% | 91.7% | Fixed `"Cybersecurity Specialization"` / `"AI&ML Specialization"` losing their branch entirely (exact-match-only `BRANCH_ALIASES` lookup) |
| + Finding C3 (slash-split-before-alias-lookup) | **93/100 = 93.0%** | **92.5%** | Fixed `"AI/ML"` being destroyed into unmatched `"AI"`/`"ML"` fragments before alias lookup ever saw the whole token |

**Final headline comparison:**

| System | Accuracy | Macro-F1 | Hallucination | Temporal | Provenance | P95 Latency |
|---|---:|---:|---:|---:|---:|---:|
| LLM-only (Baseline A) | 65.0% | 42.8% | N/A | N/A | N/A | 1,027.5 ms |
| **PlaceGuard** | **93.0%** | **92.5%** | N/A | 7/12 = 58.3% | 9/10 = 90.0% | 74,431.7 ms |

**What each fix actually was:**
- **Finding A**: added `'no_backlogs'`/`'no_active_backlogs'` → `max_backlogs` (value forced to `0`,
  regardless of the LLM's raw value shape) to `CRITERION_TYPE_ALIASES`; told the extraction prompt
  to never extract `graduation_year` (no student field exists for it); hardened
  `evaluate_eligibility` to skip any criterion type with no registered evaluator (logged, not
  evaluated) instead of raising — so no future LLM-invented criterion type can crash a case again.
- **Finding B**: both `rules/evaluators/branch.py` and `rules/evaluators/allowed_branches.py` now
  special-case `criterion.value == "ALL"` as an unconditional pass, before the list/comma-split
  membership check that previously made it fail everyone.
- **Finding C** (three contributing bugs, fixed together):
  1. Added `_merge_same_batch_allowed_branches()` in `extraction/notice_extractor.py`, called right
     before `extract_criteria_from_notice` returns — unions multiple `allowed_branches`/`"replace"`
     facts that share `(drive_id, scope)` from the *same* extraction call, instead of letting
     reconciliation's same-rank/same-timestamp tie-break silently pick one and drop the rest.
  2. `_normalize_single_branch_value` now also tries stripping a trailing qualifier word
     (" specialization", " stream", " branch(es)", " only", " department") and retrying the alias
     lookup, so `"Cybersecurity Specialization"` → `Cybersecurity` instead of being dropped as
     unrecognized.
  3. `normalize_branch_value` no longer splits on `/` before alias lookup — it only splits on `,`
     first, tries the whole comma-separated part against aliases/groups (so `"AI/ML"` matches the
     now-added `"ai/ml"` → `CSE(AI&ML)` key directly), and only falls back to splitting on `/` for
     parts that don't match as a whole (e.g. `"ECE/ETE"` still correctly splits into two branches).

**Residual gap (93% vs. the 30-case validation pass's 100%) is a mix of two things, not a code
defect left behind by this fix:**
- Re-extracting the Schneider and Opus notices fresh, 3 times each, after all fixes landed
  consistently produces the correct branch set every time (`['CSE','ISE','CSE(AI&ML)','Cybersecurity']`
  for Schneider, `['CSE','ISE']` for Opus) — confirming the code fix is correct. CASE_065/067/069/097
  (Schneider/Opus CSE(AI&ML) students) still failing in the v4 run's cached result is pure local-LLM
  non-determinism: `eval/run_eval.py` caches one extraction per source for the whole run, so one bad
  draw for that one source affects every case referencing it, and a different draw would have passed.
- A few failures are unrelated pre-existing gaps surfaced incidentally: CASE_037/CASE_087 (a
  `no_prior_offer` / branch-null criterion not making it into that particular extraction draw, so the
  missing-data case resolves to a false ELIGIBLE instead of UNKNOWN) and CASE_083 (a 3-backlog
  student passing because that draw's `max_backlogs` criterion didn't make it through either). These
  are extraction-recall variance on the local 8B model, not something Findings A/B/C were meant to
  fix.

### Data-leakage fix + multi-run variance + hallucination rate (2026-11-09)

**Data-leakage bug found and fixed first.** While building a blind gold-set verification
worksheet (`gold_set_verification.md`), `ingestion/portal/adapter.py`'s `_build_message_body()`
was found to be rendering `data/sis_data.json`'s `notes` field — plain-English answers like
"Portal authority rank 4 loses to email rank 2" — directly into the text handed to the LLM
extractor, in both the real ingestion pipeline and `eval/run_eval.py`. This affected 12/100 gold
cases, 5/10 (50%) of `provenance_reasoning_required` cases, and 5/12 (~42%) of
`temporal_reasoning_required` cases — precisely the metrics meant to evidence H3/H4. Fixed by
removing the `[PORTAL NOTE: ...]` rendering block entirely (now just a comment explaining why it
must never be rendered). This was a methodological validity issue independent of whether it moved
any single number — the metric was not measuring what it claimed to measure while the leak was
present, regardless of outcome.

**Then: 3 independent full re-runs + 1 `--with-explanation` run, against the leak-fixed pipeline.**
Each run is a complete re-extraction via the real local `llama3.1:8b` (no caching across runs), run
back-to-back. Full detail in `eval/variance_report.md`; headline:

| Metric | Mean (3 runs) | Std dev |
|---|---:|---:|
| Accuracy | 92.0% | ±0.0% |
| Macro-F1 | 91.7% | ±0.0% |
| Temporal-conflict accuracy | 58.3% | ±0.0% |
| Provenance accuracy | 90.0% | ±0.0% |
| UNKNOWN-detection accuracy | 83.3% | ±0.0% |
| Hard errors / 100 | 0.0 | ±0.0 |
| Mean per-case latency | 87,478 ms | ±16,532 ms |

Baseline A (LLM-only) over the same 3 runs: **65.0% accuracy (±1.7%), 43.1% Macro-F1 (±2.0%)** —
PlaceGuard leads by a mean 27.0 points of accuracy, consistent across every run.

Note: accuracy/temporal/provenance are **identical to the single-run 93%-era numbers reported
above within a point**, and did not move after the portal-note leak was fixed — the leak turned
out not to have flipped any of these particular gold-case verdicts in practice, even though it was
still a genuine construct-validity defect worth fixing (the measurement was invalid regardless of
whether the specific outcome happened to be unaffected this time). The small 1-point accuracy
difference (92.0% here vs. 93.0% in the single v4 run above) is ordinary local-LLM extraction
variance across different runs/dates, not evidence of a regression — see the "Residual gap" note
above on why a few branch/criterion extractions are non-deterministic on this 8B model.

**Hallucination rate / evidence support (`--with-explanation`, single run, 100 cases, 374 decomposed
factual claims):**

- **Hallucination rate: 7.2%** (27/374 unsupported claims)
- **Evidence support rate: 92.8%**
- This run's own eligibility accuracy was 88.0% (not pooled into the variance average above —
  explanation generation adds an extra LLM call per case, run once by explicit scope decision, not
  3×).

This closes out the two previously-outstanding items from "What's still outstanding" below:
the `--with-explanation` pass is now run, and the result.md numbers now reflect a run-to-run
variance estimate (not a single lucky/unlucky run) on the leak-fixed pipeline.

### Finding E — root cause of the 58.3% temporal-conflict accuracy, fixed (2026-11-09)

Root-caused by directly re-running extraction + reconciliation for all 5 failing temporal cases
(`CASE_014`, `CASE_016` — DRIVE_ORBITALTECH; `CASE_061`, `CASE_062`, `CASE_063` — DRIVE_NVIDIA) and
diffing the reconciled criterion values/sources against `expected_current_rules`. All 5 traced to a
single bug, unrelated to temporal/provenance reasoning itself:

**Root cause**: `ALLOWED_BRANCHES` (`extraction/notice_extractor.py`) was derived *only* from the
branch codes currently present in `data/students.json`. Since no student in the current roster
happens to be enrolled in `EEE` (Electrical & Electronics Engineering), that branch — though a real,
notice-stated eligible branch for both drives — was being silently dropped by
`_filter_to_allowed_branches` as if it were an LLM hallucination, producing
`['CSE','ISE','ECE']`/`['CSE','ECE']` instead of the correct branch lists. This had nothing to do
with the temporal/provenance logic the metric is nominally measuring; it happened to surface there
only because `temporal_correct` requires an exact match on *every* criterion for the drive, not just
the one actually in temporal conflict. None of the 5 affected students are themselves EEE/EE branch,
so the final ELIGIBLE/INELIGIBLE verdict was unaffected — hence `correct=True` but
`temporal_correct=False` for all 5 before the fix.

**Fix** (`extraction/notice_extractor.py`): the allowed-branch set is now a fixed canonical list
(`_CANONICAL_ALLOWED_BRANCHES`, includes `EEE`) that the student roster can only *widen*, never
narrow — so a branch with zero currently-enrolled students is never treated as invalid. Also added
`"ee"`/`"eee"` → `EEE` to `BRANCH_ALIASES` (confirmed with the user: `EE` is an alias for `EEE`, not
a distinct branch).

**Gold-set data bug surfaced by the fix**: once `EE` correctly normalized to `EEE` instead of being
dropped, `CASE_061`/`062`/`063`'s `expected_current_rules.allowed_branches.value` turned out to
itself be wrong — `['CSE','ECE','EEE','EE']`, i.e. the gold set had been authored by taking the raw
notice text at face value and listing `EEE` and `EE` as two separate branches. Corrected to
`['CSE','ECE','EEE']` in `data/gold_set.json` (3-entry diff, verified via `git diff`).

**Verification**: re-ran all 5 cases through the real `run_eval.py` harness
(`python -m eval.run_eval --cases CASE_014,CASE_016,CASE_061,CASE_062,CASE_063`) against the fixed
code + corrected gold data — **5/5 eligibility correct, 5/5 temporal_correct**. Combined with the 7
already-passing temporal cases, **temporal-conflict accuracy is now 12/12 = 100%**, up from 7/12 =
58.3%, with zero change to the eligibility verdict on any of the 5 (confirms this was purely a
provenance/value-fidelity bug, not an eligibility-accuracy regression hiding behind it).

A second, independent bug remains in the two ORBITALTECH cases (not fixed, doesn't affect this
metric since neither case is `provenance_reasoning_required`): the WhatsApp correction notice
restates CGPA/10th%/12th% as "unchanged" alongside the actual backlog correction, and reconciliation
has no notion of "this value is being restated, not re-asserted" — so its same-rank/latest-timestamp
tie-break hands provenance for those unchanged values to the WhatsApp message too, when the original
email should stay authoritative for everything except backlogs.

**Full single-run confirmation (2026-11-09, `eval/post_fix_run/`)**: per scope decision, a single
full 100-case pass (not a 3-run variance repeat — this fix is a deterministic code change, not
something sensitive to LLM run-to-run variance; see reasoning given at the time) was run against
the fixed code + corrected gold data: `run_eval`, `baseline_llm_only`, `eval_retrieval`,
`run_eval --with-explanation`, `compare_baselines`, in sequence.

| System | Accuracy | Macro-F1 | Hallucination | Temporal | Provenance | P95 Latency |
|---|---:|---:|---:|---:|---:|---:|
| LLM-only (Baseline A) | 67.0% | 44.8% | N/A | N/A | N/A | 1,149.8 ms |
| **PlaceGuard** | **92.0%** | **91.7%** | **6.1%** (23/379 claims) | **12/12 = 100.0%** | 9/10 = 90.0% | 119,789.1 ms |

(The plain `run_eval` sub-run, before the `--with-explanation` overwrite, independently scored
90/100 = 90.0% / Macro-F1 90.19% — the 2-point difference from the `--with-explanation` run's own
92.0% is ordinary run-to-run local-LLM extraction variance on the known residual gap below, not
caused by this fix; both sub-runs agree exactly on temporal (12/12 = 100.0%) and provenance
(9/10 = 90.0%), which is what this fix targeted.)

**Temporal-conflict accuracy is confirmed at 12/12 = 100.0%** (up from 58.3%), matching the
individual-case verification above. Provenance accuracy (90.0%) and the baseline comparison are
essentially unchanged from before the fix, as expected — this fix only touched the branch
allowlist, which the temporal cases happened to be sensitive to and the provenance cases didn't
depend on. The residual ~8-10 case gap from 100% is the same previously-documented pattern: LLM
extraction non-determinism on CSE(AI&ML)/Cybersecurity-branch cases (CASE_065/067/069/073/097) plus
a few unrelated pre-existing gaps (CASE_037/087's `has_prior_offer`/branch-null UNKNOWN cases,
CASE_083's backlog-criterion extraction miss, CASE_070/075 — see the "Residual gap" note earlier in
this document) — none of it introduced by this fix.

This single full run supersedes the pre-fix numbers as the current headline result.

### Finding D — percentage-as-CGPA extraction bug — fixed, triggered live by real OCR notices (2026-11-10)

Originally flagged (not fixed) from an intermediate re-run: the LLM sometimes reads a combined
"X% across 10th, 12th and UG/B.E./B.Tech" statement and applies the same literal percentage number
to a `min_cgpa`-shaped criterion, even though `Student.cgpa` is a 0–10 scale, not a percentage. This
went from theoretical to actually breaking a real case once 2 real screenshot notices were added to
the eval (see "OCR-sourced gold-set cases" below) — `DRIVE_COGNIZANT_ACE`'s notice states exactly
this pattern, and a 9.4-CGPA student was wrongly scored INELIGIBLE against a literal `min_cgpa=60`
threshold no real CGPA can ever reach.

**Fix** (`extraction/notice_extractor.py`): CGPA is always 0–10, so any extracted `min_cgpa` value
greater than 10 can only be a percentage the LLM read literally — no prompt change or LLM judgment
call needed, just a deterministic post-processing conversion (`value / 10`, e.g. `60 → 6.0`) in the
same per-item normalization block that already special-cases `no_backlogs`/`deadline`. A value of
exactly `10` (a legitimate perfect-CGPA requirement) is correctly left untouched by the strict `> 10`
check. Also added `min_ug_pct`/`min_ug_percentage` → `min_cgpa` to `CRITERION_TYPE_ALIASES`, since
the LLM sometimes names this combined criterion that way instead of `min_cgpa` outright.

**Two more real bugs surfaced by the same 2 OCR notices, fixed alongside this:**
- **Semicolon-separated branch lists weren't split.** Ujjivan's notice produced a branch value like
  `"...,Websecurity; AML,..."` — `normalize_branch_value` only ever split on commas, so that whole
  semicolon-joined chunk was tried as one unrecognized token instead of two real aliases. Fixed by
  splitting on both `,` and `;` (comma-splitting behavior for existing cases is unaffected — grepped
  all of `data/notices.json`/`data/whatsapp_messages.json` and confirmed no existing notice text
  contains a semicolon).
- **"No standing arrears" wasn't recognized as a backlogs synonym at all** — "arrears" is
  South-Indian-English terminology for backlogs, and the extraction prompt never mentioned it, so
  the LLM sometimes extracted *nothing* for that requirement. Added `no_arrears`/`no_standing_arrears`/
  `max_arrears` → `max_backlogs` (forced to `0`, same as `no_backlogs`) to `CRITERION_TYPE_ALIASES`,
  and mentioned "arrears" explicitly in the prompt's `max_backlogs` description.
- **A 4th related bug found during the full-suite regression re-check**, not from the OCR notices:
  the LLM sometimes names the backlog criterion bare `"backlogs"` instead of `"max_backlogs"` — since
  that wasn't in the alias map either, it became an invisible fact under a different `RuleKey`,
  entirely skipped by reconciliation. This silently broke provenance attribution for
  `DRIVE_BRIGHTWAVE` and `DRIVE_QUANTUMEDGE` (90.0%→30.0% provenance accuracy in one regression
  draw) even though it didn't change any eligibility verdict. Fixed by adding
  `backlogs`/`active_backlogs` → `max_backlogs` as a plain rename (not forced to `0`, since a bare
  `"backlogs"` value could legitimately be any count, e.g. "max 2 backlogs" mistyped as a type name).

**Regression-verified**: all 4 changes above touch shared extraction code used by every case, not
just the 2 OCR ones that needed them, so the full original 100-case suite was re-run twice (once
before, once after the `backlogs`→`max_backlogs` fix) to confirm no regression:

| Run | Accuracy | Macro-F1 | Temporal | Provenance | UNKNOWN detection |
|---|---:|---:|---:|---:|---:|
| Before Finding D fix (last confirmed, §Finding E) | 92.0% | 91.7% | 100.0% | 90.0% | 83.3% |
| After Finding D fix, before `backlogs` rename | 95.0% | 94.0% | 100.0% | **30.0%** (regression, diagnosed) | 83.3% |
| After `backlogs` rename (final) | **96.0%** | **94.78%** | **100.0%** | **90.0%** | 83.3% |

Final state: accuracy and Macro-F1 both improved over the last confirmed numbers (the `backlogs`
alias fix helps generally, not just the 2 drives that exposed it), temporal and provenance both back
to their confirmed levels, and the 4 remaining failures (`CASE_037`, `CASE_083`, `CASE_087`,
`CASE_097`) are the same previously-documented residual LLM extraction non-determinism — nothing new.

### OCR-sourced gold-set cases — `CASE_101`-`CASE_104` (2026-11-10)

The user supplied 6 real placement-notice screenshots (`data/images/`). 5 of the 6 were usable
(`notice_2.jpeg` has no visible company/header and was skipped) and added as **4 new, separate**
gold-set cases exercising the **real OCR call** at eval time (`extraction/ocr_client.py`'s
`extract_text_from_image`, via a new `image_path`-based source kind in `eval/run_eval.py` — not
pre-transcribed text standing in for OCR). Ground truth was derived independently by reading the raw
screenshots directly, same discipline as the rest of the gold set. One case
(`CASE_101`/`CASE_102` — Cognizant Ace Team, IDFC) deliberately exercises the Finding D
percentage-as-CGPA fix above; one (`CASE_103` — Ujjivan) deliberately exercises new branch aliases
(`websecurity`/`web security` → `Cybersecurity`, `aml` → `CSE(AI&ML)`) rather than hand-simplifying
the expected branch list; one (`CASE_104` — Eightfold AI) is a clean explicit-CGPA case that also
verifies the existing "never extract graduation_year" rule still holds when the notice arrives via
OCR. `CASE_101` additionally pairs the original Cognizant notice with a same-channel, deadline-only
correction notice (`notice_3.jpeg`), testing that a correction restating nothing else doesn't corrupt
the original notice's other facts.

**Result: 4/4 pass** (`python -m eval.run_eval --cases CASE_101,CASE_102,CASE_103,CASE_104`),
including `CASE_101`'s temporal/provenance sub-checks. **Known caveat, disclosed in `CASE_101`'s
`notes` field**: the local 8B model doesn't reliably extract "no standing arrears" on every draw
despite the arrears-synonym fix (pure LLM recall variance, same category as other residual gaps
documented in this file) — `CASE_101`'s `temporal_correct`/`provenance_correct` may occasionally read
`False` on an unlucky draw even though eligibility is unaffected.

These 4 cases are **additive and separate from the verified, stratified 100-case set** — not folded
into the headline 96.0% accuracy number above, since they weren't part of the original stratified
sample or any prior verification pass. If they are included in a future full run, that should be
disclosed as `104 cases (100 original + 4 OCR-sourced)`, not silently blended into "100 cases."

### What's still outstanding

1. ~~**`--with-explanation` pass**~~ — **done (2026-11-09)**: Hallucination rate 7.2%, evidence
   support rate 92.8% (374 claims, single run). See above.
2. ~~**Finding D**~~ — **fixed (2026-11-10)**, see above.
3. ~~**Temporal-conflict accuracy (58.3%)**~~ — **root-caused and fixed (2026-11-09, see Finding
   E)**, confirmed via full-suite re-run at **100.0%** (see Finding D's regression table above).
4. Load/throughput testing (§18) and the full §21 table with Standard RAG / RAG+DB rows remain out
   of scope per the user's decision (Baseline A + PlaceGuard only).
5. ~~**OCR-sourced test cases**~~ — **done (2026-11-10)**, see above (`CASE_101`-`104`). Further OCR
   cases, if added later, should follow the same pattern: additive, scoped `--cases` runs, not
   folded into the main suite's headline number.
6. **Independent gold-set verification** — `gold_set_verification.md` (a stratified 16-case blind
   worksheet) has been built but the actual blind verification pass has not yet been reported back
   as completed by the user.

---

# PlaceGuard Evaluation — Trimmed Validation Run (superseded by the full run above)

**Status: validation pass only, not the final experiment.** This run used a 30-case
subset of the full 100-case `data/gold_set.json` (selected to touch every one of the
13 most structurally-interesting drives — the 7 fictional drives with real cross-source
conflicts, plus NVIDIA, KPMG, APTOS, BOEING, GE, HALCYON — covering all 3 ingestion
channels, every category, and both temporal and provenance reasoning) to validate that
the rewritten pipeline works end-to-end against the real local LLM (Ollama `llama3.1:8b`)
before committing to the much slower full 100-case / 45-unique-source run.

Run date: 2026-11-04. LLM provider: `ollama` (`llama3.1:8b`, local, `LLM_PROVIDER=ollama` in `.env`).

## Headline comparison (`eval/compare_baselines.py`)

| System | Accuracy | Macro-F1 | Hallucination | Temporal | Provenance | P95 Latency |
|---|---:|---:|---:|---:|---:|---:|
| LLM-only (Baseline A) | 53.3% | 38.9% | N/A | N/A | N/A | 1,290 ms |
| **PlaceGuard** | **100.0%** | **100.0%** | N/A* | 8/8 = 100.0% | 8/9 = 88.9% | 58,573 ms |

*Hallucination rate requires `python -m eval.run_eval --with-explanation` (not run here — needs an
extra LLM call per case to generate and decompose explanations, would roughly double runtime).

## PlaceGuard detail (`eval/run_eval.py`, 30 cases)

- **Eligibility accuracy: 30/30 = 100%** (confusion matrix: 14 ELIGIBLE, 8 INELIGIBLE, 8 UNKNOWN, zero off-diagonal errors)
- **Per-class precision/recall/F1: 100% across ELIGIBLE, INELIGIBLE, UNKNOWN**
- **Temporal-conflict accuracy: 8/8 = 100%** — every case requiring temporal reasoning (deadline
  extensions, CGPA corrections, branch-list corrections) resolved to the value the real
  `reconcile_facts()` algorithm says is current.
- **Provenance accuracy: 8/9 = 88.9%** — one miss: `CASE_024` (`DRIVE_NIMBUSWORKS`,
  the outdated/forwarded-notice test). The final eligibility verdict was still correct
  (INELIGIBLE, matching ground truth) and the *value* reconciliation picked was right, but the
  reconciled `allowed_branches` fact was attributed to a different same-rank source than the gold
  set's `authoritative_source` — i.e. the LLM extraction didn't flag that specific restatement as a
  correction the same way the authored ground truth assumed. Worth a closer look in the full run,
  but it did not affect the eligibility decision.
- **Latency**: reconciliation and rule-engine stages are sub-millisecond (as expected for
  deterministic code); essentially all latency is local LLM extraction
  (mean 38.1s/case, P95 58.6s/case) — a function of running `llama3.1:8b` on local hardware, not of
  the architecture itself.
- **Accuracy by channel**: email-only 11/11 = 100%, mixed-channel 19/19 = 100%.

## Baseline A — LLM-only (`eval/baseline_llm_only.py`, same 30 cases)

**16/30 = 53.3% accuracy, Macro-F1 38.9%.** Failure pattern: the LLM-only baseline defaults to
ELIGIBLE whenever it can't confidently resolve a conflict, and systematically fails to produce
UNKNOWN even when information is genuinely missing (every UNKNOWN gold case was misclassified as
ELIGIBLE or INELIGIBLE) and fails most conflict/outdated-notice cases (`CASE_016`, `CASE_024`,
`CASE_032`, `CASE_062` — all cases requiring picking the authoritative source over a conflicting or
outdated one). This is exactly what H1/H2/H3 predict: a bare LLM, with no deterministic rule engine
and no temporal/provenance reasoning, cannot reliably reproduce the right answer on conflicting or
incomplete information — and it also cannot be trusted to abstain (say UNKNOWN) rather than guess.

## Retrieval — Recall@K (`eval/eval_retrieval.py`, same 30 cases)

| Recall@3 | Recall@5 | Recall@10 |
|---:|---:|---:|
| 100.0% | 100.0% | 100.0% |

Expected: the drive_id metadata filter alone narrows each query to a handful of candidate sources,
so recall is saturated. Recall@K is more informative on the full 100-case set where some drives have
more sources competing for the top-K slots.

## What this validates

- The full pipeline (raw text → LLM extraction → reconciliation → deterministic rule engine) runs
  correctly against a real local LLM, not just the deterministic components in isolation.
- The gold set's `expected_current_rules`, `expected_eligibility`, and `authoritative_source` values
  are self-consistent with the actual `reconcile_facts()` / `evaluate_eligibility()` implementations
  (not hand-typed guesses — see `data/gold_set.json`'s generation notes).
- A real, measurable gap between PlaceGuard and a bare LLM baseline exists and matches the
  project's research hypotheses.

## What's still outstanding

1. **Full 100-case run** — this was a 30-case subset chosen for speed (local Ollama inference is
   the bottleneck: ~38s mean per unique source extracted). The full run touches all 45 unique
   sources across all 22 drives; expect roughly 45 × ~35–60s ≈ 25–45 minutes for `run_eval.py` alone,
   plus ~100 × ~1s for `baseline_llm_only.py` (fast — one call per case, not per source).
2. **`--with-explanation` pass** — not run; needed for the Hallucination Rate / Evidence Support
   Rate metrics (§8/§9 of the plan).
3. **`CASE_024` provenance mismatch** — worth a manual look at the raw extraction output once the
   full run is available, to see whether it's a one-off LLM extraction quirk or a pattern worth
   tightening the extraction prompt for.
4. Load/throughput testing (§18) and the full §21 table with Standard RAG / RAG+DB rows are out of
   scope per the user's decision this session (Baseline A + PlaceGuard only).

## How to reproduce / extend

```bash
# Full 100-case run (slow — see latency note above)
python -m eval.run_eval
python -m eval.baseline_llm_only
python -m eval.eval_retrieval
python -m eval.compare_baselines

# Trimmed subset used for this validation pass
python -m eval.run_eval --cases CASE_001,CASE_004,CASE_006,...
```
