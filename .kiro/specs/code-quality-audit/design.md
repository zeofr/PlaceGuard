# Code Quality Audit Bugfix Design

## Overview

PlaceGuard's codebase contains 24 accumulated code quality defects across its Python backend
and Next.js/TypeScript frontend. These defects range from silent semantic bugs (wrong
temperature values passed to LLM providers, wrong `SourceType` enum values in the mock email
adapter) and active security risks (hardcoded JWT fallback secret, raw `str(e)` leak in HTTP
500 responses), through structural weaknesses (duplicate branch-evaluator logic, bare `except
Exception` swallowing `IntegrityError`), to maintenance debt (dead imports, legacy type
annotations, deprecated FastAPI lifecycle hooks, mixed JS/TS config files, missing
accessibility attributes).

The fix strategy is surgical: each change targets exactly one defect, touches the minimum
number of lines, and is guarded by the preservation requirement that all existing integration
tests continue to pass. Fixes are grouped into eight categories that reflect shared subsystems
and can be applied in parallel by different engineers.

---

## Glossary

- **Bug_Condition (C)**: The predicate `isBugCondition(input)` — a function or code path that
  currently produces incorrect or unsafe output for the given input.
- **Property (P)**: `expectedBehavior(result)` — the desired correct outcome for any input
  where `C` holds.
- **Preservation**: All behaviors for inputs where `¬C` holds must be bit-for-bit identical
  before and after the fix.
- **`get_llm_client()`**: The factory in `extraction/llm_client.py` that instantiates a
  `LangChainClient` wrapping the chosen provider's `BaseChatModel`.
- **`isBugCondition`**: Pseudocode predicate used throughout this document to identify inputs
  that currently trigger a defect.
- **`EligibilityResult`**: Pydantic schema in `core/schemas.py` representing the output of the
  rule engine, serialized by the eligibility route and consumed by the explanation generator.
- **`SourceType`**: Enum in `core/schemas.py` mapping message channels to authority ranks used
  by the reconciliation engine.
- **`authority_rank`**: Integer from `SOURCE_AUTHORITY_RANK` dict; lower = higher authority.
  Coordinator email has rank 3; student WhatsApp has rank 5 — assigning a coordinator email to
  `COORDINATOR_WHATSAPP` does not change the rank value in the current dict, but the mismatch
  means the `source_type` string stored in `facts` and `extracted_criteria` tables is wrong,
  poisoning any audit query that filters by channel.

---

## Bug Details

### Bug Condition

The 24 defects can be grouped by a single meta-predicate: "the code path activates a known
wrong implementation."  Each sub-predicate is numbered to match the requirements document.

**Formal Specification (meta-predicate):**

```
FUNCTION isBugCondition(defect_id, input)
  RETURN defect_id IN ACTIVE_DEFECTS
         AND triggers(input, defect_id)
END FUNCTION
```

Individual sub-predicates are defined in the "Bug Details" sub-sections below.

---

### Category 1 — LLM Client Factory Cross-Provider Temperature + PEP 8 E731

**Files affected:** `extraction/llm_client.py`, `config.py`

**Sub-conditions:**

```
FUNCTION isBugCondition_1_1(provider, setting_used)
  // Defect 1.1: OpenAI branch uses gemini_temperature instead of openai_temperature
  RETURN provider == "openai"
         AND setting_used == "gemini_temperature"
END FUNCTION

FUNCTION isBugCondition_1_2(provider, setting_used)
  // Defect 1.2: Claude branch uses gemini_temperature instead of claude_temperature
  RETURN provider == "claude"
         AND setting_used == "gemini_temperature"
END FUNCTION

FUNCTION isBugCondition_1_3(alias_type)
  // Defect 1.3: Module-level convenience aliases are bare lambdas (PEP 8 E731)
  RETURN alias_type == "lambda_assignment"
         AND name IN ["GeminiClient", "OpenAIClient", "ClaudeClient"]
END FUNCTION
```

**Examples:**
- `OPENAI_TEMPERATURE=0.7` is set in `.env` but `ChatOpenAI` is constructed with
  `temperature=0.1` (Gemini's default) — the OpenAI call ignores the user's setting.
- `mypy` reports `error: Cannot infer type of lambda; assign to variable with explicit type`.
- `flake8` reports `E731 do not assign a lambda expression, use a def`.

---

### Category 2 — Security: Hardcoded JWT Fallback + `str(e)` Leak

**Files affected:** `config.py`, `api/routes/ingestion.py`

```
FUNCTION isBugCondition_2_4(jwt_secret_env_set)
  // Defect 1.4: App starts successfully with CHANGE_THIS_IN_PRODUCTION as signing key
  RETURN jwt_secret_env_set == False
         AND app_starts_without_error == True
END FUNCTION

FUNCTION isBugCondition_2_5(exception_detail)
  // Defect 1.5: Raw exception string appears in HTTP 500 response body
  RETURN exception_detail CONTAINS internal_path_or_key_name
         AND exception_detail == str(original_exception)
END FUNCTION
```

**Examples:**
- Developer deploys without `.env` → server signs tokens with `"CHANGE_THIS_IN_PRODUCTION"`.
  Any attacker who forks the repo can forge a valid JWT for any USN.
- LLM API key error propagates: `HTTPException(detail="Failed to ingest notice: Invalid API
  key: sk-proj-...")` leaks the partial key to the HTTP client.

---

### Category 3 — Duplicate Branch Evaluator Normalization

**Files affected:** `rules/evaluators/branch.py`, `rules/evaluators/allowed_branches.py`

```
FUNCTION isBugCondition_3_6(criterion_type, branch_value_type)
  // Defect 1.6: "branch" evaluator does NOT normalize string values or uppercase,
  //             while "allowed_branches" evaluator does — logic has diverged
  RETURN criterion_type == "branch"
         AND branch_value_type IN ["string", "mixed_case"]
         AND student_branch_uppercase != raw_branch_in_criterion
END FUNCTION
```

**Examples:**
- `criterion_type="branch"`, `value="cse"`, `student.branch="CSE"` →
  `branch.py` returns `FAIL` (no normalization), while `allowed_branches.py` returns `PASS`.
- Future change to normalize in one evaluator silently diverges from the other.

---

### Category 4 — Type Annotation Gaps

**Files affected:** `database/crud.py`, `core/schemas.py`, `explanation/generator.py`,
`api/routes/eligibility.py`, `eval/run_eval.py`

```
FUNCTION isBugCondition_4_7(import_source)
  // Defect 1.7: typing.List used instead of built-in list[]
  RETURN import_source == "typing" AND symbol == "List"
END FUNCTION

FUNCTION isBugCondition_4_8(compilation_point)
  // Defect 1.8: USN regex recompiled on every validation call
  RETURN compilation_point == "inside_field_validator"
         AND not_module_level_constant == True
END FUNCTION

FUNCTION isBugCondition_4_9(field_access)
  // Defect 1.9: EligibilityResult accessed for .explanation or .summary
  //             but those fields are not declared on the schema
  RETURN field_access IN ["explanation", "summary"]
         AND field_declared_in_schema == False
END FUNCTION

FUNCTION isBugCondition_4_10(import_name)
  // Defect 1.10: Dead import in eligibility.py
  RETURN import_name == "get_student" AND used_in_module == False
END FUNCTION

FUNCTION isBugCondition_4_11(import_name)
  // Defect 1.11: Dead imports in eval/run_eval.py
  RETURN import_name IN ["get_db_context", "crud"] AND used_in_module == False
END FUNCTION
```

**Examples:**
- `mypy --strict` on `crud.py` emits `error: Incompatible return value type (got
  "List[Student]", expected "list[Student]")` due to the legacy annotation.
- `EligibilityResult(student_id=...).explanation` raises `AttributeError` if the object is
  constructed via the Pydantic schema directly (no `.explanation` field declared).

---

### Category 5 — Wrong SourceType Mapping in Mock Email Adapter

**File affected:** `ingestion/mock_email/adapter.py`

```
FUNCTION isBugCondition_5_12(sender_role, assigned_source_type)
  RETURN sender_role == SenderRole.COORDINATOR
         AND assigned_source_type == SourceType.COORDINATOR_WHATSAPP
         // coordinator email should not be COORDINATOR_WHATSAPP

  OR sender_role == SenderRole.STUDENT
     AND assigned_source_type == SourceType.STUDENT_WHATSAPP
     // student email should not be STUDENT_WHATSAPP
END FUNCTION
```

**Examples:**
- Email from `coordinator@msrit.edu` is stored with `source_type = "coordinator_whatsapp"`.
  Audit queries filtering by `source_type LIKE '%email%'` return zero rows for this message.
- The authority rank is coincidentally correct (rank 3 for `COORDINATOR_WHATSAPP` and the
  would-be `COORDINATOR_EMAIL`), but the stored string violates the channel contract.

---

### Category 6 — Package Structure

**Files affected:** `ingestion/__init__.py`, `scripts/` (missing `__init__.py`),
`api/main.py`, `database/connection.py`

```
FUNCTION isBugCondition_6_13(package)
  RETURN package == "ingestion" AND __init___content == ""
END FUNCTION

FUNCTION isBugCondition_6_14(directory)
  RETURN directory == "scripts" AND __init___exists == False
END FUNCTION

FUNCTION isBugCondition_6_15(environment)
  RETURN environment == "production"
         AND init_db_called_on_startup == True
         AND alembic_migrations_active == True
END FUNCTION

FUNCTION isBugCondition_6_17(decorator)
  RETURN decorator == "@app.on_event" AND fastapi_version >= "0.93"
END FUNCTION
```

**Examples:**
- `python -c "import ingestion; help(ingestion)"` prints `<no description>` — inconsistent
  with every other package.
- Running `alembic upgrade head` after a restart that called `init_db()` can create tables
  with different constraints than what Alembic expects, causing migration failures.
- FastAPI ≥ 0.93 emits `DeprecationWarning: on_event is deprecated, use lifespan instead`.

---

### Category 7 — Error Handling

**File affected:** `api/routes/eligibility.py`

```
FUNCTION isBugCondition_7_16(exception_type)
  RETURN exception_caught == "Exception"  // bare catch
         AND exception_type IN ["OperationalError", "ConnectionError", "TimeoutError"]
         // non-IntegrityError exceptions are silently swallowed
END FUNCTION
```

**Examples:**
- Database connection drops mid-request → `create_registration` raises `OperationalError` →
  `except Exception: pass` swallows it → response returns `status=ELIGIBLE` with no
  `registration_link` and no indication that the registration was not persisted.

---

### Category 8 — Frontend Quality

**Files affected:** `frontend/src/lib/api.ts`, `frontend/src/app/dashboard/page.tsx`,
`frontend/src/app/drive/[driveId]/page.tsx`, `frontend/src/components/StatusBadge.tsx`,
`frontend/next.config.js`, `frontend/src/app/login/page.tsx`

```
FUNCTION isBugCondition_8_18(token_key_location)
  RETURN token_key_location == "hardcoded_in_api_ts"
         AND canonical_location == "TOKEN_KEY_in_auth_ts"
END FUNCTION

FUNCTION isBugCondition_8_19(callback_wrapped)
  RETURN loadDrives_wrapped_in_useCallback == False
         AND eslint_disabled == True  // lint suppressed instead of fixed
END FUNCTION

FUNCTION isBugCondition_8_20(whitespace_style)
  RETURN multiple_spaces_used_for_alignment == True
         AND project_uses_prettier == True
END FUNCTION

FUNCTION isBugCondition_8_21(prop_type)
  RETURN StatusBadge_status_prop_type == "string"
         AND local_Status_type_defined == True
         AND local_Status_type_used_as_prop == False
END FUNCTION

FUNCTION isBugCondition_8_22(params_value)
  RETURN params?.driveId == undefined
         AND cast_to_string == True  // becomes "undefined" string
END FUNCTION

FUNCTION isBugCondition_8_23(config_extension)
  RETURN config_extension == ".js"
         AND project_is_typescript_first == True
END FUNCTION

FUNCTION isBugCondition_8_24(label_input_association)
  RETURN htmlFor_present == False
         AND id_on_input_present == False
END FUNCTION
```

---

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**

- All authenticated API requests (`GET /auth/me`, `POST /eligibility/check`, etc.) continue to
  work unchanged when `JWT_SECRET` is set via environment variable.
- The Gemini provider path in `get_llm_client()` is not modified; `gemini_temperature` still
  controls the Gemini model.
- The `allowed_branches` evaluator continues to return `PASS` for `["CSE", "ISE"]` when
  `student.branch = "CSE"`.
- The `Registration` unique-constraint deduplication remains idempotent: a second eligibility
  check by an already-registered student still returns `already_registered = True`.
- `POST /ingest/notice` continues to extract facts, persist them, and return
  `facts_extracted` / `criteria_reconciled` counts for valid inputs.
- `GET /timeline/{drive_id}` continues to return the full chronological fact log.
- The `StatusBadge` component continues to render colour-coded badges for all six status
  values (`ELIGIBLE`, `INELIGIBLE`, `UNKNOWN`, `active`, `closed`, `cancelled`).
- Login page continues to submit `POST /auth/login` and redirect to `/dashboard` on success.
- The evaluation harness `eval/run_eval.py` continues to run without LLM credentials.

**Scope:** Inputs where no bug condition holds (`¬C(X)`) must produce bit-identical results
before and after each fix.

---

## Hypothesized Root Causes

1. **Copy-paste without adaptation (Category 1):** The OpenAI and Claude branches were written
   by duplicating the Gemini branch and changing the class name, but the `temperature=` and
   `default_temperature=` arguments were not updated to use provider-specific settings fields
   that don't yet exist in `Settings`. The lambda aliases were a quick shorthand that was
   never converted to proper `def` functions.

2. **Absent startup guard (Category 2, defect 2.4):** `validate_settings()` checks for LLM
   API keys but does not check `jwt_secret`, so the default value passes silently. The
   `str(e)` leak (defect 2.5) is a common first-pass error-handling pattern that was never
   hardened before deployment.

3. **Independent parallel development (Category 3):** `branch.py` was written first with a
   simple exact-match. `allowed_branches.py` was added later by a different author who added
   normalization. Neither references the other; divergence is guaranteed on the next change.

4. **Legacy Python version habits (Category 4, defect 1.7):** `crud.py` pre-dates the
   project's upgrade to Python 3.10 syntax elsewhere. The missing `EligibilityResult` fields
   (defect 1.9) were added ad-hoc to the route response without updating the shared schema.

5. **Incorrect comment misleading the author (Category 5):** The `_infer_source_type` method
   has inline comments `# Using WhatsApp type for coordinators` which shows the author knew it
   was wrong but accepted it as a placeholder that was never corrected.

6. **Incremental file creation without init files (Category 6, defects 1.13/1.14):** Both
   `ingestion/__init__.py` and `scripts/__init__.py` were either forgotten or intentionally
   left empty/absent. The `@app.on_event` deprecation was introduced before the project
   upgraded to FastAPI ≥ 0.93.

7. **Overly broad exception catch (Category 7):** The `except Exception: pass` pattern is a
   common anti-pattern used to handle the "already registered" idempotency case, but it
   inadvertently catches all DB errors.

8. **Missing cross-file import (Category 8, defect 1.18):** `api.ts` was written before
   `auth.ts` centralised the token key, and was never updated. The `useCallback` / stale
   closure issues are standard React hooks pitfalls; the lint disable comment hid them.

---

## Correctness Properties

Property 1: Bug Condition — Provider-Specific Temperature Isolation

_For any_ call to `get_llm_client("openai")` or `get_llm_client("claude")`, the fixed factory
SHALL construct the `LangChainClient` with the provider's own temperature setting
(`openai_temperature` or `claude_temperature` respectively), NOT `gemini_temperature`, so that
changing `GEMINI_TEMPERATURE` in the environment does not silently alter non-Gemini providers.

**Validates: Requirements 2.1, 2.2**

Property 2: Preservation — Gemini Path Unchanged

_For any_ call to `get_llm_client("gemini")` (the default), the fixed factory SHALL produce a
`LangChainClient` with `default_temperature = settings.gemini_temperature`, identical to the
pre-fix behavior.

**Validates: Requirements 3.9**

Property 3: Bug Condition — PEP 8 Compliant Convenience Exports

_For any_ static analysis run (`flake8`, `mypy`) on `extraction/llm_client.py`, the fixed
module SHALL define `get_gemini_client`, `get_openai_client`, and `get_claude_client` as named
functions, producing zero E731 violations and correct type inference.

**Validates: Requirements 2.3**

Property 4: Bug Condition — JWT Secret Startup Validation

_For any_ application startup where `JWT_SECRET` is absent from the environment (or equals the
known-weak default), the fixed `validate_settings()` SHALL raise a `ValueError` before the
server accepts requests.

**Validates: Requirements 2.4**

Property 5: Preservation — Authenticated Requests Unaffected

_For any_ request bearing a valid JWT signed with a properly configured `JWT_SECRET`, the
fixed startup validation SHALL NOT interfere with token verification; `GET /auth/me` SHALL
continue to return the student profile.

**Validates: Requirements 3.1, 3.14**

Property 6: Bug Condition — Generic HTTP 500 Message

_For any_ exception raised inside `POST /ingest/notice`, the fixed handler SHALL return an
HTTP 500 response whose `detail` field contains only the generic string
`"Notice ingestion failed. Please try again."` and SHALL log the full exception server-side.

**Validates: Requirements 2.5**

Property 7: Preservation — Successful Ingestion Unaffected

_For any_ valid notice ingestion request, the fixed handler SHALL continue to return
`success=True` with correct `facts_extracted` and `criteria_reconciled` counts.

**Validates: Requirements 3.2**

Property 8: Bug Condition — Single Branch Normalization Source

_For any_ input where `criterion_type = "branch"` and `criterion.value` is either a
comma-separated string or a mixed-case list, the fixed `evaluate_branch` evaluator SHALL apply
the same uppercase normalization as `evaluate_allowed_branches`, using the shared
`_normalize_branch_list` helper.

**Validates: Requirements 2.6**

Property 9: Preservation — `allowed_branches` Evaluator Unchanged

_For any_ input where `criterion_type = "allowed_branches"`, the fixed code SHALL return the
same `CriterionResult` as before (`PASS` for CSE in `["CSE","ISE"]`, `FAIL` for MECH).

**Validates: Requirements 3.10**

Property 10: Bug Condition — EligibilityResult Carries Explanation Fields

_For any_ `EligibilityResult` instance constructed after the fix, the schema SHALL expose
`explanation: str | None` and `summary: str | None` fields, so accessing them does not raise
`AttributeError` at runtime.

**Validates: Requirements 2.9**

Property 11: Bug Condition — Narrow IntegrityError Catch

_For any_ call to `create_registration` that raises `sqlalchemy.exc.IntegrityError`, the fixed
handler SHALL silently proceed (idempotent). _For any_ call that raises any other exception
(e.g., `OperationalError`), the fixed handler SHALL re-raise it so the error is visible.

**Validates: Requirements 2.16, 3.3**

Property 12: Bug Condition — Email Adapter Channel Accuracy

_For any_ `MockEmailAdapter.fetch()` call where the sender role is `COORDINATOR`, the fixed
adapter SHALL assign `SourceType.COORDINATOR_EMAIL`; where the sender role is `STUDENT`, it
SHALL assign `SourceType.STUDENT_EMAIL`.

**Validates: Requirements 2.12**

Property 13: Preservation — Placement Cell Email Unaffected

_For any_ `MockEmailAdapter.fetch()` call where the sender role is `PLACEMENT_CELL`, the
fixed adapter SHALL continue to assign `SourceType.PLACEMENT_CELL_EMAIL`.

**Validates: Requirements 3.2**

Property 14: Bug Condition — Lifespan Context Manager

_For any_ FastAPI startup in a FastAPI ≥ 0.93 environment, the fixed `main.py` SHALL use the
`lifespan` context manager pattern and emit zero `DeprecationWarning` messages for lifecycle
events.

**Validates: Requirements 2.17**

Property 15: Bug Condition — Frontend Token Key Single Source of Truth

_For any_ Axios request interceptor call in `api.ts`, the fixed interceptor SHALL obtain the
token via the `getToken()` import from `@/lib/auth` rather than a hardcoded string literal,
so a rename of `TOKEN_KEY` in `auth.ts` propagates automatically.

**Validates: Requirements 2.18**

Property 16: Bug Condition — `useCallback` Stale Closure Prevention

_For any_ render of `DashboardPage` where `filter` changes, the fixed `loadDrives` SHALL be
wrapped in `useCallback([filter])` and the `useEffect` dependency array SHALL declare both
`loadDrives` and `isLoggedIn` explicitly, with no `// eslint-disable` suppressions.

**Validates: Requirements 2.19**

Property 17: Bug Condition — `StatusBadge` Prop Type Exhaustiveness

_For any_ TypeScript compilation of `StatusBadge.tsx`, the fixed component SHALL accept
`{ status: Status }` (the locally defined union type), enabling the compiler to flag any
caller passing an unknown status string.

**Validates: Requirements 2.21**

Property 18: Bug Condition — Safe `driveId` Extraction

_For any_ render of `DrivePage` where `useParams()` returns `undefined` for `driveId`, the
fixed code SHALL redirect to `/dashboard` or render an error boundary rather than silently
calling `getDriveTimeline("undefined")`.

**Validates: Requirements 2.22**

Property 19: Bug Condition — Login Form Accessibility

_For any_ render of `LoginPage`, the fixed form SHALL pair each `<input>` with an `id`
attribute and its `<label>` with a matching `htmlFor` attribute, satisfying WCAG 1.3.1.

**Validates: Requirements 2.24**

---

## Fix Implementation

### Category 1 — LLM Client Factory

**File:** `extraction/llm_client.py`  
**File:** `config.py`

#### config.py — Add provider-specific temperature settings

```diff
 # OpenAI settings (for future use)
 openai_api_key: str | None = None
 openai_model: str = "gpt-4o-mini"
+openai_temperature: float | None = None   # falls back to gemini_temperature if None

 # Claude settings (for future use)
 claude_api_key: str | None = None
 claude_model: str = "claude-3-haiku-20240307"
+claude_temperature: float | None = None   # falls back to gemini_temperature if None
```

**Why:** Adds opt-in per-provider temperature fields without breaking existing `.env` files.

#### llm_client.py — Fix OpenAI branch (defect 1.1)

In the `elif provider == "openai":` block, change:

```diff
-        model = ChatOpenAI(
-            model=settings.openai_model,
-            api_key=settings.openai_api_key,
-            temperature=settings.gemini_temperature,  # Use configured temp
-        )
-
-        return LangChainClient(
-            model=model,
-            default_temperature=settings.gemini_temperature,
-        )
+        _openai_temp = (
+            settings.openai_temperature
+            if settings.openai_temperature is not None
+            else settings.gemini_temperature
+        )
+        model = ChatOpenAI(
+            model=settings.openai_model,
+            api_key=settings.openai_api_key,
+            temperature=_openai_temp,
+        )
+
+        return LangChainClient(
+            model=model,
+            default_temperature=_openai_temp,
+        )
```

#### llm_client.py — Fix Claude branch (defect 1.2)

In the `elif provider == "claude":` block, change:

```diff
-        model = ChatAnthropic(
-            model=settings.claude_model,
-            api_key=settings.claude_api_key,
-            temperature=settings.gemini_temperature,  # Use configured temp
-        )
-
-        return LangChainClient(
-            model=model,
-            default_temperature=settings.gemini_temperature,
-        )
+        _claude_temp = (
+            settings.claude_temperature
+            if settings.claude_temperature is not None
+            else settings.gemini_temperature
+        )
+        model = ChatAnthropic(
+            model=settings.claude_model,
+            api_key=settings.claude_api_key,
+            temperature=_claude_temp,
+        )
+
+        return LangChainClient(
+            model=model,
+            default_temperature=_claude_temp,
+        )
```

#### llm_client.py — Replace lambda aliases with named functions (defect 1.3)

```diff
-# Convenience exports for backward compatibility
-GeminiClient = lambda: get_llm_client("gemini")
-OpenAIClient = lambda: get_llm_client("openai")
-ClaudeClient = lambda: get_llm_client("claude")
+# Convenience exports for backward compatibility
+def get_gemini_client() -> LLMClient:
+    """Return a LLMClient backed by the Gemini provider."""
+    return get_llm_client("gemini")
+
+
+def get_openai_client() -> LLMClient:
+    """Return a LLMClient backed by the OpenAI provider."""
+    return get_llm_client("openai")
+
+
+def get_claude_client() -> LLMClient:
+    """Return a LLMClient backed by the Claude (Anthropic) provider."""
+    return get_llm_client("claude")
```

**Why:** Named functions satisfy PEP 8 E731, get proper `def`-level docstrings, and allow
mypy to infer the return type `LLMClient` without an explicit annotation.

---

### Category 2 — Security

**File:** `config.py`

#### Raise on weak JWT secret (defect 1.4)

In `validate_settings()`, add before the return:

```diff
+    if settings.jwt_secret == "CHANGE_THIS_IN_PRODUCTION":
+        raise ValueError(
+            "JWT_SECRET is using the insecure default value. "
+            "Set a strong random secret in the JWT_SECRET environment variable "
+            "before starting the server."
+        )
```

Also wire `validate_settings()` into the application lifespan (see Category 6 fix for
`main.py`).

**File:** `api/routes/ingestion.py`

#### Replace raw `str(e)` with generic message (defect 1.5)

```diff
-    except Exception as e:
-        raise HTTPException(
-            status_code=500,
-            detail=f"Failed to ingest notice: {str(e)}",
-        )
+    except Exception:
+        import logging as _logging
+        _logging.getLogger(__name__).exception("Notice ingestion error")
+        raise HTTPException(
+            status_code=500,
+            detail="Notice ingestion failed. Please try again.",
+        )
```

**Why:** The server-side `logger.exception()` call preserves the full traceback in logs,
while the client receives only the generic message. No internal paths or API key fragments
are exposed.

---

### Category 3 — Duplicate Branch Evaluator Normalization

**File:** `rules/evaluators/allowed_branches.py`

Extract the normalization logic into a shared helper at the **top of the file** (or into a
new `rules/evaluators/_shared.py` if the project grows more cross-evaluator helpers):

```python
def _normalize_branch_list(raw: object) -> list[str]:
    """Normalize a branch criterion value to an uppercase list.

    Accepts:
        - list  : ["CSE", "ise"] → ["CSE", "ISE"]
        - str   : "CSE,ISE"     → ["CSE", "ISE"]
        - other : str(raw).upper() as a single-element list
    """
    if isinstance(raw, list):
        return [str(b).strip().upper() for b in raw]
    if isinstance(raw, str):
        return [b.strip().upper() for b in raw.split(",")]
    return [str(raw).strip().upper()]
```

**File:** `rules/evaluators/branch.py`

Import and use the shared helper:

```diff
+from rules.evaluators.allowed_branches import _normalize_branch_list
+
 @register("branch")
 def evaluate_branch(criterion: Criterion, student: Student) -> CriterionResult:
     if student.branch is None:
         return CriterionResult(
             criterion=criterion,
             status=Status.UNKNOWN,
             student_value=None,
             message="Student branch is not on record.",
         )

-    allowed_branches: list[str] = criterion.value
-    passed = student.branch in allowed_branches
+    allowed_branches = _normalize_branch_list(criterion.value)
+    student_branch = student.branch.strip().upper()
+    passed = student_branch in allowed_branches
     return CriterionResult(
         criterion=criterion,
         status=Status.PASS if passed else Status.FAIL,
         student_value=student.branch,
         message=(
             f"Branch {student.branch} is "
             f"{'' if passed else 'not '}one of the allowed branches {allowed_branches}."
         ),
     )
```

**File:** `rules/evaluators/allowed_branches.py`

Replace inline normalization block with the shared helper:

```diff
-    raw = criterion.value
-    if isinstance(raw, list):
-        allowed: list[str] = [b.strip().upper() for b in raw]
-    elif isinstance(raw, str):
-        allowed = [b.strip().upper() for b in raw.split(",")]
-    else:
-        allowed = [str(raw).upper()]
-
-    student_branch = student.branch.strip().upper()
+    allowed = _normalize_branch_list(criterion.value)
+    student_branch = student.branch.strip().upper()
```

---

### Category 4 — Type Annotation Gaps

**File:** `database/crud.py`

Remove `from typing import List` and replace all `List[X]` annotations with `list[X]`
(defect 1.7). There are six affected function signatures:

| Function | Old return type | New return type |
|---|---|---|
| `get_students` | `List[Student]` | `list[Student]` |
| `search_students` | `List[Student]` | `list[Student]` |
| `get_drives` | `List[Drive]` | `list[Drive]` |
| `get_facts_by_drive` | `List[Fact]` | `list[Fact]` |
| `get_facts_by_rule_key` | `List[Fact]` | `list[Fact]` |
| `get_fact_by_source` | `List[Fact]` | `list[Fact]` |
| `get_registrations_by_student` | `List[Registration]` | `list[Registration]` |
| `get_registrations_by_drive` | `List[Registration]` | `list[Registration]` |

**File:** `core/schemas.py`

Pre-compile the USN regex (defect 1.8):

```diff
+_USN_PATTERN = re.compile(r"^1MS\d{2}[A-Z]{2,4}\d{2,4}$")
+
 class Student(BaseModel):
     ...
     @field_validator("usn")
     @classmethod
     def validate_usn(cls, v: str) -> str:
-        pattern = r"^1MS\d{2}[A-Z]{2,4}\d{2,4}$"
-        if not re.match(pattern, v.upper()):
+        if not _USN_PATTERN.match(v.upper()):
             raise ValueError(...)
         return v.upper()
```

Add missing fields to `EligibilityResult` (defect 1.9):

```diff
 class EligibilityResult(BaseModel):
     student_id: str
     drive_id: str
     status: EligibilityStatus
     criterion_results: list[CriterionResult]
+    explanation: str | None = None
+    summary: str | None = None
```

**File:** `api/routes/eligibility.py`

Remove dead import (defect 1.10):

```diff
 from database.crud import (
     create_registration,
     get_current_criteria,
     get_drive,
-    get_student,
     get_registration,
 )
```

**File:** `eval/run_eval.py`

Remove unused imports (defect 1.11):

```diff
-from database.connection import get_db_context
-from database import crud
```

The `init_db` import and call on the `__main__` path are intentional (dev/test seeding) and
are left in place. The `from database import init_db` import stays.

---

### Category 5 — Wrong SourceType Mapping

**File:** `core/schemas.py`

Add two new enum members so coordinator and student email sources are expressible:

```diff
 class SourceType(str, Enum):
     OFFICIAL_COMPANY_PDF = "official_company_pdf"
     PLACEMENT_CELL_WHATSAPP = "placement_cell_whatsapp"
     PLACEMENT_CELL_EMAIL = "placement_cell_email"
     COORDINATOR_WHATSAPP = "coordinator_whatsapp"
+    COORDINATOR_EMAIL = "coordinator_email"
     STUDENT_PORTAL = "student_portal"
     STUDENT_WHATSAPP = "student_whatsapp"
+    STUDENT_EMAIL = "student_email"
```

Add the new types to `SOURCE_AUTHORITY_RANK`:

```diff
 SOURCE_AUTHORITY_RANK: dict[SourceType, int] = {
     SourceType.OFFICIAL_COMPANY_PDF: 1,
     SourceType.PLACEMENT_CELL_WHATSAPP: 2,
     SourceType.PLACEMENT_CELL_EMAIL: 2,
     SourceType.COORDINATOR_WHATSAPP: 3,
+    SourceType.COORDINATOR_EMAIL: 3,
     SourceType.STUDENT_PORTAL: 4,
     SourceType.STUDENT_WHATSAPP: 5,
+    SourceType.STUDENT_EMAIL: 5,
 }
```

**Why ranks:** Coordinator email carries the same authority as coordinator WhatsApp (rank 3);
student email has the same weight as student WhatsApp (rank 5). This is consistent with the
authority model in `DESIGN.md §3.1`.

**File:** `ingestion/mock_email/adapter.py`

Fix `_infer_source_type` (defect 1.12):

```diff
-        elif sender_role == SenderRole.COORDINATOR:
-            return SourceType.COORDINATOR_WHATSAPP  # Using WhatsApp type for coordinators
-        else:
-            return SourceType.STUDENT_WHATSAPP  # Using WhatsApp type for students
+        elif sender_role == SenderRole.COORDINATOR:
+            return SourceType.COORDINATOR_EMAIL
+        else:
+            return SourceType.STUDENT_EMAIL
```

Remove the misleading inline comments from the method.

---

### Category 6 — Package Structure

**File:** `ingestion/__init__.py` (defect 1.13)

Replace empty file with a descriptive module docstring:

```python
"""Ingestion pipeline for PlaceGuard.

This package provides the source adapters and coordinator that fetch placement
notices from multiple channels (WhatsApp, email, PDF, portal) and normalize
them into ``RawMessage`` objects for downstream extraction and reconciliation.

Public components:
    adapters/    — SourceAdapter ABC and concrete channel implementations
    mock_email/  — JSON-file-backed email adapter for testing
    coordinator  — Orchestrates multi-source fetch and deduplication
"""
```

**File:** `scripts/__init__.py` (defect 1.14)

Create the missing file:

```python
"""Utility scripts for PlaceGuard development and operations.

These scripts are not part of the application runtime; they are intended to
be run manually by developers and operators.

Scripts:
    migrate_dev.py — seeds the development SQLite database with synthetic data
"""
```

**File:** `api/main.py` (defects 1.15, 1.17)

Replace the deprecated `@app.on_event("startup")` with a `lifespan` context manager, and
guard `init_db()` with the `settings.debug` flag:

```diff
-from fastapi import FastAPI
+from contextlib import asynccontextmanager
+
+from fastapi import FastAPI
 from fastapi.middleware.cors import CORSMiddleware

 from api.routes import drives, eligibility, ingestion, students
 from api.routes.auth import router as auth_router
 from api.routes.timeline import router as timeline_router
 from config import settings, validate_settings
 from database.connection import init_db

-# Create FastAPI app
-app = FastAPI(...)
-
-# ... middleware ...
-
-# Startup event
-@app.on_event("startup")
-async def startup_event():
-    """Initialize database on startup."""
-    init_db()
+@asynccontextmanager
+async def lifespan(app: FastAPI):
+    """Application lifespan — replaces deprecated @app.on_event."""
+    # Validate critical settings before accepting traffic
+    validate_settings()
+    # Only create tables directly in debug/test environments;
+    # production uses Alembic migrations exclusively.
+    if settings.debug:
+        init_db()
+    yield
+    # (shutdown hooks go here when needed)
+
+# Create FastAPI app
+app = FastAPI(
+    title="PlaceGuard API",
+    ...,
+    lifespan=lifespan,
+)
```

**Why guarding `init_db()` with `settings.debug`:** In production `ALEMBIC` is the sole
schema authority. Calling `Base.metadata.create_all` in production can silently create tables
that bypass migration history, causing `alembic upgrade head` to fail on the next deploy.

---

### Category 7 — Error Handling

**File:** `api/routes/eligibility.py`

Replace broad exception catch with narrow `IntegrityError` catch (defect 1.16):

```diff
+from sqlalchemy.exc import IntegrityError
 ...
             try:
                 create_registration(
                     db,
                     usn=student.usn,
                     drive_id=request.drive_id,
                     eligibility_snapshot=result.model_dump(mode="json"),
                 )
-            except Exception:
-                pass  # unique constraint hit — already registered
+            except IntegrityError:
+                db.rollback()  # restore session after constraint violation
+                # unique constraint hit — student already registered; safe to continue
```

**Why `db.rollback()`:** SQLAlchemy marks the session as "rolled back needed" after a flush
error. Without an explicit rollback the session is unusable for the rest of the request.

---

### Category 8 — Frontend Quality

**File:** `frontend/src/lib/api.ts` (defect 1.18)

```diff
+import { getToken } from "@/lib/auth";
 ...
 api.interceptors.request.use((config) => {
-  const token = typeof window !== "undefined" ? localStorage.getItem("pg_token") : null;
+  const token = getToken();
   if (token) config.headers.Authorization = `Bearer ${token}`;
   return config;
 });
```

**File:** `frontend/src/app/dashboard/page.tsx` (defect 1.19)

```diff
-import { useEffect, useState } from "react";
+import { useCallback, useEffect, useState } from "react";
 ...
-  useEffect(() => {
-    if (!isLoggedIn()) { router.push("/login"); return; }
-    loadDrives();
-  }, [filter]); // eslint-disable-line
-
-  async function loadDrives() {
+  const loadDrives = useCallback(async () => {
     setLoading(true);
     setError(null);
     try {
       const data = await listDrives(filter === "all" ? undefined : filter);
       setDrives(data);
     } catch {
       setError("Failed to load drives. Is the API server running?");
     } finally {
       setLoading(false);
     }
-  }
+  }, [filter]);
+
+  useEffect(() => {
+    if (!isLoggedIn()) { router.push("/login"); return; }
+    loadDrives();
+  }, [loadDrives, router]);
```

**File:** `frontend/src/app/drive/[driveId]/page.tsx` (defects 1.20, 1.22)

Fix alignment whitespace (defect 1.20) — remove triple-space alignment:

```diff
-  const [timeline, setTimeline]           = useState<DriveTimeline | null>(null);
-  const [eligibility, setEligibility]     = useState<EligibilityResult | null>(null);
-  const [timelineLoading, setTLLoading]   = useState(true);
-  const [eligLoading, setEligLoading]     = useState(false);
-  const [error, setError]                 = useState<string | null>(null);
+  const [timeline, setTimeline] = useState<DriveTimeline | null>(null);
+  const [eligibility, setEligibility] = useState<EligibilityResult | null>(null);
+  const [timelineLoading, setTLLoading] = useState(true);
+  const [eligLoading, setEligLoading] = useState(false);
+  const [error, setError] = useState<string | null>(null);
```

Fix unsafe `driveId` cast (defect 1.22):

```diff
-  const driveId = params?.driveId as string;
+  const rawDriveId = params?.driveId;
+  const driveId = typeof rawDriveId === "string" && rawDriveId ? rawDriveId : null;
+
+  // Guard: redirect if driveId is absent (should not happen in normal navigation)
+  useEffect(() => {
+    if (!driveId) { router.push("/dashboard"); }
+  }, [driveId, router]);
```

Replace the subsequent direct use of `driveId` in `loadTimeline` and `handleCheckEligibility`
with the guarded value (the `useEffect` above makes `driveId` non-null by the time those
functions run, but TypeScript still needs the type to be `string`, not `string | null`):

```diff
+  if (!driveId) return null;   // render nothing while redirect is in flight
```

**File:** `frontend/src/components/StatusBadge.tsx` (defect 1.21)

```diff
-export default function StatusBadge({ status }: { status: string }) {
+export default function StatusBadge({ status }: { status: Status }) {
```

**File:** `frontend/next.config.js` → `frontend/next.config.ts` (defect 1.23)

Rename the file and rewrite with TypeScript syntax:

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/:path*",
      },
    ];
  },
};

export default nextConfig;
```

Also update `frontend/package.json` if it references `next.config.js` explicitly (check
the `scripts` field — Next.js auto-discovers `next.config.ts`).

**File:** `frontend/src/app/login/page.tsx` (defect 1.24)

Add `id` to inputs and `htmlFor` to labels:

```diff
-          <div>
-            <label className="block text-sm font-medium text-gray-700 mb-1">
-              USN
-            </label>
-            <input
-              type="text"
-              required
-              placeholder="1MS22CS042"
-              value={usn}
-              onChange={(e) => setUsn(e.target.value.toUpperCase())}
-              className="..."
-            />
-          </div>
-
-          <div>
-            <label className="block text-sm font-medium text-gray-700 mb-1">
-              Date of Birth
-            </label>
-            <input
-              type="date"
-              required
-              value={dob}
-              onChange={(e) => setDob(e.target.value)}
-              className="..."
-            />
-          </div>
+          <div>
+            <label htmlFor="usn" className="block text-sm font-medium text-gray-700 mb-1">
+              USN
+            </label>
+            <input
+              id="usn"
+              type="text"
+              required
+              placeholder="1MS22CS042"
+              value={usn}
+              onChange={(e) => setUsn(e.target.value.toUpperCase())}
+              className="..."
+            />
+          </div>
+
+          <div>
+            <label htmlFor="dob" className="block text-sm font-medium text-gray-700 mb-1">
+              Date of Birth
+            </label>
+            <input
+              id="dob"
+              type="date"
+              required
+              value={dob}
+              onChange={(e) => setDob(e.target.value)}
+              className="..."
+            />
+          </div>
```

---

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach:

1. **Exploratory (bug condition checking):** Write targeted tests against the unfixed code to
   surface counterexamples and confirm the root cause analysis.
2. **Fix + Preservation checking:** After applying fixes, run the existing test suite plus new
   property-based and unit tests to confirm correct behavior and absence of regressions.

---

### Exploratory Bug Condition Checking

**Goal:** Surface counterexamples that demonstrate each defect on UNFIXED code.

**Test Cases (run before applying fixes):**

1. **Temperature isolation (defects 1.1, 1.2):** Call `get_llm_client("openai")` / 
   `get_llm_client("claude")` with `settings.gemini_temperature = 0.9` and assert the
   constructed model's temperature is `0.9` — this will PASS (demonstrating the bug) on
   unfixed code.

2. **Lambda PEP 8 (defect 1.3):** Run `flake8 extraction/llm_client.py` — expect E731 on
   three lines on unfixed code.

3. **JWT secret startup (defect 1.4):** Call `validate_settings()` without `JWT_SECRET` env
   var — expect no exception raised on unfixed code (demonstrating the gap).

4. **str(e) leak (defect 1.5):** POST `/ingest/notice` with an invalid API key; inspect the
   response `detail` field — expect partial key string visible on unfixed code.

5. **Branch normalization divergence (defect 1.6):** Call `evaluate_branch` with
   `value="cse"` and `student.branch="CSE"` — expect `FAIL` on unfixed code.

6. **EligibilityResult fields (defect 1.9):** Construct `EligibilityResult(student_id="x",
   drive_id="y", status=EligibilityStatus.ELIGIBLE, criterion_results=[])` and access
   `.explanation` — expect `AttributeError` on unfixed code.

7. **IntegrityError swallowing (defect 1.16):** Mock `create_registration` to raise
   `sqlalchemy.exc.OperationalError`; call the eligibility endpoint — expect `status=200`
   with missing registration on unfixed code (error silently swallowed).

8. **Email adapter source type (defect 1.12):** Call `MockEmailAdapter._infer_source_type()`
   with `SenderRole.COORDINATOR` — expect `SourceType.COORDINATOR_WHATSAPP` on unfixed code.

9. **Frontend token key (defect 1.18):** Grep `frontend/src/lib/api.ts` for `"pg_token"` —
   expect the magic string to be present on unfixed code.

**Expected Counterexamples:**
- `openai_temperature` and `claude_temperature` fields do not exist in `Settings` (unfixed).
- `validate_settings()` completes without raising when `JWT_SECRET` is default (unfixed).
- `evaluate_branch` returns `FAIL` for mixed-case input (unfixed).

---

### Fix Checking

**Goal:** Verify that for all inputs where a bug condition holds, the fixed function produces
the expected behavior.

```
FOR ALL defect IN ACTIVE_DEFECTS DO
  FOR ALL input WHERE isBugCondition(defect, input) DO
    result := fixed_function(input)
    ASSERT expectedBehavior(defect, result)
  END FOR
END FOR
```

---

### Preservation Checking

**Goal:** Verify that all inputs where no bug condition holds produce identical results.

```
FOR ALL input WHERE NOT isBugCondition(ANY_DEFECT, input) DO
  ASSERT original_function(input) == fixed_function(input)
END FOR
```

**Testing Approach:** Property-based testing is used for the rule engine (branch evaluator,
eligibility engine) because:
- It generates many random `Criterion` / `Student` combinations automatically.
- It catches mixed-case / whitespace edge cases that hand-written tests miss.
- The `allowed_branches` evaluator has an existing passing test suite that acts as an oracle.

---

### Unit Tests

**Backend:**

- `test_llm_client.py::test_openai_uses_openai_temperature` — mock `ChatOpenAI`, assert
  constructor receives `temperature=settings.openai_temperature`.
- `test_llm_client.py::test_claude_uses_claude_temperature` — same for Claude.
- `test_llm_client.py::test_gemini_path_unchanged` — Gemini branch still uses
  `gemini_temperature`.
- `test_llm_client.py::test_convenience_functions_are_callable` — `get_gemini_client`,
  `get_openai_client`, `get_claude_client` are callable functions, not lambdas.
- `test_config.py::test_validate_settings_raises_on_weak_jwt_secret` — `ValueError` raised.
- `test_config.py::test_validate_settings_passes_with_strong_secret` — no exception.
- `test_ingestion_route.py::test_500_returns_generic_message` — response `detail` does not
  contain any substring of the original exception message.
- `test_branch_evaluators.py::test_branch_normalizes_lowercase` — `evaluate_branch` with
  `value="cse"` and `student.branch="CSE"` returns `PASS`.
- `test_branch_evaluators.py::test_branch_normalizes_comma_string` — `value="CSE,ISE"`.
- `test_eligibility_route.py::test_integrity_error_is_handled_silently` — `IntegrityError`
  from `create_registration` does not propagate to response.
- `test_eligibility_route.py::test_operational_error_is_reraised` — `OperationalError`
  propagates as HTTP 500.
- `test_mock_email_adapter.py::test_coordinator_email_maps_to_coordinator_email_type`.
- `test_mock_email_adapter.py::test_student_email_maps_to_student_email_type`.
- `test_mock_email_adapter.py::test_placement_cell_email_unchanged`.

**Frontend:**

- `StatusBadge.test.tsx` — TypeScript compile check: passing `status="unknown_value"` should
  produce a type error.
- `api.test.ts` — mock `getToken` from `@/lib/auth`; assert the interceptor calls it (not
  `localStorage.getItem("pg_token")` directly).
- `DashboardPage.test.tsx` — render the component, change filter, assert `loadDrives` is
  called and no eslint-disable comment appears in source.
- Accessibility test: use `@testing-library/jest-dom` to assert `getByLabelText("USN")` finds
  the input in the login page.

---

### Property-Based Tests

- **Branch evaluator preservation:** Generate `Hypothesis` strategies for `Criterion` with
  `criterion_type = "branch"` and random `value` (list or string, mixed case), and
  `Student` with random `branch`. Assert: result for `evaluate_branch` == result for
  `evaluate_allowed_branches` for all generated inputs after the fix.
- **EligibilityResult round-trip:** Generate random `EligibilityResult` instances and
  serialize/deserialize via `model_dump(mode="json")` / `model_validate`. Assert
  `explanation` and `summary` fields survive the round-trip without `ValidationError`.
- **Source type authority rank completeness:** Assert `SOURCE_AUTHORITY_RANK` contains an
  entry for every member of the `SourceType` enum after the two new members are added.

---

### Integration Tests

- **Full eligibility flow:** POST `/ingest/notice` (valid notice) → POST `/eligibility/check`
  → assert `status=ELIGIBLE`, `registration_link` present, `Registration` row created.
- **Idempotent re-check:** POST `/eligibility/check` a second time for same student/drive →
  assert `already_registered=True`, no duplicate `Registration` row.
- **Ingest error propagation:** POST `/ingest/notice` with mock LLM raising `RuntimeError` →
  assert HTTP 500 `detail == "Notice ingestion failed. Please try again."`.
- **JWT startup guard:** Start app without `JWT_SECRET` env var → assert process exits with
  `ValueError` before binding port.
- **Coordinator email ingestion:** Feed a coordinator-role email through `MockEmailAdapter`
  → assert `source_type = "coordinator_email"` in the persisted `Fact` row.

---

## Migration and Rollout Approach

### Step 1 — Non-breaking, no-risk changes (can be merged immediately)

Apply these in a single PR; they have zero runtime behavior change:

| Defect | Change | Risk |
|---|---|---|
| 1.7 | `typing.List` → `list[]` in `crud.py` | None — Python 3.10+ no-op |
| 1.8 | Pre-compile USN regex | None — functionally identical |
| 1.10 | Remove dead `get_student` import | None |
| 1.11 | Remove dead `get_db_context`, `crud` imports | None |
| 1.13 | Add docstring to `ingestion/__init__.py` | None |
| 1.14 | Add `scripts/__init__.py` | None |
| 1.20 | Fix whitespace alignment in `[driveId]/page.tsx` | None |
| 1.23 | Rename `next.config.js` → `next.config.ts` | Minimal — Next.js auto-discovers |

### Step 2 — Schema additions (additive, backward-compatible)

Apply in a single PR before any route changes:

| Defect | Change | Risk |
|---|---|---|
| 1.9 | Add `explanation`, `summary` to `EligibilityResult` | None — new optional fields |
| 1.12 / 5 | Add `COORDINATOR_EMAIL`, `STUDENT_EMAIL` to `SourceType` enum + rank dict | None — new enum values |

### Step 3 — Logic fixes (test-gated)

These change observable behavior and require passing the full test suite:

| Defect | Change | Gating condition |
|---|---|---|
| 1.1, 1.2 | Fix LLM temperature per provider | Unit tests for all three provider paths |
| 1.3 | Replace lambda aliases with named functions | `flake8`, `mypy` clean |
| 1.6 | Shared branch normalization helper | Property-based test: `branch == allowed_branches` for all inputs |
| 1.12 | Fix email adapter source types | Unit test for all three sender roles |
| 1.16 | Narrow `except Exception` to `IntegrityError` | Unit tests for both `IntegrityError` and `OperationalError` |

### Step 4 — Security fixes (require env var change before deploy)

| Defect | Change | Pre-deploy action required |
|---|---|---|
| 1.4 | Add JWT secret startup validation | Set `JWT_SECRET` in all deployment environments **before** deploying |
| 1.5 | Generic HTTP 500 message | None — but confirm logging is configured to capture tracebacks |

**Deploy order for defect 1.4:** Update `.env` / secrets manager with a strong `JWT_SECRET`
first, then deploy the code change. Reversing this order will crash the server on startup.

### Step 5 — Structural changes (require smoke test)

| Defect | Change | Smoke test |
|---|---|---|
| 1.15 | Guard `init_db()` with `settings.debug` | Verify `alembic upgrade head` succeeds cleanly on a fresh DB |
| 1.17 | Replace `@app.on_event` with `lifespan` | `GET /health` returns 200 after deploy |

### Step 6 — Frontend changes (CI/CD gated)

| Defect | Change | CI check |
|---|---|---|
| 1.18 | Use `getToken()` in interceptor | `yarn test` passes |
| 1.19 | `useCallback` + fix `useEffect` deps | ESLint 0 warnings |
| 1.21 | `StatusBadge` prop type narrowing | TypeScript compile clean |
| 1.22 | Safe `driveId` extraction | Manual smoke test on `/drive/[driveId]` page |
| 1.24 | Add `id`/`htmlFor` to login inputs | `axe-core` accessibility test passes |

---

## Regression Prevention

### Automated Guards

1. **`mypy --strict` in CI:** Catches future `typing.List` regressions, lambda assignments,
   missing type annotations, and undeclared fields on Pydantic models.

2. **`flake8` in CI:** Catches E731 (lambda alias) regressions.

3. **`bandit` security scan in CI:** Add rule `B105` (hardcoded password strings) to catch
   future fallback-secret patterns.

4. **Property-based tests in CI (Hypothesis):** Run `test_branch_evaluators.py` with
   `@settings(max_examples=500)` to ensure branch normalization never diverges again.

5. **`SOURCE_AUTHORITY_RANK` completeness test:** A unit test that asserts
   `set(SourceType) == set(SOURCE_AUTHORITY_RANK.keys())` so new `SourceType` members without
   a rank entry fail immediately.

6. **ESLint `react-hooks/exhaustive-deps` rule:** Enforce in `.eslintrc` with `"error"`
   severity so `// eslint-disable` suppressions for hooks are flagged in PR review.

7. **`axe-core` / `jest-axe` accessibility checks:** Add to the frontend test suite to
   catch missing `htmlFor`/`id` associations on form elements.

### Code Review Checklist Additions

- Any new LLM provider branch in `get_llm_client()` **must** use a dedicated `settings.*_temperature` field.
- Any `except Exception` block **must** include a comment justifying the breadth of the catch.
- Any `SourceType` enum member addition **must** be accompanied by a `SOURCE_AUTHORITY_RANK` entry.
- Any Pydantic response model returned from a route **must** declare all fields that the route populates.
