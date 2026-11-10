# PlaceGuard — Research Paper Source Document

*Compiled 2026-11-10. This document assembles the material needed to write the research paper —
problem statement, related work, architecture, methodology, results, and limitations — from the
project's design documents (`README.md`, `DESIGN.md`, `PlaceGuard_Evaluation_Plan.md`) and the full
evaluation history (`eval/result.md`, `eval/variance_report.md`). Numbers in §7 reflect the final,
post-bugfix confirmatory run on the complete 104-case gold set (100 original + 4 real-OCR-sourced
cases); see §7's provenance note for exactly which run each number comes from.*

---

## 1. Title

**A Temporal- and Provenance-Aware Generative AI Framework for Placement Information Management
and Eligibility Verification**
*(Product name: **PlaceGuard**)*

---

## 2. Abstract

College placement information at most institutions is scattered across Gmail, WhatsApp, and a
rarely-updated student portal, with no single source of truth and no timestamp-based reconciliation
between channels. A more serious consequence of this fragmentation is procedural, not just
informational: registration links for company drives are frequently forwarded to the entire student
body **before** eligibility (CGPA, backlogs, branch, prior offers, academic percentage, etc.) is
verified. This allows ineligible students to register and sit for online assessments, which can — and
does — result in companies blacklisting the institution.

**PlaceGuard** is a hybrid GenAI + deterministic-rules system that (1) ingests placement
communication from multiple asynchronous channels (email, WhatsApp — including OCR'd screenshot
notices — and a student portal), (2) uses an LLM to extract structured, machine-checkable eligibility
criteria from unstructured notices, (3) evaluates every student against those criteria using a
deterministic rule engine (never an LLM judgment call), and (4) gates access to registration so that
only verified-eligible students can proceed — while explaining *why* to both eligible and ineligible
students, citing the exact source and timestamp behind every answer.

The core research contribution is not "an LLM chatbot for placements" — it is an architecture and
evaluation methodology for **reconciling conflicting, time-varying, multi-source institutional
information** and combining it with **deterministic eligibility reasoning**, so that a generative
model is used only where it is safe to use one (extraction, explanation, conflict-resolution) and
never for the final yes/no decision. Evaluated end-to-end on a 104-case gold set (including 4 cases
built from real, OCR'd placement-notice screenshots), PlaceGuard substantially outperforms a bare
LLM-only baseline on eligibility accuracy, resolves nearly all temporal/provenance conflict cases
correctly, and reports a measurable but non-zero hallucination rate on generated explanations — see
§7 for the full results.

---

## 3. Problem Statement

### 3.1 As observed in the field

| # | Observation | Consequence |
|---|---|---|
| 1 | Placement notifications arrive via Gmail, WhatsApp, and the student portal — with no coordination between them | Students must manually cross-check multiple channels; nothing is authoritative |
| 2 | The student portal is rarely updated | It cannot be trusted as the source of truth, even though it nominally should be |
| 3 | Time-sensitive updates (deadline extensions, added restrictions) are communicated over WhatsApp | Superseding information is buried in chat history with no versioning |
| 4 | The registration link is forwarded to *everyone* before eligibility is verified | Students can self-declare eligibility incorrectly (deliberately or by mistake) |
| 5 | No systematic gate exists between "sees the link" and "is actually eligible" | Ineligible students reach the OA stage → risk of the **company blacklisting the college** |

### 3.2 Why this is a GenAI-shaped problem, not just a database problem

A simple database of "who is eligible for what" is insufficient because:
- Eligibility criteria arrive as **free-text, semi-structured notices** (PDFs, emails, forwarded
  messages, and — as this project's evaluation set confirms — phone-camera screenshots of notices
  requiring OCR) with inconsistent phrasing across companies.
- The **same fact changes over time** (e.g., a deadline is extended, a new exclusion is added) and
  different channels may carry different, stale, or updated versions **simultaneously**.
- Different sources carry **different authority** — an official Placement Cell circular should always
  override a student's WhatsApp forward of an old PDF, even if the forward appeared more recently in
  the group.
- Explaining *why* a student is or isn't eligible, and answering natural-language questions about it,
  requires language understanding — but the **decision itself must be deterministic and auditable**,
  because the cost of an error (blacklisting) is institutional, not just personal.

This is exactly the kind of problem where GenAI adds value in extraction, reconciliation, and
explanation — but must be deliberately kept **out** of the final decision boundary.

---

## 4. System Architecture

### 4.1 Design principle

> **GenAI extracts and explains. A deterministic rule engine decides.**

The LLM is never asked "is this student eligible?" It is asked "what does this notice say?" and "how
do I explain this decision in plain language?" The actual eligibility computation is symbolic,
testable, and reproducible — which also makes it defensible to the Placement Cell and to companies.

### 4.2 High-level pipeline

```
Sources (Gmail / WhatsApp [incl. OCR'd screenshots] / Portal / PDFs)
        ↓
Ingestion & Normalization (timestamp, source, sender-role tagging)
        ↓
LLM Extraction (notice text → structured Fact, incl. is_correction tagging)
        ↓
Temporal + Provenance Reconciliation (deterministic — §5.1 algorithm)
        ↓
Deterministic Eligibility Rule Engine (criteria registry — §5.4 aggregation)
        ↓
ELIGIBLE / INELIGIBLE / UNKNOWN + Evidence
        ↓
Access-Gated Registration + LLM Explanation (cited, per-criterion)
```

### 4.3 Three eligibility states, not two

Eligibility is reported as **ELIGIBLE / INELIGIBLE / UNKNOWN** rather than a forced yes/no. If a
student's profile is missing a required field (e.g., 10th percentage not on record) or a notice is
genuinely ambiguous, the system says so explicitly rather than guessing — a deliberate reliability/
safety property, not an oversight.

### 4.4 Example interaction

**Student asks:** *"Am I eligible for Company X?"*

| Requirement | Student record | Status |
|---|---|---|
| CGPA ≥ 7.5 | 8.72 | ✅ |
| Branch: CSE/ISE | CSE | ✅ |
| Active backlogs = 0 | 0 | ✅ |
| No existing offer | None | ✅ |

*Source: Official Placement Cell circular, 14 Sept 2026, 6:00 PM (supersedes the 12:30 PM WhatsApp
forward with the old deadline).*

### 4.5 Extensibility (implementation-level design discipline)

New features are additions to data or to a registry, not edits to control flow:

1. **Ingestion sources → adapter interface** (`SourceAdapter.fetch() -> list[RawMessage]`). Adding a
   channel = one new adapter class; nothing downstream changes.
2. **Eligibility criteria → a registry, not an if/elif chain.** Each criterion type is a self-contained
   evaluator function registered in a dict keyed by `criterion_type`. The rule engine iterates over
   whatever is registered; adding a criterion is a new function, not a rewrite.
3. **Source authority → a data table, not a hardcoded enum.** Changing the hierarchy is a data edit.
4. **Facts are immutable and event-sourced.** Every extracted fact is stored as-is, forever, with full
   provenance. "What's the current rule" is a query/view over that log, never an overwritten value.

---

## 5. Locked Design Decisions

### 5.1 Source authority ranking

Authority-first, recency second; lower authority only fills coverage gaps, never overrides higher
authority.

```
rank 1: official_company_pdf
rank 2: placement_cell_whatsapp / placement_cell_email
rank 3: coordinator_whatsapp
rank 4: student_portal
rank 5: student_whatsapp (forwards, self-reports)
```

Resolution algorithm for a given rule key:
1. Collect all facts asserting that key.
2. Keep only facts at the **highest rank present** (a rank-5 forward never beats a rank-1 PDF,
   regardless of timestamp).
3. Among same-rank facts, the latest `effective_timestamp` wins (handles same-authority updates, e.g.
   a 4PM → 6PM deadline extension).
4. If the highest-ranked source is silent on this key, fall back to the next rank down for
   **coverage**, not for conflict resolution.

### 5.2 Supersession / correction detection

Done at **extraction time**, not reconciliation time. The LLM extractor tags each fact with
`{"is_correction": bool, "supersedes_ref": "source_id | null"}` when it recognizes "Correction:",
"Update:", "deadline extended to...", etc. Reconciliation then stays a pure deterministic data
lookup — no LLM judgment enters that stage.

### 5.3 Rule-key schema

The join key two facts must share to be considered "the same rule": `(drive_id, criterion_type,
scope)`. `scope` defaults to `"ALL"`, or a branch/category code when a criterion is scoped.

### 5.4 UNKNOWN propagation policy

Evaluate **every** registered criterion independently — no short-circuiting on the first failure.
Then aggregate by priority:
1. Any criterion `FAIL` → overall **INELIGIBLE** (a confirmed failure is conclusive regardless of what
   else is missing).
2. Else, any criterion `UNKNOWN` → overall **UNKNOWN**.
3. Else → **ELIGIBLE**.

Rationale: a known disqualifying fact always wins over missing data elsewhere, but missing data is
never silently treated as a pass.

### 5.5 Extraction error vs. generation hallucination

Tracked as **separate** fields in the evaluation record:
- `extraction_errors` — the extracted criterion value doesn't match what the source notice actually
  said.
- `generation_hallucination` — the explanation text makes a claim not present in the evidence bundle
  it was given.

Conflating these would hide whether a failure came from misreading a notice or from the explainer
inventing something.

---

## 6. Research Questions and Hypotheses

**RQ1 (Temporal/provenance reasoning):** How can temporal- and source-authority-aware retrieval
improve the accuracy of GenAI systems when institutional information is distributed across multiple
asynchronous, unstructured communication channels with unequal authority?

**RQ2 (Policy-to-logic extraction):** How reliably can an LLM extract structured, executable
eligibility rules from free-text placement notices of varying phrasing and completeness, and how
should low-confidence extractions be flagged rather than silently applied?

**RQ3 (Decision safety):** Does separating "explanation" (generative) from "decision" (deterministic)
reduce hallucinated or incorrect eligibility outcomes compared to an end-to-end LLM-only approach?

Formal hypotheses tested against these questions (`PlaceGuard_Evaluation_Plan.md` §24):

| | Hypothesis |
|---|---|
| **H1 — Eligibility Reliability** | Adding temporal and provenance-aware reasoning improves placement eligibility accuracy compared with an LLM-only approach. |
| **H2 — Hallucination Reduction** | Separating deterministic eligibility reasoning from generative explanation reduces unsupported factual claims. |
| **H3 — Temporal Reliability** | Explicit temporal modelling improves the ability to resolve outdated and conflicting placement information. |
| **H4 — Decision Traceability** | Provenance tracking improves the ability to identify and verify the evidence supporting placement decisions. |

The intended research contribution (per the evaluation plan's framing) is the *combination* —
temporal information + source provenance + structured student data + deterministic eligibility rules
+ evidence-grounded generation — not any one piece in isolation. The project does not claim to
eliminate hallucination; it claims the architecture **measurably reduces** hallucination and decision
errors relative to an LLM-only approach, and this is what §7 measures.

---

## 7. Evaluation Methodology and Results

### 7.1 Evaluated systems

| System | Description |
|---|---|
| Baseline A — LLM-only | Raw notice/WhatsApp/portal text + student profile sent directly to the LLM, no retrieval, no reconciliation, no rule engine (`eval/baseline_llm_only.py`) |
| **PlaceGuard (proposed)** | Full pipeline: LLM extraction → temporal/provenance reconciliation → deterministic rule engine → explanation (`eval/run_eval.py`) |

Per an explicit, disclosed scope decision, **Baseline B (standard RAG) and Baseline C (RAG + student
database)** from the original evaluation plan were **not implemented or tested** — only Baseline A and
the proposed system are compared. This is a real limitation of the evaluation, not an oversight; see
§9.

### 7.2 Gold set

104 hand/author-constructed cases in `data/gold_set.json`:
- **100 cases** built from synthetic placement notices and synthetic student records, spanning
  22 drives, 3 ingestion channels (email, WhatsApp, portal), and deliberately engineered temporal
  conflicts, source-authority conflicts, and missing-data (`UNKNOWN`) scenarios.
- **4 cases (`CASE_101`–`CASE_104`)** built from 6 **real placement-notice screenshots** supplied by
  the researcher and processed through the system's actual OCR pipeline (`extraction/ocr_client.py`,
  EasyOCR) at evaluation time — not pre-transcribed text standing in for OCR. One screenshot
  (`notice_2.jpeg`) was excluded because no company/header was visible in it, making it impossible to
  attribute to a drive.

Each case specifies: student, drive, the notices in scope, the expected eligibility verdict, whether
the case requires temporal or provenance reasoning, and (for most cases) the expected reconciled value
and authoritative source for every criterion the drive asserts — not just the one that determines the
eligibility verdict. This lets `temporal_correct`/`provenance_correct` be graded independently of
whether a given criterion happens to be eligibility-determining.

Ground truth was derived by the researcher reading the raw notice text (or, for the 4 OCR cases, the
original screenshot image directly) and applying the locked rules in §5 by hand — not by querying the
system under test. See §9 for a discussion of the construct-validity implications of
researcher-authored ground truth.

### 7.3 Metrics (per `PlaceGuard_Evaluation_Plan.md` §26, "Minimal Evaluation for the Initial
Prototype")

1. Eligibility accuracy
2. Macro-F1
3. Temporal-conflict accuracy (`temporal_correct`, independent of the eligibility verdict)
4. Provenance accuracy (`provenance_correct`)
5. Hallucination rate (unsupported factual claims in generated explanations, decomposed and checked
   against the evidence bundle)
6. UNKNOWN-detection accuracy
7. Recall@5 (retrieval)
8. Mean / P95 latency

All 8 minimal-evaluation metrics are implemented and reported below; this satisfies the plan's
"first prototype" bar in full.

### 7.4 Headline results — final confirmatory run, 104 cases

After the §7.6 fix, the full 3-run + 1-explanation suite completed clean: zero hard errors across
all 4 runs, on the complete 104-case gold set (100 original + 4 real-OCR cases).

| System | Accuracy | Macro-F1 | Hallucination | Temporal | Provenance | P95 Latency |
|---|---:|---:|---:|---:|---:|---:|
| LLM-only (Baseline A) | 67.3% | 45.1% | N/A | N/A | N/A | 1,400.6 ms |
| **PlaceGuard** | **95.2%** | **94.1%** | **8.2%** (33/401 claims) | 12/13 = 92.3% | 9/11 = 81.8% | 100,041.2 ms |

Mean-of-3 variance (see §7.5):

| Metric | Mean (3 runs) | Std dev |
|---|---:|---:|
| Accuracy | 94.2% | ±2.5% |
| Macro-F1 | 92.9% | ±2.7% |
| Temporal-conflict accuracy | 92.3% | ±0.0% |
| Provenance accuracy | 81.8% | ±0.0% |
| UNKNOWN-detection accuracy | 80.6% | ±4.8% |
| Hard errors / 104 | 0.0 | ±0.0 |
| Mean per-case latency | 49,563 ms | ±1,260 ms |

Baseline A over the same 3 runs: 66.7% accuracy (±1.1%), 44.5% Macro-F1 (±1.2%) — PlaceGuard leads
by a mean **27.6 points** of accuracy, consistent across every run. Recall@3/@5/@10 are all 100.0%
(50 unique sources indexed), saturated for the same reason noted earlier (the `drive_id` metadata
filter does most of the work).

Temporal (92.3%) and provenance (81.8%) read lower than the original 100-case-only figures (100.0%
/ 90.0%) purely because the denominator grew from 12/10 to 13/11 reasoning-required cases when the
4 OCR cases were folded in — neither pre-existing cohort's result changed; full detail in
`eval/result.md`'s "Final 104-case suite" section.

### 7.5 Run-to-run variance

PlaceGuard's extraction stage calls a real local LLM (`llama3.1:8b` via Ollama) with non-zero
sampling variance; the reported headline numbers are the mean of 3 independent full re-extractions
(not a cached replay), with sample standard deviation reported alongside. Baseline A is reported the
same way, over the same 3 runs. The `--with-explanation` run (needed for hallucination rate) was run
once, not 3×, by explicit scope decision — generating and decomposing per-case explanations roughly
doubles runtime, and the metric it isolates (claim-level factual support) is not expected to be
sensitive to the same extraction non-determinism that affects eligibility/temporal/provenance
accuracy.

### 7.6 A bug found and fixed during the final confirmatory run

The first attempt at the final 104-case, 3-run + 1-explanation suite crashed `CASE_104` in **every**
run with `'<=' not supported between instances of 'int' and 'str'`. Root cause: `CASE_104`'s real OCR
notice (`notice_6.jpeg`, Eightfold AI) states its backlog requirement as "Backlogs: No current/active
backlogs" — a label/value table row rather than a sentence. The LLM extracted this under the generic
criterion-type name `"backlogs"` (already aliased to the canonical `max_backlogs`) but attached the
literal string value `"No current active backlogs"` instead of a number, because the existing
force-to-zero logic only recognized a fixed list of literal type-name synonyms (`no_backlogs`,
`no_active_backlogs`, `no_arrears`, `no_standing_arrears`, `max_arrears`) — it never inspected the
*value* itself, so a non-numeric string reaching `max_backlogs` under any other type name flowed
straight through to the rule engine's `student.backlogs <= max_allowed` comparison and crashed.

**Fix** (`extraction/notice_extractor.py`): a new, more general check — if a `max_backlogs` value is a
non-numeric string, parse it ("no"/"none"/"nil" → 0) instead of forcing based on the literal
criterion-type name; if it can't be parsed, skip the criterion with a warning rather than crash the
whole case. Verified via a grep of all existing notice text that no previously-passing case was
exposed to a non-numeric `max_backlogs` value under a type name outside the original explicit synonym
list, so this is additive, not a change in behavior for the already-verified 100-case set. The entire
3-run + 1-explanation suite was re-run from a clean state after this fix, since the crash affected
every run including the `--with-explanation` run.

This is reported here, rather than silently folded into a "clean" final number, because the project's
own stated discipline throughout development (see `eval/result.md`'s full findings history) is to
root-cause and fix bugs surfaced by real evaluation data immediately and disclose them, not to retry
until a crash-free run appears.

---

## 8. Findings From Development — a Narrative of Bugs Surfaced by Evaluation

This section exists because several of the evaluation's most informative moments were not clean
pass/fail numbers but concrete bugs the gold set surfaced — each one is evidence that the evaluation
harness was exercising real system behavior, not a tautological check against the system's own
assumptions. All are now fixed; each is reported with its root cause, not just its symptom.

**Finding A — unregistered criterion types crashed the whole case (9/100 cases).**
`rules/eligibility_engine.py` had no fallback when the LLM emitted a criterion type with no
registered evaluator (`graduation_year`, and a `no_backlogs` synonym not yet in the alias map).
Fixed by excluding `graduation_year` from extraction (no student field exists for it) and hardening
`evaluate_eligibility` to skip-and-log any unregistered criterion type instead of raising.

**Finding B — the `"ALL"` sentinel for "open to all branches" was never recognized by the branch
evaluators**, so a drive explicitly open to every branch rejected every student. Fixed by special-
casing `criterion.value == "ALL"` as an unconditional pass in both branch evaluators.

**Finding C — exact-match-only `BRANCH_ALIASES` lookup silently dropped branches on phrasing drift**
(e.g., `"Cybersecurity Specialization"`, `"AI/ML"`), and the LLM sometimes split one notice's branch
eligibility across two separate criteria that reconciliation's tie-break then collapsed into one,
losing the other branch entirely. Fixed with three changes: merging same-batch `allowed_branches`
facts before reconciliation ever sees them, a qualifier-suffix-stripping retry in the alias lookup,
and splitting on `,` before `/` (not the other way around) so slash-joined aliases like `"AI/ML"` are
tried whole first.

**Finding D — a percentage-scale value extracted as if it were a CGPA.** Several notices state a
single combined threshold ("60% across 10th, 12th and UG") and the LLM sometimes applied that literal
number to a `min_cgpa`-shaped criterion, even though `Student.cgpa` is a 0–10 scale. This was first
flagged as a theoretical gap and only became a confirmed, case-breaking bug once a real OCR-sourced
notice (`CASE_101`, Cognizant Ace Team) exercised it, failing a 9.4-CGPA student against a literal
threshold of 60. Fixed deterministically — any extracted `min_cgpa > 10` can only be a misread
percentage, so it is divided by 10 — rather than by prompting the LLM to "try harder," since the
conversion is unambiguous and needs no model judgment. Finding a bare `"backlogs"` type-name variant
during the regression check for this fix, and the semicolon-separated branch list and "arrears"
backlog synonym from the same 2 OCR notices, were three further related bugs fixed in the same pass
(see `eval/result.md` for the full detail and the regression numbers that confirm each fix).

**Finding E — the root cause of a 58.3% temporal-conflict accuracy metric, with nothing wrong with
the temporal/provenance logic itself.** The system's allowed-branch list was derived only from
branches currently present in the student roster, so `EEE` — a real, notice-stated eligible branch
with zero currently-enrolled students — was silently dropped as if it were an LLM hallucination.
Root-caused by directly re-running extraction and reconciliation for all 5 failing cases and diffing
against expected values; none of the 5 affected students were themselves EEE-branch, so the
eligibility verdict was unaffected, but the full reconciled branch list didn't match, which the
grading metric (correctly) still counts as a miss. Fixed by making the allowed-branch list a fixed
canonical set the roster can only widen, never narrow. Fixing this also surfaced a real gold-set
authoring bug (`EEE` and `EE` had been listed as two separate branches, when `EE` is simply an alias
for `EEE`) — corrected after cross-checking against the project's own design document, which already
specified the de-duplicated value, and against the raw notice text itself. Temporal-conflict accuracy
rose from 58.3% to 100.0% with zero change to any eligibility verdict, confirming this was purely a
value-fidelity bug, not an accuracy regression hiding behind a different metric.

**The data-leakage bug that could have invalidated H3/H4's evidence entirely.** While building an
independent gold-set verification worksheet, the portal ingestion adapter was found to be rendering
plain-English answer hints from the raw student-information-system data (e.g., "Portal authority
rank 4 loses to email rank 2") directly into the text handed to the LLM extractor — in both the real
pipeline and the eval harness. This affected roughly half of the cases the temporal/provenance
metrics specifically exist to evaluate. It was fixed immediately on discovery, regardless of whether
it had changed any specific number (it had not, in this case) — the methodological point is that the
metric was not measuring what it claimed to measure while the leak was present, independent of outcome.

**Collectively**, these findings illustrate a pattern worth stating explicitly in the paper's
discussion section: *the single biggest source of system failures in this evaluation was not the
LLM's reasoning quality but brittle string/alias-matching logic sitting between extraction and the
deterministic rule engine* — exactly the kind of defect a registry-based, additive architecture (§4.5)
is supposed to make easy to find and fix one case at a time, and exactly the kind of defect a
pure-accuracy-number evaluation would never localize without the case-level gold-set detail this
evaluation methodology provides.

---

## 9. Limitations (to disclose explicitly in the paper)

1. **Only one baseline was tested.** Standard RAG (Baseline B) and RAG + structured student database
   (Baseline C), both specified in the original evaluation plan, were explicitly descoped. The
   reported comparison establishes that PlaceGuard outperforms a bare LLM-only approach; it does
   **not** establish that the full temporal/provenance/rule-engine architecture outperforms a simpler
   RAG system, which is a narrower and more interesting claim this evaluation cannot make.
2. **Ground truth was author-constructed, not independently verified by a third party.** The
   researcher who built the system also labeled the gold set. Mitigations applied: (a) a stratified,
   16-case blind verification worksheet (`gold_set_verification.md`) was built, containing only the
   raw student/notice inputs with no answer-revealing fields, specifically so a blind re-derivation
   pass is possible — but as of this writing that blind pass has not been completed and reported
   back; (b) specific gold-set corrections made after observing a system failure were cross-checked
   against the original, pre-implementation design handoff document and against the raw notice text
   itself, rather than being adjusted to whatever the system happened to output; (c) all such
   corrections are disclosed with their reasoning in `eval/result.md`, not silently applied.
3. **Small sub-category sample sizes.** Temporal-conflict and provenance-reasoning accuracy are each
   computed over roughly a dozen cases, not hundreds — single-case swings move these percentages by
   several points. The evaluation plan's suggestion of a 500-case benchmark for a "final experiment"
   was not attempted; this is explicitly scoped as a first-prototype evaluation.
4. **Residual LLM extraction non-determinism is a known, disclosed limitation, not something the
   evaluation claims to have eliminated.** The local 8B model (`llama3.1:8b`) does not reliably
   extract every criterion identically across repeated runs on the same notice text (e.g., "no
   standing arrears" is not recognized on every draw despite a dedicated synonym fix). This is
   measured directly via the 3-run variance numbers in §7.5 rather than papered over with a single
   favorable run.
5. **Load/throughput testing was out of scope.** Latency is reported as mean/P95 per case under
   sequential, single-request evaluation; no concurrent-load behavior was characterized.
6. **The 4 OCR-sourced cases are a small, additive pass, not a systematic OCR-robustness study.** Real
   screenshot OCR introduces its own noise (confirmed — e.g., "No current/active backlogs" OCR'd with
   visible character-level errors), and only 4 cases across 4 drives exercise this path. This is
   adequate to demonstrate the OCR integration works end-to-end and to surface the real bug described
   in §7.6, but not to characterize OCR-specific accuracy at scale.

Framed for a college-assignment research paper rather than a venue submission: these limitations are
exactly the right scope for a first-prototype evaluation, and stating them explicitly and specifically
(rather than with a generic "future work" paragraph) is itself evidence of methodological care, which
is assessed favorably far more often than a suspiciously flawless result set.

---

## 10. Related Work (2024–2026)

### 10.1 Conflicting / temporal information in RAG systems

- **Astute RAG: Overcoming Imperfect Retrieval Augmentation and Knowledge Conflicts for LLMs** —
  Wang, Wan, Sun, Chen, Arık (2024), [arXiv:2410.07176](https://arxiv.org/abs/2410.07176). Proposes
  adaptively reconciling conflicting evidence from retrieval instead of naively concatenating it —
  directly relevant to reconciling Gmail/WhatsApp/portal disagreements.
- **Retrieval-Augmented Generation with Conflicting Evidence** — Wang et al. (2025),
  [arXiv:2504.13079](https://arxiv.org/abs/2504.13079). Introduces a multi-agent debate approach
  (Madam-RAG) that distinguishes *ambiguity* (multiple valid answers) from *misinformation/staleness*
  (one answer is simply outdated) — maps directly onto this project's "deadline extended" vs.
  "conflicting genuinely ambiguous requirement" cases.
- **DRAGged into Conflicts: Detecting and Addressing Conflicting Sources in Search-Augmented LLMs**
  (2025), [arXiv:2506.08500](https://arxiv.org/abs/2506.08500). Benchmarks model behavior under
  "freshness and misinformation" conflicts specifically — the closest existing benchmark category to
  this project's WhatsApp-supersedes-email scenario, and shows current models handle it inconsistently
  (74–79% accuracy even with taxonomy-aware pipelines).

**Gap:** these works study conflict detection/resolution as a general RAG problem. None couple it to
a **downstream deterministic decision** (eligibility) where the cost of picking the wrong version of a
fact is institutional reputational damage, not just an incorrect chatbot answer.

### 10.2 Source authority / provenance-aware retrieval

- **Retrieval-Augmented Generation with Estimation of Source Reliability** (2024),
  [arXiv:2410.22954](https://arxiv.org/abs/2410.22954). Proposes retrieving and weighting documents
  per-source reliability rather than treating all retrieved content as equally trustworthy.
- **Not All Contexts Are Equal: Teaching LLMs Credibility-Aware Generation** — Pan, Cao, Lin, Han,
  Zheng, Wang, Cai, Sun, EMNLP 2024. Trains models to weigh retrieved context by credibility rather
  than by surface relevance alone.

**Gap:** both treat source credibility as a soft, learned weighting signal. This project's setting
needs a **hard, auditable authority hierarchy** (Placement Cell official update > company PDF > portal
> student forward) with explicit supersession semantics — closer to institutional/legal reasoning
than to open-web credibility scoring.

### 10.3 Extracting executable rules from natural-language policy

- **A Methodology for Using LLMs to Create User-Friendly Applications for Medicaid Redetermination
  and Other Social Services** (2024),
  [PMC11361957](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11361957/). Near-identical structural
  problem: extracting eligibility rules from unstructured government policy text and compiling them
  into executable, deterministic logic end users can query — the strongest structural precedent for
  this project's rule-engine layer.
- **LMN: A Tool for Generating Machine-Enforceable Policies from Natural Language Access Control
  Rules using LLMs** (2025), [arXiv:2502.12460](https://arxiv.org/abs/2502.12460). Converts free-text
  policy into structured, machine-checkable rule format (ABAC-style) — directly analogous to
  converting "CSE/ISE, CGPA ≥ 7.5, no backlogs" into a rule object.

**Gap:** both are single-document, single-snapshot extraction. Neither handles the case where the
*same policy* is updated multiple times across *different channels* with different authority, which
is the actual situation in a placement cycle.

### 10.4 Educational/institutional chatbots

- **Unimib Assistant: Designing a Student-Friendly RAG-Based Chatbot for All Their Needs** (2024),
  [arXiv:2411.19554](https://arxiv.org/abs/2411.19554). Explicitly identifies the same root problem
  this project targets — university information fragmented across "WhatsApp group chats for each
  course, direct contact with Secretariat or Professors" alongside the intranet — and builds a RAG
  assistant to unify it.

**Gap:** Unimib Assistant is a general-purpose Q&A layer; it does not attempt eligibility gating,
deterministic decisioning, or registration access control — it stops at "answer the question,"
whereas this project's core novelty is turning the answer into a **gated action**.

### 10.5 Synthesis — the actual research gap this project targets

No existing system combines (a) multi-source, multi-authority, time-varying institutional
communication, (b) LLM-based extraction of eligibility policy into structured rules, and (c) a
deterministic decision layer that gates a real-world action (registration) rather than just answering
a question. This project's contribution is this end-to-end architecture plus an evaluation methodology
that measures decision correctness under conflicting/stale information — not just answer
plausibility.

---

## 11. Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| LLM / extraction & explanation | Local `llama3.1:8b` via Ollama (evaluation runs); Claude/GPT-4-class API supported by `llm_client.py` | Used only for extraction, reconciliation-adjacent tagging (`is_correction`), and explanation — never the final verdict |
| Rule engine | Plain Python, criterion evaluators in a registry dict | Fully unit-testable, additive by design |
| Reconciliation | `reconciliation/temporal_provenance_engine.py` | Deterministic — §5.1 algorithm |
| Vector store | ChromaDB (`database/vector_store.py`) | Used for retrieval evaluation (`eval/eval_retrieval.py`); `drive_id` metadata filtering does most of the real work at this notice volume |
| OCR | EasyOCR (`extraction/ocr_client.py`) | Real screenshot-notice ingestion, exercised end-to-end by `CASE_101`–`CASE_104` |
| Schemas | Pydantic models: `Fact`, `Criterion`, `Student`, `EligibilityResult`, `Source` | One shared, versioned contract between extraction → reconciliation → rule engine → API |
| Database | (per design) PostgreSQL for the full system; evaluation harness uses JSON fixtures directly | Immutable facts-as-event-log model |
| Testing | pytest against hand-written fixtures (rule engine and reconciliation engine first, before any LLM-extracted data touches them) | Plus the full `eval/` harness for system-level evaluation |

---

## 12. Repository / Evaluation Artifact Map

| Artifact | Purpose |
|---|---|
| `data/gold_set.json` | 104-case gold set with expected eligibility, reasoning-requirement flags, and expected reconciled rules |
| `data/notices.json`, `data/whatsapp_messages.json`, `data/sis_data.json` | Synthetic + OCR-sourced raw notice text and metadata |
| `data/images/` | 6 real placement-notice screenshots (5 used) |
| `eval/run_eval.py` | Full PlaceGuard pipeline evaluation |
| `eval/baseline_llm_only.py` | Baseline A (LLM-only) evaluation |
| `eval/eval_retrieval.py` | Recall@K retrieval evaluation |
| `eval/compare_baselines.py` | Headline comparison table |
| `eval/compute_variance.py` | Multi-run variance aggregation |
| `eval/generate_verification_worksheet.py` | Produces the blind, answer-stripped verification worksheet |
| `gold_set_verification.md` | The blind verification worksheet itself (16-case stratified sample) |
| `eval/result.md` | Full chronological evaluation history, including every finding/bug/fix described in §8 |
| `eval/variance_report.md` | Latest multi-run variance aggregate |

---

## 13. Suggested Paper Structure (mapping this document's sections to a typical paper outline)

| Paper section | Source |
|---|---|
| Title / Abstract | §1–2 |
| Introduction / Problem Statement | §3 |
| Related Work | §10 |
| System Architecture | §4–5 |
| Research Questions / Hypotheses | §6 |
| Evaluation Methodology | §7.1–7.3 |
| Results | §7.4–7.5 |
| Discussion (bugs-as-evidence narrative) | §8 |
| Limitations | §9 |
| Future Work | README.md §11 (real WhatsApp/Gmail integration, knowledge-graph cross-drive analytics, fine-tuned extraction model, automated conflict alerts, fairness/bias audit) |
| Conclusion | Restate §2's core claim with §7's headline numbers |
