# PlaceGuard — Faculty Presentation Notes

### A Temporal- and Provenance-Aware GenAI Framework for Placement Information Management and Eligibility Verification

---

## 1. The Problem, in One Paragraph

College placement information arrives scattered across Gmail, WhatsApp, and a rarely-updated
student portal, with no single source of truth and no timestamp-based reconciliation between
channels. Registration links get forwarded to the entire student body **before** eligibility
(CGPA, backlogs, branch, prior offers, academic percentage) is actually verified. Ineligible
students register, sit the online assessment, and companies can — and do — blacklist the
institution over it. This is not a UI problem; it is a **decision-integrity** problem.

## 2. The Core Design Principle

> **GenAI extracts and explains. A deterministic rule engine decides.**

The LLM is never asked *"is this student eligible?"* It is only ever asked *"what does this
notice say?"* and *"explain this already-computed decision in plain language."* The actual
ELIGIBLE / INELIGIBLE / UNKNOWN verdict is computed by ordinary, testable, deterministic Python —
not by an LLM's judgment call. This is the single idea the whole system is built around, and it's
the answer to give if asked "why not just use ChatGPT for this?"

Three states, not two, matters: if a student's CGPA or backlog count is missing from the record,
the system says **UNKNOWN** rather than silently assuming a value. Guessing in either direction
(assume pass, assume fail) is unsafe when the downstream consequence is a company blacklisting the
college.

## 3. End-to-End Pipeline

```
 Gmail inbox        Mock WhatsApp console       SIS / portal feed
(real OAuth,      (console simulating the        (JSON feed standing
 placement cell     Placement Cell / student       in for the student
 sender only)       WhatsApp group)                portal, not yet
      │                    │                       API-accessible)
      │                    │                              │
      └───────────┬────────┴───────────┬──────────────────┘
                   ▼                    ▼
         ┌────────────────────────────────────────┐
         │   INGESTION ADAPTERS (per-channel)       │
         │   normalize into one RawMessage shape:    │
         │   {source_type, sender_role, timestamp,   │
         │    body, authority_rank}                  │
         └───────────────────┬────────────────────────┘
                              ▼
         ┌────────────────────────────────────────┐
         │   LLM EXTRACTION LAYER                   │
         │   notice text → structured Fact rows:    │
         │   {criterion_type, operator, value,       │
         │    confidence, is_correction}             │
         │   Low-confidence extractions are held      │
         │   back for review instead of auto-applied  │
         └───────────────────┬────────────────────────┘
                              ▼
         ┌────────────────────────────────────────┐
         │   TEMPORAL + PROVENANCE RECONCILIATION    │
         │   groups facts by (drive, criterion,      │
         │   scope); picks the winner by:            │
         │     1. highest source authority           │
         │     2. explicit correction language        │
         │     3. most recent timestamp (tie-break)   │
         └───────────────────┬────────────────────────┘
                              ▼
         ┌────────────────────────────────────────┐
         │   DETERMINISTIC RULE ENGINE               │
         │   every criterion is checked against the  │
         │   student record → ELIGIBLE / INELIGIBLE / │
         │   UNKNOWN (never a forced guess)           │
         └───────────────────┬────────────────────────┘
                              ▼
         ┌────────────────────────────────────────┐
         │   EVIDENCE-GROUNDED EXPLANATION (LLM)     │
         │   turns the already-decided verdict +     │
         │   per-criterion evidence into plain        │
         │   language, citing source + timestamp      │
         └───────────────────┬────────────────────────┘
                              ▼
          Student dashboard (status + explanation,         Placement-cell
          registration link gated to ELIGIBLE only)         analytics dashboard
```

### Worked example

A student asks *"Am I eligible for this drive?"* and the system doesn't just say yes/no — it
shows the full evidence trail:

| Requirement | Student record | Status |
|---|---|---|
| CGPA ≥ 7.5 | 8.72 | ✅ PASS |
| Branch: CSE/ISE | CSE | ✅ PASS |
| Active backlogs = 0 | 0 | ✅ PASS |
| No existing offer | None | ✅ PASS |

*Source: Official Placement Cell WhatsApp update, 6:00 PM — supersedes the earlier 12:30 PM
version that had a different deadline.*

If a later, higher-authority message changes a condition, the system re-reconciles and the
dashboard reflects the change — it never keeps serving a stale answer.

## 4. Why Reconciliation Is the Hard Part (the actual research contribution)

Three properties make this different from "just add a database":

1. **Different sources carry different authority.** An official company PDF should always beat a
   placement-cell WhatsApp message, which should always beat a student's forward of an old
   message — *even if the student's forward is the most recent message in the group.* Naive
   "most recent wins" retrieval gets this wrong.
2. **The same fact changes over time**, and different channels can be stale simultaneously (e.g.
   the student portal often lags real-time WhatsApp/email updates by days).
3. **Corrections are explicit** ("Correction: CGPA is 7.0, not 7.5") and must be detected and
   applied even when they come from the *same* authority level as the thing they're correcting.

The reconciliation engine encodes exactly this: **authority rank first, explicit correction
second, recency only as the final tie-break** — never recency alone.

## 5. Technology Stack

| Layer | Technology | Why |
|---|---|---|
| Backend API | **FastAPI** (Python) | Async-capable, auto-generated OpenAPI docs, strong typing via Pydantic |
| Data validation / schemas | **Pydantic v2** (`pydantic-settings` for config) | Every object passed between pipeline stages (RawMessage, Criterion, EligibilityResult) is a validated schema, not a loose dict |
| ORM / database | **SQLAlchemy 2.0** (SQLite for dev, swappable to PostgreSQL/MySQL for production) | `Fact` table is append-only/immutable by design — an audit log, never UPDATEd or DELETEd |
| LLM orchestration | **LangChain** (`ChatOllama`, `ChatGoogleGenerativeAI`) | One abstraction over multiple interchangeable providers |
| LLM providers | **Ollama (local, `llama3.1:8b`)** for zero-cost/offline development; **Gemini** as a hosted alternative | Provider is a single config flag — the extraction/explanation code never changes |
| Vector store (traditional RAG) | **ChromaDB** (embedded, no server) + **sentence-transformers** (`all-MiniLM-L6-v2`) | Semantic retrieval layer that narrows candidate facts during reconciliation — used only to *retrieve*, never to decide |
| Email ingestion | **Gmail API** (OAuth2, `google-api-python-client`) | Real channel adapter, scoped to the placement-cell sender only |
| WhatsApp ingestion | **Mock WhatsApp console** (drop-in replacement for the WhatsApp Business Cloud API) | Same `RawMessage` contract as the real API — swapping the adapter later needs no pipeline changes |
| Portal ingestion | JSON-backed adapter standing in for the SIS portal | Portal data goes through the *same* extraction pipeline as email/WhatsApp — no special-cased parsing |
| Auth | **JWT** (`python-jose`), role-separated student/admin | Registration gating is enforced server-side, not hidden in the UI |
| Frontend | **Next.js 14 + React 18 + TypeScript + Tailwind CSS** | Student dashboard (status, explanation, gated registration) + placement-cell view (drive timeline, eligibility breakdown) |
| Testing | **pytest** | Deterministic rule engine and evaluators are fully unit-tested in isolation from the LLM |

## 6. The Three-Layer Safety Argument (what to say if asked "how do you prevent hallucination?")

PlaceGuard does **not** rely on prompting the model with "don't hallucinate." It relies on
architecture:

1. **Confidence filtering at extraction** — every extracted criterion carries a confidence level
   (`high`/`medium`/`low`); anything below a configurable threshold is held back for manual review
   instead of silently becoming a rule a real student is judged against.
2. **The rule engine cannot be talked out of a decision** — `evaluate_eligibility()` is plain
   Python control flow over structured `Criterion` objects. There is no prompt in this function;
   an LLM output never reaches it directly, only after extraction + reconciliation have produced
   a structured fact.
3. **Explanations are generated *after* the decision, from the decision** — the explanation
   prompt is given the already-computed per-criterion PASS/FAIL/UNKNOWN results and instructed to
   explain only from that evidence, never to re-derive or override it.

## 7. Evaluation Methodology

The project includes a dedicated evaluation plan (`PlaceGuard_Evaluation_Plan.md`) comparing four
system variants on the same benchmark of labelled test cases:

| System | What it does |
|---|---|
| Baseline A — LLM-only | LLM receives the notice + student info directly and outputs the verdict — no retrieval, no rules |
| Baseline B — Standard RAG | Vector retrieval over notices feeds an LLM that outputs the verdict — no authority/temporal reasoning |
| Baseline C — RAG + structured DB | Adds structured student records to Baseline B — still no deterministic decision layer |
| **PlaceGuard** | Temporal + provenance-aware reconciliation → deterministic rule engine → evidence-grounded explanation |

Metrics measured: **eligibility accuracy**, **macro-F1** across the three states, **temporal
conflict resolution accuracy**, **provenance/source attribution accuracy**, **hallucination
rate** (unsupported claims in generated explanations), **UNKNOWN-detection accuracy** (does the
system correctly refuse to guess when data is missing), **retrieval Recall@K**, and **latency**.
The benchmark is built from real placement-cell email patterns (sampled read-only from the actual
inbox to learn authentic phrasing) combined into fictional test drives/students, covering email,
WhatsApp, and SIS-portal channels individually and in cross-channel conflict.

## 8. What To Demo Live

1. **Mock WhatsApp console**: post an official notice, then post a correction with a changed
   CGPA cutoff — show the dashboard update to the corrected value, citing the correction message
   as the source.
2. **A forwarded-stale-notice case**: have a "student" forward the *original, superseded* notice
   after the correction — show the system still reports the corrected value, not the forward,
   because authority (not recency) governs.
3. **A missing-data case**: a student with no backlog count on record — show the system reports
   `UNKNOWN`, not a guessed pass/fail.
4. **The gated registration flow**: an ineligible student does not get the registration link —
   they get a cited, per-criterion explanation of exactly which requirement they failed instead.
5. **The placement-cell dashboard**: eligible/registered/rejected counts and the reconciliation
   trace for a drive with conflicting sources.

## 9. One-Sentence Summary (for the abstract slide)

> PlaceGuard uses generative AI only where it is safe to use — extracting structured eligibility
> criteria from messy, multi-channel, time-varying placement communication and explaining
> decisions in plain language — while keeping the actual eligibility verdict deterministic,
> auditable, and provably never influenced by a hallucination, because the cost of getting it
> wrong is not a bad chatbot answer, it's a company blacklisting the college.
