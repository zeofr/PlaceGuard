# Implementation Plan

## Overview

This plan implements all 24 code-quality fixes for the PlaceGuard codebase using the bug condition methodology. Tasks follow the six-step migration/rollout order from the design document: (1) non-breaking no-risk changes, (2) schema additions, (3) logic fixes, (4) security fixes, (5) structural changes, (6) frontend changes, with a final testing step covering unit, property-based, and integration tests for each category.

## Task Dependency Graph

```json
{
  "waves": [
    {
      "wave": 1,
      "tasks": ["1", "2", "3"],
      "description": "Step 1 — Non-breaking no-risk changes (dead imports, annotations, init files, whitespace, next.config rename)"
    },
    {
      "wave": 2,
      "tasks": ["4", "5", "6"],
      "description": "Step 2 — Schema additions (EligibilityResult fields, SourceType enum members)"
    },
    {
      "wave": 3,
      "tasks": ["7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23"],
      "description": "Steps 3–6 — Logic fixes, security fixes, structural changes, frontend changes (parallel after wave 2)"
    },
    {
      "wave": 4,
      "tasks": ["24", "25", "26", "27", "28", "29", "30", "31"],
      "description": "Step 7 — Unit, property-based, and integration tests + final checkpoint"
    }
  ]
}
```

- Steps 1–2 must be applied before Step 3 (logic fixes depend on schema additions in Step 2).
- Step 4 (security) and Step 5 (structural) can be applied in parallel with Step 3 once Step 2 is done.
- Step 6 (frontend) is independent of all backend steps and can proceed in parallel.
- Step 7 tests are written incrementally alongside each step; the checkpoint validates all steps together.

## Tasks

<!-- Bug Condition Methodology
  C(X)   = isBugCondition — a code path that produces incorrect or unsafe output
  P(r)   = expectedBehavior — the desired correct outcome when C holds
  ¬C(X)  = non-buggy inputs whose behavior must be bit-identically preserved
-->

---

## Step 1 — Non-breaking, no-risk changes

These changes have zero runtime-behavior impact and can be merged immediately in a single PR.
They cover defects: **1.7, 1.8, 1.10, 1.11, 1.13, 1.14, 1.20, 1.23**

- [ ] 1. Write bug condition exploration test for dead-code and annotation defects
  - **Property 1: Bug Condition** - Dead imports and legacy annotation defects (1.7, 1.8, 1.10, 1.11, 1.13, 1.14, 1.20, 1.23)
  - **CRITICAL**: This test MUST FAIL (or surface the condition) on unfixed code — failure/detection confirms the bugs exist
  - **DO NOT attempt to fix the test or the code when it fails**
  - **GOAL**: Surface counterexamples that demonstrate each defect exists
  - **Scoped PBT Approach**: These are deterministic static-analysis defects; scope the property to concrete detection checks
  - Defect 1.7: Import `List` from `typing` in `database/crud.py` and assert it does NOT appear — expect detection on unfixed code
  - Defect 1.8: Inspect `core/schemas.py`; assert `_USN_PATTERN` module-level constant EXISTS — expect `AttributeError`/`False` on unfixed code
  - Defect 1.10: Inspect `api/routes/eligibility.py` import block; assert `get_student` is NOT imported — expect detection on unfixed code
  - Defect 1.11: Inspect `eval/run_eval.py`; assert `get_db_context` and bare `crud` are NOT imported — expect detection on unfixed code
  - Defect 1.13: Assert `ingestion/__init__.py` has a non-empty docstring — expect empty on unfixed code
  - Defect 1.14: Assert `scripts/__init__.py` EXISTS — expect `FileNotFoundError` on unfixed code
  - Defect 1.20: Assert no triple-space alignment in `frontend/src/app/drive/[driveId]/page.tsx` `useState` declarations — expect detection on unfixed code
  - Defect 1.23: Assert `frontend/next.config.ts` EXISTS (and `next.config.js` does NOT) — expect detection on unfixed code
  - Run checks on UNFIXED code
  - **EXPECTED OUTCOME**: All checks detect the defect (confirms bugs exist)
  - Document counterexamples found
  - Mark task complete when checks are written, run, and detections are documented
  - _Requirements: 2.7, 2.8, 2.10, 2.11, 2.13, 2.14, 2.20, 2.23_

- [ ] 2. Write preservation property tests for step-1 scope (BEFORE implementing fix)
  - **Property 2: Preservation** - Runtime behavior unchanged for all non-defective inputs after step-1 changes
  - **IMPORTANT**: Follow observation-first methodology
  - Observe: importing `crud.py` still returns correct student/drive/fact lists on unfixed code
  - Observe: USN validation (`validate_usn`) accepts valid USNs and rejects invalid ones on unfixed code
  - Write property-based test: for all valid USN strings matching `^1MS\d{2}[A-Z]{2,4}\d{2,4}$`, `Student(usn=v)` succeeds after fix; for all invalid strings it raises `ValueError`
  - Write unit test: importing `eligibility.py` and `run_eval.py` completes without `ImportError` after dead imports removed
  - Write test: `ingestion` package import still works and `help(ingestion)` produces non-empty output after docstring added
  - Write test: `scripts` package import works after `__init__.py` created
  - Verify all tests PASS on UNFIXED code (confirms baseline)
  - _Requirements: 3.11, 3.4, 3.3_

- [ ] 3. Apply step-1 non-breaking fixes

  - [ ] 3.1 Fix legacy `typing.List` annotation in `database/crud.py` (defect 1.7)
    - Remove `from typing import List` import line
    - Replace all `List[Student]`, `List[Drive]`, `List[Fact]`, `List[Registration]` return-type annotations with `list[Student]`, `list[Drive]`, `list[Fact]`, `list[Registration]`
    - Affected functions: `get_students`, `search_students`, `get_drives`, `get_facts_by_drive`, `get_facts_by_rule_key`, `get_fact_by_source`, `get_registrations_by_student`, `get_registrations_by_drive`
    - _Bug_Condition: isBugCondition_4_7 — import_source == "typing" AND symbol == "List"_
    - _Expected_Behavior: built-in list[] generic used consistently (PEP 585)_
    - _Preservation: All CRUD functions continue returning the same data; mypy now clean_
    - _Requirements: 2.7_

  - [ ] 3.2 Pre-compile USN regex in `core/schemas.py` (defect 1.8)
    - Add module-level constant `_USN_PATTERN = re.compile(r"^1MS\d{2}[A-Z]{2,4}\d{2,4}$")` before the `Student` class definition
    - In `validate_usn`, replace `re.match(pattern, v.upper())` with `_USN_PATTERN.match(v.upper())`
    - Remove the local `pattern = ...` variable inside the validator
    - _Bug_Condition: isBugCondition_4_8 — compilation_point == "inside_field_validator" AND not_module_level_constant == True_
    - _Expected_Behavior: pattern compiled once at import time_
    - _Preservation: validate_usn accepts/rejects exactly the same USN strings as before_
    - _Requirements: 2.8_

  - [ ] 3.3 Remove dead `get_student` import from `api/routes/eligibility.py` (defect 1.10)
    - Remove `get_student` from the `from database.crud import (...)` block
    - Verify no other usage of `get_student` exists in the file before removing
    - _Bug_Condition: isBugCondition_4_10 — import_name == "get_student" AND used_in_module == False_
    - _Expected_Behavior: import block only contains used symbols_
    - _Preservation: All eligibility route handlers continue to work; student obtained via get_current_student dependency_
    - _Requirements: 2.10_

  - [ ] 3.4 Remove dead imports from `eval/run_eval.py` (defect 1.11)
    - Remove `from database.connection import get_db_context`
    - Remove `from database import crud` (bare module import, never used in module body)
    - Keep `from database import init_db` — this is intentional for dev/test seeding
    - _Bug_Condition: isBugCondition_4_11 — import_name IN ["get_db_context", "crud"] AND used_in_module == False_
    - _Expected_Behavior: only used imports remain_
    - _Preservation: eval harness continues to run and print accuracy/F1/latency metrics_
    - _Requirements: 2.11, 3.11_

  - [ ] 3.5 Add docstring to `ingestion/__init__.py` (defect 1.13)
    - Replace empty file content with a module docstring describing the package's purpose
    - Docstring must describe: source adapters, mock_email adapter, coordinator orchestration, `RawMessage` normalization
    - _Bug_Condition: isBugCondition_6_13 — package == "ingestion" AND __init___content == ""_
    - _Expected_Behavior: __init__.py has non-empty docstring consistent with other packages_
    - _Preservation: `import ingestion` continues to work; no public API changed_
    - _Requirements: 2.13_

  - [ ] 3.6 Create `scripts/__init__.py` (defect 1.14)
    - Create new file `scripts/__init__.py` with a module docstring describing the scripts package
    - Docstring must note: not part of application runtime, intended for developer/operator use, documents `migrate_dev.py`
    - _Bug_Condition: isBugCondition_6_14 — directory == "scripts" AND __init___exists == False_
    - _Expected_Behavior: scripts/ is a proper Python package with __init__.py_
    - _Preservation: `migrate_dev.py` continues to run as before_
    - _Requirements: 2.14_

  - [ ] 3.7 Fix whitespace alignment in `frontend/src/app/drive/[driveId]/page.tsx` (defect 1.20)
    - Remove triple-space alignment padding from all `useState` declarations
    - Replace multi-space `=` alignment with single space: `const [x, setX] = useState(...)`
    - Affected lines: `timeline`, `eligibility`, `timelineLoading`, `eligLoading`, `error` state declarations
    - _Bug_Condition: isBugCondition_8_20 — multiple_spaces_used_for_alignment == True AND project_uses_prettier == True_
    - _Expected_Behavior: single space around = consistent with Prettier config_
    - _Preservation: No functional change; state variables work identically_
    - _Requirements: 2.20_

  - [ ] 3.8 Rename `frontend/next.config.js` to `frontend/next.config.ts` (defect 1.23)
    - Rename the file from `next.config.js` to `next.config.ts`
    - Add `import type { NextConfig } from "next"` at the top
    - Annotate the config object: `const nextConfig: NextConfig = { ... }`
    - Use `export default nextConfig` (ESM default export)
    - Verify `frontend/package.json` scripts do not hardcode `next.config.js` (Next.js 14 auto-discovers `next.config.ts`)
    - _Bug_Condition: isBugCondition_8_23 — config_extension == ".js" AND project_is_typescript_first == True_
    - _Expected_Behavior: next.config.ts with typed NextConfig import, consistent with tailwind.config.ts_
    - _Preservation: Rewrite rules (API proxy) continue to function identically_
    - _Requirements: 2.23_

  - [ ] 3.9 Verify step-1 exploration test now passes
    - **Property 1: Expected Behavior** - Dead imports and annotation defects resolved
    - **IMPORTANT**: Re-run the SAME checks from task 1 — do NOT write new tests
    - All static-analysis checks from task 1 must now detect NO defects
    - **EXPECTED OUTCOME**: All checks PASS (confirms step-1 fixes are correct)
    - _Requirements: 2.7, 2.8, 2.10, 2.11, 2.13, 2.14, 2.20, 2.23_

  - [ ] 3.10 Verify step-1 preservation tests still pass
    - **Property 2: Preservation** - Runtime behavior unchanged after step-1 fixes
    - **IMPORTANT**: Re-run the SAME tests from task 2 — do NOT write new tests
    - **EXPECTED OUTCOME**: All preservation tests PASS (confirms no regressions)

---

## Step 2 — Schema additions (additive, backward-compatible)

These changes add optional fields and new enum members; they are purely additive and non-breaking.
They cover defects: **1.9, 1.12 (schema side)**

- [ ] 4. Write bug condition exploration test for schema defects
  - **Property 1: Bug Condition** - Missing EligibilityResult fields and missing SourceType enum members (1.9, schema side of 1.12)
  - **CRITICAL**: Tests MUST FAIL on unfixed code
  - **GOAL**: Confirm missing fields cause AttributeError and missing enum members cause KeyError
  - Defect 1.9: Construct `EligibilityResult(student_id="x", drive_id="y", status=EligibilityStatus.ELIGIBLE, criterion_results=[])` and access `.explanation` — expect `AttributeError` on unfixed code
  - Defect 1.9: Access `.summary` on the same instance — expect `AttributeError` on unfixed code
  - Schema side of 1.12: Assert `SourceType.COORDINATOR_EMAIL` exists — expect `AttributeError` on unfixed code
  - Schema side of 1.12: Assert `SourceType.STUDENT_EMAIL` exists — expect `AttributeError` on unfixed code
  - Schema side of 1.12: Assert `SOURCE_AUTHORITY_RANK[SourceType.COORDINATOR_EMAIL]` exists — expect `KeyError` on unfixed code
  - Schema side of 1.12: Assert `SOURCE_AUTHORITY_RANK[SourceType.STUDENT_EMAIL]` exists — expect `KeyError` on unfixed code
  - Run on UNFIXED code; **EXPECTED OUTCOME**: Exceptions raised (confirms bugs exist)
  - Document counterexamples; mark complete when documented
  - _Requirements: 2.9, 2.12_

- [ ] 5. Write preservation property tests for schema additions (BEFORE implementing fix)
  - **Property 2: Preservation** - Existing SourceType members and EligibilityResult fields survive additive changes
  - **IMPORTANT**: Follow observation-first methodology on UNFIXED code
  - Observe: all existing `SourceType` members serialize/deserialize correctly; record values
  - Observe: `EligibilityResult` round-trip via `model_dump(mode="json")` / `model_validate` preserves all current fields
  - Write property-based test: for all existing `SourceType` members, `SOURCE_AUTHORITY_RANK` contains an entry and rank value is unchanged after fix
  - Write unit test: `set(SourceType) == set(SOURCE_AUTHORITY_RANK.keys())` — assert completeness holds after additions
  - Write property-based test: random `EligibilityResult` instances with all current fields round-trip without `ValidationError`
  - Verify all tests PASS on UNFIXED code (confirms baseline)
  - _Requirements: 3.5, 3.3, 3.4_

- [ ] 6. Apply step-2 schema additions

  - [ ] 6.1 Add `explanation` and `summary` fields to `EligibilityResult` in `core/schemas.py` (defect 1.9)
    - Add `explanation: str | None = None` field to the `EligibilityResult` Pydantic model
    - Add `summary: str | None = None` field to the `EligibilityResult` Pydantic model
    - Place new fields after `criterion_results` to maintain JSON serialization order
    - _Bug_Condition: isBugCondition_4_9 — field_access IN ["explanation", "summary"] AND field_declared_in_schema == False_
    - _Expected_Behavior: EligibilityResult.explanation and .summary are declared optional fields, no AttributeError_
    - _Preservation: All existing EligibilityResult fields (student_id, drive_id, status, criterion_results) unchanged; model_dump round-trip still works_
    - _Requirements: 2.9, 3.3, 3.4_

  - [ ] 6.2 Add `COORDINATOR_EMAIL` and `STUDENT_EMAIL` to `SourceType` enum in `core/schemas.py` (schema side of defect 1.12)
    - Add `COORDINATOR_EMAIL = "coordinator_email"` to the `SourceType` enum after `COORDINATOR_WHATSAPP`
    - Add `STUDENT_EMAIL = "student_email"` to the `SourceType` enum after `STUDENT_WHATSAPP`
    - Add `SourceType.COORDINATOR_EMAIL: 3` to `SOURCE_AUTHORITY_RANK` dict (same rank as COORDINATOR_WHATSAPP)
    - Add `SourceType.STUDENT_EMAIL: 5` to `SOURCE_AUTHORITY_RANK` dict (same rank as STUDENT_WHATSAPP)
    - _Bug_Condition: isBugCondition_5_12 — sender_role COORDINATOR assigned COORDINATOR_WHATSAPP; sender_role STUDENT assigned STUDENT_WHATSAPP_
    - _Expected_Behavior: COORDINATOR_EMAIL and STUDENT_EMAIL enum members exist with correct authority ranks_
    - _Preservation: All existing SourceType members and their ranks are unchanged; reconciliation engine continues to select higher-authority facts_
    - _Requirements: 2.12, 3.5_

  - [ ] 6.3 Verify step-2 exploration test now passes
    - **Property 1: Expected Behavior** - EligibilityResult fields and SourceType enum members present
    - **IMPORTANT**: Re-run the SAME checks from task 4 — do NOT write new tests
    - **EXPECTED OUTCOME**: All assertions PASS (no AttributeError or KeyError)
    - _Requirements: 2.9, 2.12_

  - [ ] 6.4 Verify step-2 preservation tests still pass
    - **Property 2: Preservation** - Existing schema members unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 5 — do NOT write new tests
    - **EXPECTED OUTCOME**: All preservation tests PASS; SOURCE_AUTHORITY_RANK completeness test passes

---

## Step 3 — Logic fixes (test-gated)

These changes alter observable behavior and must be gated on the full test suite.
They cover defects: **1.1, 1.2, 1.3, 1.6, 1.12 (adapter side), 1.16**

- [ ] 7. Write bug condition exploration test for logic defects
  - **Property 1: Bug Condition** - LLM temperature cross-contamination, lambda aliases, branch normalization divergence, email SourceType mismatch, bare except swallowing (1.1, 1.2, 1.3, 1.6, 1.12, 1.16)
  - **CRITICAL**: Tests MUST FAIL on unfixed code — failure confirms the bugs exist
  - **DO NOT fix the code or the test when it fails**
  - **GOAL**: Surface concrete counterexamples for each logic defect
  - Defects 1.1, 1.2 — Temperature isolation: with `settings.gemini_temperature=0.9` and `settings.openai_temperature=None` / `settings.claude_temperature=None`, call `get_llm_client("openai")` and `get_llm_client("claude")`; capture the `temperature` passed to each model constructor; assert it is NOT `0.9` — expect both to use `0.9` (gemini's value) on unfixed code, demonstrating the cross-contamination
  - Defect 1.3 — Lambda aliases: `import inspect; assert inspect.isfunction(GeminiClient)` — expect `AssertionError` on unfixed code (lambda is not a def function)
  - Defect 1.6 — Branch normalization: call `evaluate_branch(Criterion(criterion_type="branch", value="cse"), Student(branch="CSE", ...))` and assert result.status == Status.PASS — expect `FAIL` on unfixed code
  - Defect 1.12 (adapter): call `MockEmailAdapter._infer_source_type(SenderRole.COORDINATOR)` and assert result == `SourceType.COORDINATOR_EMAIL` — expect `SourceType.COORDINATOR_WHATSAPP` on unfixed code
  - Defect 1.12 (adapter): call `MockEmailAdapter._infer_source_type(SenderRole.STUDENT)` and assert result == `SourceType.STUDENT_EMAIL` — expect `SourceType.STUDENT_WHATSAPP` on unfixed code
  - Defect 1.16 — Bare except: mock `create_registration` to raise `sqlalchemy.exc.OperationalError`; call the eligibility check endpoint; assert HTTP 500 is returned — expect HTTP 200 (silently swallowed) on unfixed code
  - Run on UNFIXED code; **EXPECTED OUTCOME**: All assertions fail/detect defects
  - Document counterexamples (e.g., "openai uses gemini_temperature=0.9 instead of openai_temperature")
  - Mark complete when run and failures documented
  - _Requirements: 2.1, 2.2, 2.3, 2.6, 2.12, 2.16_

- [ ] 8. Write preservation property tests for logic fixes (BEFORE implementing fix)
  - **Property 2: Preservation** - Gemini path, allowed_branches evaluator, placement cell email, IntegrityError handling all unchanged
  - **IMPORTANT**: Follow observation-first methodology on UNFIXED code
  - Observe: `get_llm_client("gemini")` with `settings.gemini_temperature=0.1`; record `default_temperature` of returned `LangChainClient`
  - Write unit test: Gemini path still uses `gemini_temperature` unchanged after provider-specific fix
  - Observe: `evaluate_allowed_branches(Criterion(value=["CSE","ISE"]), Student(branch="CSE"))` returns `PASS` on unfixed code
  - Write property-based test (Hypothesis): for all `criterion_type="allowed_branches"` inputs, result of `evaluate_branch == evaluate_allowed_branches` after fix — generate random branch lists and student branches
  - Observe: `MockEmailAdapter._infer_source_type(SenderRole.PLACEMENT_CELL)` returns `PLACEMENT_CELL_EMAIL` on unfixed code
  - Write unit test: placement cell email mapping unchanged after fix
  - Observe: `create_registration` raising `IntegrityError` is silently handled; registration endpoint returns success on unfixed code
  - Write unit test: `IntegrityError` continues to be silently swallowed (idempotent re-registration) after narrowing fix
  - Verify all tests PASS on UNFIXED code
  - _Requirements: 3.9, 3.10, 3.2, 3.3_

- [ ] 9. Fix LLM temperature cross-contamination and lambda aliases

  - [ ] 9.1 Add `openai_temperature` and `claude_temperature` settings to `config.py` (defects 1.1, 1.2)
    - In the `Settings` class, add `openai_temperature: float | None = None` after `openai_model`
    - Add `claude_temperature: float | None = None` after `claude_model`
    - Add inline comments: `# falls back to gemini_temperature if None`
    - _Bug_Condition: isBugCondition_1_1 / isBugCondition_1_2 — provider-specific temperature fields do not exist_
    - _Expected_Behavior: opt-in per-provider temperature fields added without breaking existing .env files_
    - _Requirements: 2.1, 2.2_

  - [ ] 9.2 Fix OpenAI temperature in `extraction/llm_client.py` (defect 1.1)
    - In the `elif provider == "openai":` block, replace the hardcoded `settings.gemini_temperature` with a local variable `_openai_temp`
    - Compute: `_openai_temp = settings.openai_temperature if settings.openai_temperature is not None else settings.gemini_temperature`
    - Pass `temperature=_openai_temp` to `ChatOpenAI` constructor
    - Pass `default_temperature=_openai_temp` to `LangChainClient` constructor
    - _Bug_Condition: isBugCondition_1_1 — provider == "openai" AND setting_used == "gemini_temperature"_
    - _Expected_Behavior: openai_temperature used; falls back to gemini_temperature only if None_
    - _Preservation: Gemini path untouched; OpenAI path continues to construct LangChainClient_
    - _Requirements: 2.1, 3.9_

  - [ ] 9.3 Fix Claude temperature in `extraction/llm_client.py` (defect 1.2)
    - In the `elif provider == "claude":` block, replace the hardcoded `settings.gemini_temperature` with a local variable `_claude_temp`
    - Compute: `_claude_temp = settings.claude_temperature if settings.claude_temperature is not None else settings.gemini_temperature`
    - Pass `temperature=_claude_temp` to `ChatAnthropic` constructor
    - Pass `default_temperature=_claude_temp` to `LangChainClient` constructor
    - _Bug_Condition: isBugCondition_1_2 — provider == "claude" AND setting_used == "gemini_temperature"_
    - _Expected_Behavior: claude_temperature used; falls back to gemini_temperature only if None_
    - _Preservation: Gemini path untouched; Claude path continues to construct LangChainClient_
    - _Requirements: 2.2, 3.9_

  - [ ] 9.4 Replace lambda convenience aliases with named functions in `extraction/llm_client.py` (defect 1.3)
    - Remove the three lambda assignments: `GeminiClient = lambda: ...`, `OpenAIClient = lambda: ...`, `ClaudeClient = lambda: ...`
    - Add three named function definitions with docstrings and explicit `-> LLMClient` return type annotations:
      - `def get_gemini_client() -> LLMClient:` — returns `get_llm_client("gemini")`
      - `def get_openai_client() -> LLMClient:` — returns `get_llm_client("openai")`
      - `def get_claude_client() -> LLMClient:` — returns `get_llm_client("claude")`
    - Update any import sites that reference `GeminiClient`, `OpenAIClient`, or `ClaudeClient` by the old lambda names (grep the codebase first)
    - _Bug_Condition: isBugCondition_1_3 — alias_type == "lambda_assignment"_
    - _Expected_Behavior: named def functions; flake8 E731 zero violations; mypy infers LLMClient return type_
    - _Preservation: Calling get_gemini_client() / get_openai_client() / get_claude_client() returns the same LangChainClient as before_
    - _Requirements: 2.3_

- [ ] 10. Fix shared branch normalization helper

  - [ ] 10.1 Extract `_normalize_branch_list` into `rules/evaluators/allowed_branches.py` (defect 1.6)
    - At the top of `rules/evaluators/allowed_branches.py`, define the shared helper function:
      ```python
      def _normalize_branch_list(raw: object) -> list[str]:
          if isinstance(raw, list):
              return [str(b).strip().upper() for b in raw]
          if isinstance(raw, str):
              return [b.strip().upper() for b in raw.split(",")]
          return [str(raw).strip().upper()]
      ```
    - Replace the existing inline normalization block inside `evaluate_allowed_branches` with a call to `_normalize_branch_list(criterion.value)`
    - _Bug_Condition: isBugCondition_3_6 — criterion_type == "branch" AND branch_value_type IN ["string", "mixed_case"] AND normalization logic duplicated/diverged_
    - _Expected_Behavior: single implementation in allowed_branches.py used by both evaluators_
    - _Requirements: 2.6, 3.10_

  - [ ] 10.2 Import and use `_normalize_branch_list` in `rules/evaluators/branch.py` (defect 1.6)
    - Add `from rules.evaluators.allowed_branches import _normalize_branch_list` import
    - In `evaluate_branch`, replace the direct `student.branch in allowed_branches` comparison with:
      - `allowed_branches = _normalize_branch_list(criterion.value)`
      - `student_branch = student.branch.strip().upper()`
      - `passed = student_branch in allowed_branches`
    - _Bug_Condition: isBugCondition_3_6 — branch.py does NOT normalize; allowed_branches.py does — logic diverged_
    - _Expected_Behavior: evaluate_branch produces PASS for ("cse", "CSE"), PASS for ("CSE,ISE", "CSE"), consistent with evaluate_allowed_branches_
    - _Preservation: evaluate_allowed_branches continues to return PASS for CSE in ["CSE","ISE"], FAIL for MECH_
    - _Requirements: 2.6, 3.10_

- [ ] 11. Fix email adapter SourceType mapping in `ingestion/mock_email/adapter.py` (defect 1.12)
  - In `_infer_source_type`, replace `return SourceType.COORDINATOR_WHATSAPP` with `return SourceType.COORDINATOR_EMAIL`
  - Replace `return SourceType.STUDENT_WHATSAPP` (in the student-role branch) with `return SourceType.STUDENT_EMAIL`
  - Remove the misleading inline comments `# Using WhatsApp type for coordinators` and `# Using WhatsApp type for students`
  - Ensure `SourceType.COORDINATOR_EMAIL` and `SourceType.STUDENT_EMAIL` are imported (added in step-2 task 6.2)
  - _Bug_Condition: isBugCondition_5_12 — sender_role == COORDINATOR AND assigned_source_type == COORDINATOR_WHATSAPP_
  - _Expected_Behavior: coordinator email → COORDINATOR_EMAIL; student email → STUDENT_EMAIL_
  - _Preservation: PLACEMENT_CELL sender role continues to map to PLACEMENT_CELL_EMAIL; authority ranks unchanged_
  - _Requirements: 2.12, 3.2, 3.5_

- [ ] 12. Narrow bare `except Exception` to `IntegrityError` in `api/routes/eligibility.py` (defect 1.16)
  - Add `from sqlalchemy.exc import IntegrityError` to the imports in `api/routes/eligibility.py`
  - In the `create_registration` call site, replace `except Exception: pass` with `except IntegrityError: db.rollback()`
  - Add inline comment: `# unique constraint hit — student already registered; safe to continue`
  - _Bug_Condition: isBugCondition_7_16 — exception_caught == "Exception" AND exception_type IN ["OperationalError", "ConnectionError", "TimeoutError"]_
  - _Expected_Behavior: IntegrityError silently handled (idempotent); OperationalError and other DB errors re-raise_
  - _Preservation: IntegrityError path continues to return already_registered=True; existing happy-path registration flow unchanged_
  - _Requirements: 2.16, 3.3_

- [ ] 13. Verify step-3 exploration test now passes
  - **Property 1: Expected Behavior** - All logic defects resolved
  - **IMPORTANT**: Re-run the SAME checks from task 7 — do NOT write new tests
  - Temperature assertions: openai uses openai_temperature (not gemini), claude uses claude_temperature (not gemini)
  - Lambda assertion: `inspect.isfunction(get_gemini_client)` → True
  - Branch assertion: `evaluate_branch(value="cse", student.branch="CSE")` → PASS
  - Email adapter assertions: COORDINATOR → COORDINATOR_EMAIL, STUDENT → STUDENT_EMAIL
  - OperationalError assertion: eligibility endpoint returns HTTP 500 (not silently swallowed)
  - **EXPECTED OUTCOME**: All assertions PASS (confirms all logic bugs fixed)
  - _Requirements: 2.1, 2.2, 2.3, 2.6, 2.12, 2.16_

- [ ] 14. Verify step-3 preservation tests still pass
  - **Property 2: Preservation** - Gemini path, allowed_branches, placement cell email, IntegrityError handling all unchanged
  - **IMPORTANT**: Re-run the SAME tests from task 8 — do NOT write new tests
  - Property-based test: for all allowed_branches inputs, evaluate_branch == evaluate_allowed_branches
  - **EXPECTED OUTCOME**: All preservation tests PASS (confirms no regressions)

---

## Step 4 — Security fixes

These changes require environment variable changes before deployment.
They cover defects: **1.4, 1.5**

> **Pre-deploy action (defect 1.4):** Set `JWT_SECRET` to a strong random value in all deployment environments BEFORE deploying the code change. Reversing this order will crash the server on startup.

- [ ] 15. Write bug condition exploration test for security defects
  - **Property 1: Bug Condition** - Hardcoded JWT fallback secret and raw str(e) leak (1.4, 1.5)
  - **CRITICAL**: Tests MUST demonstrate the security gap on unfixed code
  - **GOAL**: Confirm the defects exist before fixing
  - Defect 1.4: Unset `JWT_SECRET` env var; call `validate_settings()` directly; assert it raises `ValueError` — expect NO exception (silent pass) on unfixed code
  - Defect 1.5: Mock the LLM client to raise `RuntimeError("Invalid API key: sk-proj-SECRETVALUE")`; POST `/ingest/notice`; assert the response body's `detail` field does NOT contain `"sk-proj-SECRETVALUE"` — expect the secret to appear in the detail on unfixed code
  - Run on UNFIXED code; **EXPECTED OUTCOME**: Defects detected (validates security gaps exist)
  - Document counterexamples: "validate_settings() returns None without JWT_SECRET", "HTTP 500 detail contains API key fragment"
  - Mark complete when documented
  - _Requirements: 2.4, 2.5_

- [ ] 16. Write preservation property tests for security fixes (BEFORE implementing fix)
  - **Property 2: Preservation** - JWT auth and valid ingestion continue to work when settings are correct
  - **IMPORTANT**: Follow observation-first methodology on UNFIXED code
  - Observe: with `JWT_SECRET` set to a valid value, `validate_settings()` completes without exception on unfixed code
  - Write unit test: `validate_settings()` does NOT raise when a strong `JWT_SECRET` is set (non-default, non-empty value)
  - Observe: with a valid notice and valid API key, POST `/ingest/notice` returns HTTP 200 with correct counts on unfixed code
  - Write unit test: valid ingestion continues to return `success=True` with `facts_extracted` > 0 after generic error message change
  - Verify both tests PASS on UNFIXED code
  - _Requirements: 3.1, 3.2, 3.9_

- [ ] 17. Apply step-4 security fixes

  - [ ] 17.1 Add JWT secret startup validation to `config.py` (defect 1.4)
    - In `validate_settings()`, add a check before the return statement:
      ```python
      if settings.jwt_secret == "CHANGE_THIS_IN_PRODUCTION":
          raise ValueError(
              "JWT_SECRET is using the insecure default value. "
              "Set a strong random secret in the JWT_SECRET environment variable "
              "before starting the server."
          )
      ```
    - Ensure `validate_settings()` is wired into the application lifespan (verified in step-5 task 18.1)
    - _Bug_Condition: isBugCondition_2_4 — jwt_secret_env_set == False AND app_starts_without_error == True_
    - _Expected_Behavior: ValueError raised at startup when JWT_SECRET is the insecure default; server refuses to start_
    - _Preservation: validate_settings() completes successfully when JWT_SECRET is a proper random secret_
    - _Requirements: 2.4, 3.1_

  - [ ] 17.2 Replace `str(e)` leak with generic HTTP 500 message in `api/routes/ingestion.py` (defect 1.5)
    - In the `POST /ingest/notice` route handler's outer `except Exception as e` block:
      - Remove `detail=f"Failed to ingest notice: {str(e)}"`
      - Add `import logging` (or use module-level logger) and call `logger.exception("Notice ingestion error")` to log the full traceback server-side
      - Replace the `detail` with the generic string `"Notice ingestion failed. Please try again."`
    - The `except` clause signature can drop the `as e` binding since `e` is no longer used in the detail
    - _Bug_Condition: isBugCondition_2_5 — exception_detail CONTAINS internal_path_or_key_name AND exception_detail == str(original_exception)_
    - _Expected_Behavior: HTTP 500 detail is always the generic string; full traceback logged server-side_
    - _Preservation: Valid ingestion requests continue to return HTTP 200 with correct fact counts_
    - _Requirements: 2.5, 3.2_

  - [ ] 17.3 Verify step-4 exploration test now passes
    - **Property 1: Expected Behavior** - JWT startup raises on weak secret; HTTP 500 returns generic message
    - **IMPORTANT**: Re-run the SAME checks from task 15 — do NOT write new tests
    - **EXPECTED OUTCOME**: `validate_settings()` raises `ValueError` when JWT_SECRET is default; response detail is generic string
    - _Requirements: 2.4, 2.5_

  - [ ] 17.4 Verify step-4 preservation tests still pass
    - **Property 2: Preservation** - Auth and valid ingestion unaffected by security fixes
    - **IMPORTANT**: Re-run the SAME tests from task 16 — do NOT write new tests
    - **EXPECTED OUTCOME**: All preservation tests PASS

---

## Step 5 — Structural changes

These changes require a smoke test after deployment.
They cover defects: **1.15, 1.17**

- [ ] 18. Write bug condition exploration test for structural defects
  - **Property 1: Bug Condition** - `init_db` runs unconditionally in production and deprecated lifecycle decorator (1.15, 1.17)
  - **CRITICAL**: Tests MUST detect the structural defects on unfixed code
  - Defect 1.15: Set `settings.debug = False`; call the startup handler; assert `Base.metadata.create_all` is NOT called — expect it IS called on unfixed code (no debug guard)
  - Defect 1.17: Inspect `api/main.py` source; assert no `@app.on_event("startup")` decorator exists — expect it to exist on unfixed code; also assert the app uses a `lifespan` parameter — expect it NOT to exist on unfixed code
  - Run on UNFIXED code; **EXPECTED OUTCOME**: Defects detected
  - Document counterexamples: "`init_db()` called unconditionally", "`@app.on_event` decorator present"
  - Mark complete when documented
  - _Requirements: 2.15, 2.17_

- [ ] 19. Write preservation property tests for structural changes (BEFORE implementing fix)
  - **Property 2: Preservation** - App starts correctly and all routes respond after lifecycle refactor
  - **IMPORTANT**: Follow observation-first methodology on UNFIXED code
  - Observe: with `settings.debug = True`, `init_db()` is called during startup — record this as the expected behavior for debug mode
  - Write unit test: with `settings.debug = True`, `init_db()` IS called in lifespan startup
  - Write unit test: with `settings.debug = False`, `init_db()` is NOT called in lifespan startup
  - Observe: `GET /health` (or any route) returns HTTP 200 after startup on unfixed code
  - Write integration test: after lifespan refactor, at least one route (e.g., `GET /drives`) responds with HTTP 200 or 401 (not 500)
  - Verify all tests PASS on UNFIXED code (debug=True path)
  - _Requirements: 3.1, 3.7_

- [ ] 20. Apply step-5 structural changes to `api/main.py` (defects 1.15, 1.17)

  - [ ] 20.1 Replace `@app.on_event("startup")` with `lifespan` context manager (defect 1.17)
    - Add `from contextlib import asynccontextmanager` import
    - Define an `async def lifespan(app: FastAPI)` function decorated with `@asynccontextmanager`
    - Move the body of the old `startup_event` into the `lifespan` function (before the `yield`)
    - Pass `lifespan=lifespan` to the `FastAPI(...)` constructor
    - Remove the `@app.on_event("startup")` decorator and the `startup_event` function
    - _Bug_Condition: isBugCondition_6_17 — decorator == "@app.on_event" AND fastapi_version >= "0.93"_
    - _Expected_Behavior: lifespan context manager used; zero DeprecationWarning for lifecycle events_
    - _Preservation: all startup logic (validate_settings, conditional init_db) still executes; routes still respond_
    - _Requirements: 2.17, 3.1_

  - [ ] 20.2 Guard `init_db()` with `settings.debug` in the lifespan (defect 1.15)
    - Inside the lifespan's startup block (before `yield`), wrap the `init_db()` call:
      ```python
      if settings.debug:
          init_db()
      ```
    - Ensure `validate_settings()` is called unconditionally (before the `if settings.debug` guard)
    - _Bug_Condition: isBugCondition_6_15 — environment == "production" AND init_db_called_on_startup == True AND alembic_migrations_active == True_
    - _Expected_Behavior: init_db() only called when settings.debug is True; production uses Alembic exclusively_
    - _Preservation: debug/test environments continue to create tables via init_db(); alembic upgrade head succeeds cleanly in production_
    - _Requirements: 2.15_

  - [ ] 20.3 Verify step-5 exploration test now passes
    - **Property 1: Expected Behavior** - No deprecated decorator; init_db guarded by debug flag
    - **IMPORTANT**: Re-run the SAME checks from task 18 — do NOT write new tests
    - **EXPECTED OUTCOME**: No `@app.on_event` present; lifespan parameter used; `init_db` only called when debug=True
    - _Requirements: 2.15, 2.17_

  - [ ] 20.4 Verify step-5 preservation tests still pass
    - **Property 2: Preservation** - App starts and routes respond after structural change
    - **IMPORTANT**: Re-run the SAME tests from task 19 — do NOT write new tests
    - **EXPECTED OUTCOME**: All preservation tests PASS; smoke test `GET /drives` returns non-500

---

## Step 6 — Frontend changes

These changes are CI/CD gated.
They cover defects: **1.18, 1.19, 1.21, 1.22, 1.24**

- [ ] 21. Write bug condition exploration test for frontend defects
  - **Property 1: Bug Condition** - Hardcoded token key, missing useCallback, wrong prop type, unsafe driveId cast, missing label/input accessibility (1.18, 1.19, 1.21, 1.22, 1.24)
  - **CRITICAL**: Tests/checks MUST detect defects on unfixed code
  - **GOAL**: Confirm each frontend defect exists before fixing
  - Defect 1.18: Grep `frontend/src/lib/api.ts` for the string literal `"pg_token"` — expect it to appear (hardcoded) on unfixed code; assert it does NOT appear after fix
  - Defect 1.19: Grep `frontend/src/app/dashboard/page.tsx` for `eslint-disable` — expect it to appear on unfixed code; assert `useCallback` import is absent on unfixed code
  - Defect 1.21: Inspect `StatusBadge.tsx` prop type; assert `status` prop is declared as `Status` (the local union type) NOT `string` — expect `string` on unfixed code
  - Defect 1.22: Grep `frontend/src/app/drive/[driveId]/page.tsx` for `as string` cast on `params?.driveId` — expect it to appear on unfixed code
  - Defect 1.24: Inspect login page inputs; assert `id` attribute is present on both inputs; assert `htmlFor` is present on both labels — expect both missing on unfixed code
  - Run on UNFIXED code; **EXPECTED OUTCOME**: All defects detected
  - Document counterexamples; mark complete when documented
  - _Requirements: 2.18, 2.19, 2.21, 2.22, 2.24_

- [ ] 22. Write preservation property tests for frontend changes (BEFORE implementing fix)
  - **Property 2: Preservation** - Login flow, StatusBadge rendering, dashboard load, drive page all continue to work
  - **IMPORTANT**: Follow observation-first methodology on UNFIXED code
  - Observe: `StatusBadge` renders correct colour-coded badge for all six status values (`ELIGIBLE`, `INELIGIBLE`, `UNKNOWN`, `active`, `closed`, `cancelled`) on unfixed code
  - Write unit test: `StatusBadge` renders without crash for all six known status strings after prop type narrowing
  - Observe: login page submits `POST /auth/login` and redirects to `/dashboard` on unfixed code
  - Write unit test: login form renders with functional USN and date-of-birth inputs (regardless of label association)
  - Observe: dashboard page loads drives and renders the filter UI on unfixed code
  - Write unit test: dashboard page renders and `loadDrives` is called on mount after `useCallback` refactor
  - Verify all tests PASS on UNFIXED code
  - _Requirements: 3.12, 3.13, 3.7_

- [ ] 23. Apply step-6 frontend fixes

  - [ ] 23.1 Use `getToken()` in Axios interceptor in `frontend/src/lib/api.ts` (defect 1.18)
    - Add `import { getToken } from "@/lib/auth"` at the top of `api.ts`
    - In the Axios request interceptor, replace `localStorage.getItem("pg_token")` (and any surrounding `typeof window !== "undefined"` guard) with a call to `getToken()`
    - Verify `getToken()` in `auth.ts` already handles the SSR guard internally; if not, add the guard there
    - _Bug_Condition: isBugCondition_8_18 — token_key_location == "hardcoded_in_api_ts"_
    - _Expected_Behavior: interceptor calls getToken() from auth.ts; renaming TOKEN_KEY in auth.ts propagates automatically_
    - _Preservation: Axios interceptor continues to attach the Bearer token to authenticated requests_
    - _Requirements: 2.18, 3.12_

  - [ ] 23.2 Wrap `loadDrives` in `useCallback` in `frontend/src/app/dashboard/page.tsx` (defect 1.19)
    - Add `useCallback` to the React import: `import { useCallback, useEffect, useState } from "react"`
    - Convert `async function loadDrives()` into `const loadDrives = useCallback(async () => { ... }, [filter])`
    - Update the `useEffect` dependency array to `[loadDrives, router]` (no longer needs `isLoggedIn` check inline — call it in the effect body)
    - Remove the `// eslint-disable-line` suppression comment from the useEffect
    - _Bug_Condition: isBugCondition_8_19 — loadDrives_wrapped_in_useCallback == False AND eslint_disabled == True_
    - _Expected_Behavior: loadDrives wrapped in useCallback([filter]); useEffect properly declares all deps; zero eslint-disable suppressions_
    - _Preservation: Dashboard loads drives on mount; filter changes re-fetch the drive list_
    - _Requirements: 2.19, 3.7_

  - [ ] 23.3 Narrow `StatusBadge` prop type in `frontend/src/components/StatusBadge.tsx` (defect 1.21)
    - Change the component signature from `{ status: string }` to `{ status: Status }` where `Status` is the local union type already defined in the file
    - Verify the `Status` type covers all six values: `"ELIGIBLE" | "INELIGIBLE" | "UNKNOWN" | "active" | "closed" | "cancelled"` (or the actual values used in the codebase — confirm by checking all call sites)
    - _Bug_Condition: isBugCondition_8_21 — StatusBadge_status_prop_type == "string" AND local_Status_type_defined == True_
    - _Expected_Behavior: prop accepts Status union type; TypeScript flags callers passing unknown status strings at compile time_
    - _Preservation: StatusBadge continues to render the correct colour-coded badge for all six status values_
    - _Requirements: 2.21, 3.13_

  - [ ] 23.4 Fix unsafe `driveId` cast in `frontend/src/app/drive/[driveId]/page.tsx` (defect 1.22)
    - Replace `const driveId = params?.driveId as string` with a runtime guard:
      ```typescript
      const rawDriveId = params?.driveId;
      const driveId = typeof rawDriveId === "string" && rawDriveId ? rawDriveId : null;
      ```
    - Add a `useEffect` that redirects to `/dashboard` when `driveId` is null
    - Add an early return guard: `if (!driveId) return null;` to avoid rendering while redirect is in flight
    - Ensure `loadTimeline` and `handleCheckEligibility` only call the API when `driveId` is non-null (TypeScript type narrowing handles this after the guard)
    - _Bug_Condition: isBugCondition_8_22 — params?.driveId == undefined AND cast_to_string == True_
    - _Expected_Behavior: absent driveId redirects to /dashboard; no "undefined" string ever passed to getDriveTimeline_
    - _Preservation: Valid driveId navigation continues to load the drive page and timeline normally_
    - _Requirements: 2.22_

  - [ ] 23.5 Add `id`/`htmlFor` to login form in `frontend/src/app/login/page.tsx` (defect 1.24)
    - Add `id="usn"` to the USN `<input>` element
    - Add `htmlFor="usn"` to the USN `<label>` element
    - Add `id="dob"` to the date-of-birth `<input>` element
    - Add `htmlFor="dob"` to the date-of-birth `<label>` element
    - Verify no other form inputs in the login page are missing label associations
    - _Bug_Condition: isBugCondition_8_24 — htmlFor_present == False AND id_on_input_present == False_
    - _Expected_Behavior: each input has an id; each label has a matching htmlFor; WCAG 1.3.1 satisfied_
    - _Preservation: Login form continues to submit POST /auth/login and redirect to /dashboard on success_
    - _Requirements: 2.24, 3.12_

  - [ ] 23.6 Verify step-6 exploration test now passes
    - **Property 1: Expected Behavior** - All frontend defects resolved
    - **IMPORTANT**: Re-run the SAME checks from task 21 — do NOT write new tests
    - **EXPECTED OUTCOME**: No hardcoded "pg_token", no eslint-disable, Status prop type used, no `as string` cast, htmlFor/id present
    - _Requirements: 2.18, 2.19, 2.21, 2.22, 2.24_

  - [ ] 23.7 Verify step-6 preservation tests still pass
    - **Property 2: Preservation** - Login, StatusBadge, dashboard, drive page all work correctly
    - **IMPORTANT**: Re-run the SAME tests from task 22 — do NOT write new tests
    - **EXPECTED OUTCOME**: All preservation tests PASS; `yarn build` / TypeScript compile clean; ESLint 0 warnings

---

## Step 7 — Tests (unit, property-based, integration for each category)

- [ ] 24. Write unit tests for Category 1 — LLM Client Factory

  - [ ] 24.1 Unit tests for temperature isolation
    - Write `tests/test_llm_client.py::test_openai_uses_openai_temperature`: mock `ChatOpenAI`; assert constructor receives `temperature=settings.openai_temperature` when `openai_temperature` is set
    - Write `tests/test_llm_client.py::test_openai_falls_back_to_gemini_temperature`: assert `temperature=settings.gemini_temperature` when `openai_temperature is None`
    - Write `tests/test_llm_client.py::test_claude_uses_claude_temperature`: mock `ChatAnthropic`; assert `temperature=settings.claude_temperature` when set
    - Write `tests/test_llm_client.py::test_claude_falls_back_to_gemini_temperature`: assert fallback to `gemini_temperature`
    - Write `tests/test_llm_client.py::test_gemini_path_unchanged`: assert Gemini path still uses `gemini_temperature` unchanged
    - Write `tests/test_llm_client.py::test_convenience_functions_are_callable`: assert `get_gemini_client`, `get_openai_client`, `get_claude_client` are `def` functions (not lambdas); call each and assert returns `LLMClient` instance
    - _Requirements: 2.1, 2.2, 2.3, 3.9_

- [ ] 25. Write unit tests for Category 2 — Security

  - [ ] 25.1 Unit tests for JWT validation and generic HTTP 500
    - Write `tests/test_config.py::test_validate_settings_raises_on_weak_jwt_secret`: unset `JWT_SECRET` env var or set to `"CHANGE_THIS_IN_PRODUCTION"`; call `validate_settings()`; assert `ValueError` raised with message containing `"JWT_SECRET"`
    - Write `tests/test_config.py::test_validate_settings_passes_with_strong_secret`: set `JWT_SECRET` to a random 32-char string; assert `validate_settings()` does not raise
    - Write `tests/test_ingestion_route.py::test_500_returns_generic_message`: mock the LLM client to raise `RuntimeError("sk-proj-SECRET")`; POST `/ingest/notice`; assert response status 500; assert `response.json()["detail"] == "Notice ingestion failed. Please try again."`; assert `"sk-proj-SECRET"` does NOT appear in the response body
    - _Requirements: 2.4, 2.5_

- [ ] 26. Write unit + property-based tests for Category 3 — Branch Normalization

  - [ ] 26.1 Unit tests for branch evaluator normalization (defect 1.6)
    - Write `tests/test_branch_evaluators.py::test_branch_normalizes_lowercase`: `evaluate_branch(Criterion(value="cse"), Student(branch="CSE"))` → `PASS`
    - Write `tests/test_branch_evaluators.py::test_branch_normalizes_comma_string`: `evaluate_branch(Criterion(value="CSE,ISE"), Student(branch="ise"))` → `PASS`
    - Write `tests/test_branch_evaluators.py::test_branch_fail_for_non_member`: `evaluate_branch(Criterion(value=["CSE","ISE"]), Student(branch="MECH"))` → `FAIL`
    - Write `tests/test_branch_evaluators.py::test_allowed_branches_unchanged`: `evaluate_allowed_branches(Criterion(value=["CSE","ISE"]), Student(branch="CSE"))` → `PASS`; `branch="MECH"` → `FAIL`
    - _Requirements: 2.6, 3.10_

  - [ ] 26.2 Property-based test for branch evaluator consistency (Hypothesis)
    - Write `tests/test_branch_evaluators.py::test_branch_evaluators_consistent_for_all_inputs`: use Hypothesis strategies to generate `Criterion` with `criterion_type` in `["branch", "allowed_branches"]` and random `value` (list or string, mixed case); generate random `Student.branch`; assert `evaluate_branch` returns the same `CriterionResult.status` as `evaluate_allowed_branches` for all generated inputs
    - Use `@settings(max_examples=500)` for thorough coverage
    - _Requirements: 2.6, 3.10_

- [ ] 27. Write unit tests for Category 4 — Schema and Import fixes

  - [ ] 27.1 Unit test for EligibilityResult field round-trip (defect 1.9)
    - Write `tests/test_schemas.py::test_eligibility_result_explanation_field`: construct `EligibilityResult`; assert `.explanation` and `.summary` are accessible as `None`; set them to strings; assert `model_dump(mode="json")` includes both fields; assert `model_validate(data)` reconstructs them correctly
    - Write property-based test: generate random `EligibilityResult` instances with arbitrary `explanation` / `summary` strings; assert round-trip via `model_dump` / `model_validate` preserves values without `ValidationError`
    - _Requirements: 2.9_

  - [ ] 27.2 Unit tests for SourceType completeness (defects 1.12, schema additions)
    - Write `tests/test_schemas.py::test_source_authority_rank_completeness`: assert `set(SourceType) == set(SOURCE_AUTHORITY_RANK.keys())` — every SourceType member has a rank; no member is missing
    - Write `tests/test_schemas.py::test_coordinator_email_rank`: assert `SOURCE_AUTHORITY_RANK[SourceType.COORDINATOR_EMAIL] == 3`
    - Write `tests/test_schemas.py::test_student_email_rank`: assert `SOURCE_AUTHORITY_RANK[SourceType.STUDENT_EMAIL] == 5`
    - _Requirements: 2.12, 3.5_

- [ ] 28. Write unit tests for Category 5 — Email Adapter and Category 7 — Error Handling

  - [ ] 28.1 Unit tests for email adapter source type mapping (defect 1.12)
    - Write `tests/test_mock_email_adapter.py::test_coordinator_email_maps_to_coordinator_email_type`: `MockEmailAdapter._infer_source_type(SenderRole.COORDINATOR)` → `SourceType.COORDINATOR_EMAIL`
    - Write `tests/test_mock_email_adapter.py::test_student_email_maps_to_student_email_type`: `_infer_source_type(SenderRole.STUDENT)` → `SourceType.STUDENT_EMAIL`
    - Write `tests/test_mock_email_adapter.py::test_placement_cell_email_unchanged`: `_infer_source_type(SenderRole.PLACEMENT_CELL)` → `SourceType.PLACEMENT_CELL_EMAIL`
    - _Requirements: 2.12, 3.2, 3.5_

  - [ ] 28.2 Unit tests for narrow IntegrityError catch (defect 1.16)
    - Write `tests/test_eligibility_route.py::test_integrity_error_is_handled_silently`: mock `create_registration` to raise `IntegrityError`; POST `/eligibility/check`; assert response status 200 with `already_registered=True`
    - Write `tests/test_eligibility_route.py::test_operational_error_is_reraised`: mock `create_registration` to raise `OperationalError`; POST `/eligibility/check`; assert response status 500
    - _Requirements: 2.16, 3.3_

- [ ] 29. Write frontend unit tests

  - [ ] 29.1 Frontend unit tests for token key, useCallback, StatusBadge, accessibility
    - Write `api.test.ts`: mock `getToken` from `@/lib/auth`; make a test request through the Axios instance; assert `getToken` was called; assert `localStorage.getItem` was NOT called directly with `"pg_token"`
    - Write `DashboardPage.test.tsx`: render the component with a mocked `listDrives`; change the `filter` state; assert `loadDrives` is called again; assert no `eslint-disable` comment in source file
    - Write `StatusBadge.test.tsx`: TypeScript compile check — confirm `status="unknown_value"` produces a type error at compile time; assert all six valid status values render a badge
    - Write accessibility test for `login/page.tsx` using `@testing-library/jest-dom`: assert `getByLabelText("USN")` finds the USN input; assert `getByLabelText("Date of Birth")` finds the date input
    - _Requirements: 2.18, 2.19, 2.21, 2.24, 3.12, 3.13_

- [ ] 30. Write integration tests

  - [ ] 30.1 Full eligibility flow integration test
    - POST `/ingest/notice` with a valid notice payload → assert `success=True`, `facts_extracted > 0`, `criteria_reconciled >= 0`
    - POST `/eligibility/check` for an eligible student → assert `status=ELIGIBLE`, `registration_link` present, `Registration` row created in DB
    - POST `/eligibility/check` again for the same student/drive → assert `already_registered=True`, no duplicate `Registration` row
    - _Requirements: 3.2, 3.3_

  - [ ] 30.2 Ingest error propagation integration test
    - Mock LLM client to raise `RuntimeError("secret-key-value")`; POST `/ingest/notice`
    - Assert HTTP status 500
    - Assert `response.json()["detail"] == "Notice ingestion failed. Please try again."`
    - Assert `"secret-key-value"` does NOT appear anywhere in the response body
    - _Requirements: 2.5, 3.2_

  - [ ] 30.3 JWT startup guard integration test
    - Start the FastAPI app without `JWT_SECRET` env var (or with the default weak value)
    - Assert the lifespan startup raises `ValueError` before the app accepts requests
    - Start again with a strong `JWT_SECRET` → assert `GET /drives` returns 200 or 401 (not 500)
    - _Requirements: 2.4, 3.1_

  - [ ] 30.4 Coordinator email ingestion integration test
    - Feed a coordinator-role email through `MockEmailAdapter`
    - Assert the resulting `Fact` row in the DB has `source_type = "coordinator_email"`
    - Assert the authority rank used in reconciliation is 3
    - _Requirements: 2.12, 3.5_

---

## Checkpoint

- [ ] 31. Checkpoint — Ensure all tests pass
  - Run the full backend test suite: `pytest tests/ -v`
  - Run the frontend build and type check: `yarn --cwd frontend build` and `yarn --cwd frontend tsc --noEmit`
  - Run frontend linter: `yarn --cwd frontend lint` — assert 0 errors and 0 warnings
  - Run static analysis: `flake8 .` — assert zero E731 violations; `mypy --strict extraction/llm_client.py config.py database/crud.py core/schemas.py` — assert zero errors
  - Verify `SOURCE_AUTHORITY_RANK` completeness test passes
  - Verify property-based branch consistency test passes with `max_examples=500`
  - Verify all six `StatusBadge` status values render correctly
  - Confirm no `// eslint-disable` suppressions remain in `dashboard/page.tsx`
  - Confirm `next.config.ts` exists and `next.config.js` is deleted
  - Smoke test: start the backend with a properly configured `.env`; `GET /drives` returns 200; `POST /auth/login` returns a JWT
  - Ensure all tests pass; ask the user if any questions arise

## Notes

- All backend fixes are in Python (≥3.10); all frontend fixes are in TypeScript/Next.js 14.
- **Deployment order for defect 1.4 (JWT secret):** update the `JWT_SECRET` env var / secrets manager with a strong random value in ALL environments BEFORE deploying the Step 4 code change. Reversing this order will crash the server on startup.
- Property-based tests (Hypothesis) should run with `@settings(max_examples=500)` for thorough branch-normalization coverage.
- The `SOURCE_AUTHORITY_RANK` completeness assertion (`set(SourceType) == set(SOURCE_AUTHORITY_RANK.keys())`) should be added to CI to guard against future enum additions missing a rank entry.
- `next.config.js` must be deleted (not just renamed) after `next.config.ts` is created to avoid Next.js picking up both config files.
- Step-6 frontend changes require `yarn build` and `yarn tsc --noEmit` to pass as the primary correctness gate.
