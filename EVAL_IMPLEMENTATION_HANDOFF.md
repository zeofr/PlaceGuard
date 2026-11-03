# Evaluation Plan Implementation — Handoff / Continuation Doc

Read this first in the new session, then re-read `PlaceGuard_Evaluation_Plan.md` and the approved
plan file content below. This doc has everything needed to resume without re-deriving it.

The approved plan (from plan mode) is also saved at:
`C:\Users\vinee\.claude\plans\go-through-the-readme-md-glimmering-hoare.md`
— read that file too, it has the phase breakdown. This doc adds the detailed data design that
plan file doesn't contain (it was worked out live after the plan was approved).

## Decisions locked in by the user this session (do not re-ask)

1. Baselines in scope: **Baseline A (LLM-only) + PlaceGuard** only. Baseline B/C deferred.
2. Benchmark must run the **real end-to-end pipeline** (raw text → extraction → reconciliation →
   rule engine), not the old shortcut of handing `expected_current_rules` straight to the rule engine.
3. Dataset size: **100 test cases** (not 500).
4. Must cover **all 3 real channels**: email notices, informal WhatsApp messages, SIS/portal records
   — including cross-channel conflicts.
5. Sampled 50 real placement emails from the user's inbox (read-only, via
   `scripts/sample_placement_emails.py` — already written and run) to learn authentic phrasing.
   That script is safe to keep/reuse; the sampled output was scratch-only, not committed.

## What's already done

- `scripts/sample_placement_emails.py` — created. Read-only Gmail sampler (calls only `.fetch()`,
  never `mark_as_read`/`add_label`). Already run once, 50 real emails reviewed for patterns
  (forwarded notices, "Fwd:" chains, deadline phrasing like "Today 5:30 PM"/"Tomorrow 9 AM",
  eligibility criteria buried in long JD text, same-thread corrections, hiring-schedule tables,
  final-selects announcements). No further action needed on this file.
- `data/students.json` — **expanded from 30 to 42 students** (USNs `1MS22CS031`..`1MS22EC042`
  appended). New students cover: missing branch (`1MS22CS031`, branch=null), missing
  has_prior_offer (`1MS22IS032`), missing tenth_pct (`1MS22CS033`), missing twelfth_pct
  (`1MS22EC034`), boundary CGPA exactly 7.0 (`1MS22CS035`), backlogs=2 boundary (`1MS22IS036`),
  double-missing cgpa+backlogs (`1MS22CS037`), high achiever (`1MS22CS038`), prior-offer-true
  #2 (`1MS22CI039`), low achiever (`1MS22ME040`), boundary 10th/12th=60 exact (`1MS22CS041`),
  strong ECE student (`1MS22EC042`). **This file is done — no more changes needed to it.**

## Key technical findings from this session (do not re-derive)

- `rules.eligibility_engine.evaluate_eligibility(student, criteria) -> EligibilityResult` — already
  correct for ELIGIBLE/INELIGIBLE/UNKNOWN semantics (FAIL beats UNKNOWN beats ELIGIBLE; every
  criterion always evaluated, no short-circuit). **Do not modify this file.**
- `reconciliation.temporal_provenance_engine.reconcile_facts(facts: list[Fact]) -> dict[RuleKey, Fact]`
  is the **pure, no-DB-write** reconciliation function to use in the eval harness (not
  `reconcile_facts_for_drive`, which needs a `db: Session` and persists). Algorithm: group by
  `RuleKey(drive_id, criterion_type, scope)`; within a group, highest authority rank wins
  (lower number = higher authority); among facts at that rank, if any `is_correction=True`, the
  latest such correction by `effective_timestamp` wins; otherwise the latest `effective_timestamp`
  at that rank wins. **Authority always beats recency across ranks.**
- **IMPORTANT GOTCHA — branch add/remove delta logic does NOT live in `reconcile_facts()`.**
  It lives only in `api/routes/ingestion.py`'s `_merge_branch_delta_facts()`, which is an
  ingestion-route-specific patch step operating against already-persisted `ExtractedCriterion`
  rows, not something `reconcile_facts()` knows about. **Decision: do NOT use `list_operation`
  "add"/"remove" scenarios in the gold-set benchmark** — only use "replace"-style full-list
  branch corrections (which `reconcile_facts()` handles correctly via the normal
  authority+is_correction+recency rule). This keeps the benchmark testing the actual
  reconciliation engine rather than route-layer patching logic that's a separate concern
  (already covered by its own unit tests from earlier this session).
- **GOTCHA — `rules/evaluators/deadline.py` compares against `date.today()`** (real wall-clock
  date when the test runs), not a fixed timestamp. **Decision: do NOT include a "deadline"
  criterion in any gold-set case's `expected_current_rules`** — results would silently change
  over time and break reproducibility. Notices can still *mention* deadlines for narrative/realism
  and temporal-chain color, just don't assert on them in the answer key. (This matches the
  original 12-case gold_set's existing convention — it never asserted on deadline either.)
- Evaluator semantics per `criterion_type` (confirmed by reading `rules/evaluators/*.py`):
  - `min_cgpa`, `min_10th_pct`, `min_12th_pct`: `student_value >= criterion.value`; `None` → UNKNOWN.
    Operator convention: `"gte"`.
  - `max_backlogs`: `student.backlogs <= criterion.value`; `None` → UNKNOWN. Operator convention: `"lte"`.
  - `allowed_branches`: exact uppercase string membership check (`student.branch.upper() in [...]`)
    — **note `"CSE(AI&ML)"` and `"CSE"` are different strings**, use this for deliberate
    branch-code-precision test cases. `None` branch → UNKNOWN. Operator convention: `"in"`.
  - `no_prior_offer`: PASS iff `student.has_prior_offer is False`; `None` → UNKNOWN. Operator: `"eq"`, value `false`.
  - A drive with **no stated criterion** for some aspect (e.g. no branch restriction at all) simply
    has no `Criterion` for that type — it's never evaluated, not UNKNOWN. Useful for "open to all
    branches" cases.
  - A case with **zero criteria at all** → `evaluate_eligibility` returns ELIGIBLE by default
    (empty status list has no FAIL/UNKNOWN in it) — this is correct per spec, not a bug; use it
    deliberately for one "open to all, no stated bar" case (mirrors old `CASE_011` SoftEdge case).
- `ingestion/portal/adapter.py`'s `PortalAdapter._build_message_body()` converts each
  `data/sis_data.json` `placement_events[]` entry into a text blob starting `=== {company_name} ===`
  — portal/SIS data goes through the **same LLM extraction path** as email/WhatsApp
  (`extract_criteria_from_notice`), it is NOT structured-parsed separately. So in the eval harness,
  SIS events need to be converted to this same text-blob shape and run through
  `extract_with_confidence()` exactly like email/WhatsApp — no special-casing needed. Portal
  `source_type="student_portal"`, `authority_rank=4` (between email/WhatsApp-official rank 2 and
  student-forward rank 5).
- `core.schemas.SOURCE_AUTHORITY_RANK`: `official_company_pdf=1`, `placement_cell_whatsapp=2`,
  `placement_cell_email=2`, `coordinator_whatsapp=3`, `student_portal=4`, `student_whatsapp=5`.
- Existing `data/notices.json` (13 entries) and `data/sis_data.json` (10 `placement_events`)
  **already share 10 real-company-named drives** (KPMG, Boeing, NVIDIA, Schneider, TechMahindra,
  IBM, GE, Morphle, Aptos, Ericsson — plus Opus which has no SIS entry, 11 "real" drives total) —
  and the SIS entries already carry `"notes"` fields documenting which ones are
  `CONSISTENT`/`CONFLICT`/`PARTIAL`/`INCOMPLETE` vs. the email notices. **Only NVIDIA has a genuine
  numeric conflict usable for reconciliation testing** (portal CGPA 7.5 stale vs. email correction
  CGPA 7.8 — email rank 2 beats portal rank 4). The rest are `CONSISTENT`, so just reuse them
  single-channel with varied students for "Normal"/"Missing info"/"Multi-condition" cases — don't
  invent conflicts that aren't really there.
- **The original `gold_set.json`'s 12 cases reference notice ids (N001–N018) that don't exist
  anywhere in `data/notices.json`** — that dataset's raw-notice companion file was never committed
  (same orphaned-file problem as `synthetic_students.json`). **Decision: `gold_set.json` will be
  fully replaced (not merged/appended) by the new 100-case version** — there is nothing reusable
  in the old 12 cases' raw content, only their *pattern* (which is already reflected in the new
  design below).

## The 100-case design (fully worked out — just needs to be written as data + code)

**22 drives total: 11 existing "real-company" drives (reuse as-is, single/dual-channel) + 11 new
fictional drives (need new notices/whatsapp/sis content, carry the temporal/conflict/outdated
complexity).** Branch codes used throughout: `CSE, ISE, CSE(AI&ML), Cybersecurity, ECE, MECH, ETE,
EIE, EEE`.

### New fictional drives to author (content not yet written — this is the next step)

For each, write: 1 email notice (`data/notices.json`), plus whatsapp/portal entries where noted
(`data/whatsapp_messages.json` — **new file, doesn't exist yet**, same shape as notices.json but
informal tone; and 2 new entries appended to `data/sis_data.json`'s `placement_events`).

1. **DRIVE_VERTEXSOFT** — email T1 (rank2, 2026-10-20): CGPA 7.5+, branches CSE/ISE, no backlogs.
   WhatsApp correction T2 (rank2, 2026-10-21, `is_correction=true`): "CGPA requirement is 7.0, not
   7.5." Student forward T3 (rank5, 2026-10-23, `is_forwarded=true`): forwards the original 7.5
   email verbatim. **Winner: min_cgpa gte 7.0 (source=whatsapp correction), allowed_branches
   in [CSE,ISE] (source=email), max_backlogs lte 0 (source=email).** Forward must be ignored
   (rank5 < rank2) — dedicated outdated/forward test. 4 cases: `1MS22CS001`(ELIGIBLE),
   `1MS22EC005`(INELIGIBLE, multi-fail), `1MS22CS035`(ELIGIBLE, cgpa=7.0 exact boundary),
   `1MS22CS037`(UNKNOWN, cgpa+backlogs null), plus pad `1MS22CS041`(ELIGIBLE, cgpa7.65) = 5 cases.

2. **DRIVE_BRIGHTWAVE** — official PDF rank1 (2026-10-18): CGPA 7.5+, CSE/ISE only, no backlogs.
   Coordinator WhatsApp rank3 (2026-10-19): claims CGPA 6.5, open to all, no backlog rule (should
   be ignored — rank1 beats rank3 regardless of recency). **Winner: min_cgpa gte 7.5
   (source=pdf), allowed_branches in [CSE,ISE] (pdf), max_backlogs lte 0 (pdf).**
   Cases: `1MS22CS020`(ELIGIBLE), `1MS22EC005`(INELIGIBLE), `1MS22IS004`(INELIGIBLE, cgpa7.45<7.5
   narrow miss), pad `1MS22CS038`(ELIGIBLE) = 4 cases. provenance_reasoning_required=true.

3. **DRIVE_CLOUDPEAK** — email rank2 (2026-10-22): CGPA 7.5+ ("revised up from earlier posting"),
   branches CSE/ISE/ECE, no backlogs. SIS portal event (new, rank4, portal_last_updated
   2026-10-19, stale): CGPA 7.0+, same branches. Student rumor WhatsApp rank5 (2026-10-24): "heard
   it's 6.5 only" (ignore). **Winner: min_cgpa gte 7.5 (source=email), allowed_branches
   in [CSE,ISE,ECE] (email), max_backlogs lte 0 (email).** 3-channel case.
   Cases: `1MS22EC042`(ELIGIBLE), `1MS22EC034`(INELIGIBLE, cgpa7.4<7.5), `1MS22IS009`(UNKNOWN,
   backlogs null), pad `1MS22EC018`(ELIGIBLE) = 4 cases. temporal+provenance both true.

4. **DRIVE_ORBITALTECH** — email rank2 (2026-10-15): CGPA 8.0+, branches CSE/ISE/ECE/EEE, no
   backlogs (max 0), min 70% 10th & 12th. WhatsApp correction rank2 (2026-10-17,
   `is_correction=true`): "backlog rule relaxed — up to 2 backlogs allowed now." **Winner:
   min_cgpa gte 8.0 (email), allowed_branches in [CSE,ISE,ECE,EEE] (email), max_backlogs lte 2
   (source=whatsapp correction, supersedes the email's 0), min_10th_pct gte 70 (email),
   min_12th_pct gte 70 (email).**
   Cases: `1MS22CS038`(ELIGIBLE), `1MS22ET023`(INELIGIBLE, cgpa+branch fail), `1MS22IS036`(
   INELIGIBLE, cgpa fail only — backlogs=2 exactly passes the relaxed rule, good boundary test),
   `1MS22EC026`(ELIGIBLE), pad `1MS22CS024`(ELIGIBLE) = 5 cases.

5. **DRIVE_SILVERLINE** — email rank2 (2026-10-16): CGPA 7.0+, branches CSE/ISE only, no backlogs.
   WhatsApp correction rank2 (2026-10-18, `is_correction=true`, **full replace list, NOT an
   add/remove delta** — "eligible branches are CSE, ISE, ECE (full updated list)"). **Winner:
   allowed_branches in [CSE,ISE,ECE] (source=whatsapp correction), min_cgpa gte 7.0 (email),
   max_backlogs lte 0 (email).**
   Cases: `1MS22EC042`(ELIGIBLE), `1MS22CS029`(ELIGIBLE, cgpa7.05 boundary), `1MS22ET012`(
   INELIGIBLE), pad `1MS22IS025`(ELIGIBLE) = 4 cases.

6. **DRIVE_NIMBUSWORKS** — email rank2 (2026-10-14): CGPA 6.5+, branches CSE/ECE/ISE, no backlog
   rule stated. WhatsApp correction rank2 (2026-10-16, `is_correction=true`, full replace): "eligible
   branches are CSE and ECE only (ISE removed)." Student forward rank5 (2026-10-20,
   `is_forwarded=true`): forwards the original T1 email claiming all 3 branches still eligible —
   must be ignored. **Winner: allowed_branches in [CSE,ECE] (source=whatsapp correction),
   min_cgpa gte 6.5 (email). No max_backlogs criterion at all (never stated) — backlogs never
   checked for this drive.**
   Cases: `1MS22EC018`(ELIGIBLE), `1MS22IS025`(**INELIGIBLE** — dedicated outdated/forward test:
   ISE was removed, the naive/forward-trusting answer would wrongly say ELIGIBLE), `1MS22ET023`(
   INELIGIBLE, branch), pad `1MS22CS016`(ELIGIBLE, cgpa6.8, no backlog criterion so backlogs=1
   irrelevant) = 4 cases.

7. **DRIVE_PRISMATIC** — single email rank2 (2026-10-12), no conflict: CGPA 8.5+, branches
   CSE/ISE/ECE/EEE, no backlogs, min 75% 10th & 12th. Straightforward 5-criteria multi-condition.
   Cases: `1MS22CS013`(ELIGIBLE), `1MS22CS007`(INELIGIBLE, 3-way fail), `1MS22EI030`(INELIGIBLE,
   branch — EIE not in list), `1MS22EC026`(INELIGIBLE, cgpa8.35<8.5 narrow miss), pad
   `1MS22CS038`(ELIGIBLE) = 5 cases.

8. **DRIVE_QUANTUMEDGE** — official PDF rank1 (2026-10-10): CGPA 7.0+, branches CSE/ISE, no
   backlogs. SIS portal event (new, rank4, posted 2026-10-08, stale/different scope): "CGPA 7.0+,
   open to all branches." Student rumor WhatsApp rank5 (2026-10-15): "heard it's CGPA 6.0, open to
   all" (ignore). **Winner: min_cgpa gte 7.0 (pdf — portal agrees on CGPA so no real conflict
   there, but authority still decides), allowed_branches in [CSE,ISE] (source=pdf, portal's
   "open to all" loses on authority alone), max_backlogs lte 0 (pdf).** Pure-authority 3-channel
   test (PDF wins regardless of recency).
   Cases: `1MS22CI015`(INELIGIBLE — branch "CSE(AI&ML)" string ≠ "CSE", precision test),
   `1MS22IS017`(ELIGIBLE), `1MS22CS016`(INELIGIBLE, cgpa+backlog), pad `1MS22CS041`(ELIGIBLE)
   = 4 cases.

9. **DRIVE_HALCYON** — single email rank2 (2026-10-11), no conflict: CGPA 7.0+, branches
   CSE/ISE/ECE/MECH, no backlogs, min 65% 10th & 12th, no prior offer. 5 criteria incl.
   `no_prior_offer` — designed to be reused heavily for missing-info variety.
   Cases: `1MS22CS037`(UNKNOWN — cgpa+backlogs null), `1MS22IS032`(UNKNOWN — prior_offer null),
   `1MS22CS033`(UNKNOWN — 10th null), `1MS22EC034`(UNKNOWN — 12th null), `1MS22CI039`(
   INELIGIBLE — branch CSE(AI&ML) not listed AND prior_offer=true), `1MS22ME040`(INELIGIBLE,
   multi-fail), pad `1MS22ME010`(ELIGIBLE) = 7 cases.

10. **DRIVE_FERROLINE** — single email rank2 (2026-10-13), no conflict: CGPA 7.65+, branches
    CSE/ISE/ECE, max 2 backlogs, min 60% 10th & 12th. Deliberate boundary-value drive.
    Cases: `1MS22CS041`(ELIGIBLE — cgpa=7.65 exact, 10th=12th=60 exact, all boundary gte passes),
    `1MS22ET023`(INELIGIBLE, cgpa7.55 narrow miss + branch), `1MS22IS036`(ELIGIBLE — backlogs=2
    exact boundary, lte passes), pad `1MS22CI027`(INELIGIBLE — branch "CSE(AI&ML)" ≠ "CSE") = 4 cases.

11. **DRIVE_AEROVANE** — single email rank2 (2026-10-09), no conflict: CGPA 6.5+, open to all
    branches (no allowed_branches criterion at all), no backlogs. Simple normal/boundary drive.
    Cases: `1MS22ET012`(INELIGIBLE — backlog fail only, cgpa=6.5 exact boundary passes),
    `1MS22CS029`(ELIGIBLE), `1MS22ME040`(INELIGIBLE), `1MS22CS035`(ELIGIBLE) = 4 cases.

New-drive subtotal: 5+4+4+5+4+4+5+4+7+4+4 = **50 cases**.

### Existing "real" drives — reuse single/dual-channel, vary students only

Use existing `data/notices.json` text content as-is (already written, read earlier this session).
Map each notice's prose to criteria per the evaluator conventions above (operators: `gte` for
academic, `lte` for max_backlogs, `in` for allowed_branches, `eq`/`false` for no_prior_offer).
Branch-code mapping already decided per drive below — use exactly these lists.

- **KPMG** (`N_KPMG_001`, email only — the 2 KPMG WhatsApp entries already in notices.json are
  deadline-only, not used in `expected_current_rules` per the "no deadline assertions" rule
  above): `allowed_branches=[CSE,CSE(AI&ML),Cybersecurity]`, `min_10th_pct=60`, `min_12th_pct=60`,
  `max_backlogs=0`. Cases: `1MS22CI002`(ELIGIBLE), `1MS22EC005`(INELIGIBLE), `1MS22CY006`(
  ELIGIBLE), `1MS22CS033`(UNKNOWN — 10th null), `1MS22CS001`(ELIGIBLE) = 5 cases.
- **BOEING** (`N_BOEING_001`): `min_cgpa=7.0` only. Cases: `1MS22ME010`(ELIGIBLE),
  `1MS22ET012`(INELIGIBLE), `1MS22CS037`(UNKNOWN), `1MS22IS032`(ELIGIBLE, cgpa7.6),
  `1MS22EI030`(ELIGIBLE) = 5 cases.
- **NVIDIA** (`N_NVIDIA_001` email rank2 CGPA7.8 + new SIS entry rank4 CGPA7.5 stale — genuine
  cross-channel conflict, see findings above): `min_cgpa=7.8` (source=email),
  `allowed_branches=[CSE,ECE,EEE,EE]`→ use `[CSE,ECE,EEE]` (drop "EE" dup of EEE) (source=email).
  Cases: `1MS22EC026`(ELIGIBLE), `1MS22CS016`(INELIGIBLE), `1MS22EC042`(ELIGIBLE),
  `1MS22CS037`(UNKNOWN) = 4 cases. provenance+temporal both true.
- **SCHNEIDER** (`N_SCHNEIDER_001`): `min_10th_pct=65`, `min_12th_pct=65`, `max_backlogs=0`,
  `allowed_branches=[CSE,CSE(AI&ML),Cybersecurity]`. Cases: `1MS22CY019`(ELIGIBLE),
  `1MS22EC005`(INELIGIBLE), `1MS22CI021`(ELIGIBLE), `1MS22CS041`(INELIGIBLE — 60%<65% narrow
  miss), `1MS22CI039`(ELIGIBLE) = 5 cases.
- **TECHMAHINDRA** (`N_TECHMAHINDRA_001`): `min_10th_pct=50`, `min_12th_pct=50`,
  `allowed_branches=[CSE,CSE(AI&ML),ECE,ETE,ISE]`. Cases: `1MS22ET023`(ELIGIBLE),
  `1MS22ME022`(INELIGIBLE), `1MS22EI014`(INELIGIBLE — EIE not listed), `1MS22CI002`(ELIGIBLE)
  = 4 cases.
- **IBM** (`N_IBM_001`, whatsapp rank2): `min_cgpa=7.0`, `max_backlogs=0`,
  `allowed_branches=[CSE,ISE,ECE,EEE,EIE,ETE]`. Cases: `1MS22EI014`(ELIGIBLE),
  `1MS22CS029`(ELIGIBLE), `1MS22ME010`(INELIGIBLE, branch), `1MS22ET012`(INELIGIBLE,
  cgpa+backlog) = 4 cases.
- **GE** (`N_GE_001`): `min_cgpa=8.0` only. Cases: `1MS22CS020`(ELIGIBLE), `1MS22CS007`(
  INELIGIBLE), `1MS22IS009`(ELIGIBLE — cgpa=8.0 exact boundary), `1MS22CS037`(UNKNOWN),
  `1MS22CS029`(INELIGIBLE, cgpa7.05) = 5 cases.
- **MORPHLE** (`N_MORPHLE_001`): `min_cgpa=6.0`, `max_backlogs=0`,
  `allowed_branches=[CSE,ISE,ECE,ETE,EIE,MECH]`. Cases: `1MS22ET012`(INELIGIBLE, backlog),
  `1MS22ME010`(ELIGIBLE), `1MS22CS029`(ELIGIBLE), `1MS22EI030`(ELIGIBLE), `1MS22CS031`(
  UNKNOWN — branch null) = 5 cases.
- **APTOS** (`N_APTOS_001` — notice states no extractable numeric/branch criteria at all →
  `expected_current_rules={}` empty, vacuous ELIGIBLE for everyone, deliberate test of "don't
  invent unstated criteria"). Cases: `1MS22CS001`(ELIGIBLE), `1MS22ME040`(ELIGIBLE despite
  terrible stats — correct per spec) = 2 cases.
- **ERICSSON** (`N_ERICSSON_001`): `min_10th_pct=60`, `min_12th_pct=60`, `max_backlogs=0` (no
  branch restriction — all streams). Cases: `1MS22ET012`(INELIGIBLE), `1MS22CS029`(ELIGIBLE),
  `1MS22CY028`(ELIGIBLE), `1MS22CS033`(UNKNOWN, 10th null), `1MS22EI014`(ELIGIBLE) = 5 cases.
- **OPUS** (`N_OPUS_001`): `allowed_branches=[CSE,CSE(AI&ML),ISE]` only. Cases:
  `1MS22CS024`(ELIGIBLE), `1MS22ME022`(INELIGIBLE), `1MS22CI027`(ELIGIBLE), `1MS22EC005`(
  INELIGIBLE) = 4 cases.

Real-drive subtotal: 5+5+4+5+4+4+5+5+2+5+4 = **48 cases**.

**Running total 50+48 = 98.** Add 2 more anywhere to hit exactly 100 (e.g. one more KPMG student,
one more AEROVANE student) — not load-bearing, just pick any two more student/drive pairings
following the same patterns above and compute the expected result the same way.

### `authoritative_source` field

Every case's `expected_current_rules[criterion_type]` should include `"authoritative_source"` =
the winning fact's `source_id` (per the "winner" notes above) — this field is **load-bearing** for
**Provenance Accuracy**, unlike the old gold_set.json where it was dead/unused data.

### Category tagging

Tag each case with a `"category"` field (one of: `normal`, `temporal_conflict`,
`conflicting_sources`, `missing_info`, `multi_condition`, `outdated_forwarded`) for the ~20/20/15/
15/20/10 proportion target — approximate is fine, exact proportions aren't load-bearing, but do
set `temporal_reasoning_required`/`provenance_reasoning_required`/`expected_unknown` accurately
per case since those ARE read by the eval harness for sub-accuracy metrics.

## Remaining implementation steps (in order)

1. **Write the new-drive content**: append ~11 new email notices to `data/notices.json`; create
   `data/whatsapp_messages.json` (new file) with the WhatsApp-channel entries described above
   (corrections, coordinator rumor, student forwards/rumors); append 2 new `placement_events` to
   `data/sis_data.json` (CLOUDPEAK, QUANTUMEDGE) using the exact text-blob shape
   `ingestion/portal/adapter.py`'s `_build_message_body()` produces (see "Key technical findings"
   above — fields: `event_id, company_name, job_title, role_designation, employment_type, lpa,
   preferred_skills, work_mode, bond_agreement, apply_before, event_date, registration_status,
   portal_posted_date, portal_last_updated, eligibility_criteria, time_since_posted, notes`).
2. **Write `data/gold_set.json`** — full replace with the 100 cases designed above. Shape per
   case (same fields as the old file, plus new `category` field):
   `case_id, description, drive_id, student_id (USN), notices_in_scope (list of source_ids —
   can span notices.json/whatsapp_messages.json/sis_data.json), expected_current_rules
   (per-criterion_type: operator, value, authoritative_source), expected_eligibility,
   expected_unknown, temporal_reasoning_required, provenance_reasoning_required, category, notes`.
3. **Rewrite `eval/run_eval.py`** per the approved plan file's Phase 2 (full pipeline: resolve
   `notices_in_scope` ids against all 3 source files → `extract_with_confidence()` per item →
   `reconcile_facts()` (pure fn) → compare winners to `expected_current_rules` for
   Temporal/Provenance accuracy → build `Criterion`s from the *reconciled* winners (not the
   answer key) → `evaluate_eligibility()` → Eligibility Accuracy/Macro-F1/UNKNOWN accuracy →
   optional `--with-explanation` flag for Hallucination Rate → per-stage latency → save
   `eval/placeguard_results.json` → extended `print_report()` with channel breakdown).
4. **Add `eval/eval_retrieval.py`** (Recall@5) — scratch ChromaDB instance, index all 3 source
   files, query per case, compare against `notices_in_scope`.
5. **Fix `eval/baseline_llm_only.py`** — repoint at real `data/students.json` + all 3 source files
   instead of the missing synthetic files.
6. **Update `eval/compare_baselines.py`** — read new result shapes, print fuller §21 table for the
   2 in-scope systems only.
7. **Verify** per the plan file's Verification section (run all 4 eval scripts end-to-end, hand-
   check 4-5 cases across channels, confirm `placeguard_dev.db`/`data/chroma_db` untouched).

## Files touched so far (current git status additions beyond the earlier RAG-migration session)

- `scripts/sample_placement_emails.py` — new, done.
- `data/students.json` — modified, done (42 students now).
- `EVAL_IMPLEMENTATION_HANDOFF.md` — this file.

Nothing else has been written yet for the eval work — `data/notices.json`, `data/sis_data.json`,
`data/gold_set.json`, `data/whatsapp_messages.json`, and all of `eval/*.py` are still pending per
the steps above.
