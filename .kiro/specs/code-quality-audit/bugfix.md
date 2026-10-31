# Bugfix Requirements Document

## Introduction

The PlaceGuard codebase contains a range of accumulated code quality defects spanning the Python backend and the Next.js/TypeScript frontend. These defects include: semantic bugs introduced by copy-paste errors in the LLM client factory, missing or incorrect type annotations, duplicate evaluator logic with no single source of truth, broken package-structure conventions, inconsistent error-handling patterns, inline security risks (hardcoded JWT fallback secret, raw `str(e)` leak in API responses), dead code and unused imports, and several TypeScript type-safety gaps in the frontend. Left unaddressed these issues reduce maintainability, create security exposure, and can introduce silent runtime failures.

---

## Bug Analysis

### Current Behavior (Defect)

**Python Backend — LLM Client Factory**

1.1 WHEN the OpenAI provider is selected THEN the system passes `settings.gemini_temperature` as the `temperature` argument to `ChatOpenAI`, silently ignoring any `openai_temperature` or `openai_model` specific configuration

1.2 WHEN the Claude provider is selected THEN the system passes `settings.gemini_temperature` as the `temperature` argument to `ChatAnthropic`, silently ignoring any Claude-specific temperature configuration

1.3 WHEN `get_llm_client()` is called THEN the module exposes three module-level lambda aliases (`GeminiClient`, `OpenAIClient`, `ClaudeClient`) that are assigned as bare lambdas without type annotations, violating PEP 8 (lambdas must not be assigned to a variable name) and producing a mypy error

**Python Backend — Security**

1.4 WHEN the application starts without a `JWT_SECRET` environment variable THEN the system uses the hardcoded fallback string `"CHANGE_THIS_IN_PRODUCTION"` as the signing key, allowing any attacker who reads the source code to forge valid JWTs

1.5 WHEN an unhandled exception occurs in `POST /ingest/notice` THEN the system returns `str(e)` verbatim as the HTTP 500 `detail`, potentially leaking internal stack traces, file paths, or API-key names to the client

**Python Backend — Duplicate Criterion Evaluators / Missing Source of Truth**

1.6 WHEN the LLM extraction stage emits `criterion_type = "branch"` THEN the evaluator at `rules/evaluators/branch.py` is invoked; when it emits `"allowed_branches"` THEN a separate evaluator at `rules/evaluators/allowed_branches.py` is invoked — both contain duplicated normalization logic with no shared helper, making them diverge silently over time

**Python Backend — Type Annotation Gaps and Import Issues**

1.7 WHEN `database/crud.py` imports `List` from `typing` THEN the system uses the legacy `typing.List` generic instead of the built-in `list[...]` union syntax available since Python 3.9, inconsistent with all other files in the project that already use PEP 604 / PEP 585 syntax

1.8 WHEN `core/schemas.py` imports `re` THEN the `re` module is imported at module level but `field_validator` in `validate_usn` is the only consumer — the import itself is fine, but `re.match` is called without pre-compiling the pattern, meaning the pattern is re-compiled on every USN validation call

1.9 WHEN `explanation/generator.py` references `EligibilityResult` from `core.schemas` THEN the import is present but `EligibilityResult` in `core/schemas.py` is not annotated with `explanation: str | None` or `summary: str | None` fields, yet the eligibility route and explanation generator both write to and read from those fields, causing an AttributeError at runtime if the schema is used directly

1.10 WHEN `api/routes/eligibility.py` performs a `from database.crud import get_student` import THEN `get_student` is imported but never called in that module (the student is obtained via the `get_current_student` dependency), making it a dead import

1.11 WHEN `eval/run_eval.py` imports `from database import init_db` and `from database import crud` THEN it also imports `from database.connection import get_db_context` but `get_db_context` and `crud` are never used in the module body, resulting in unused imports

**Python Backend — Package / Module Structure**

1.12 WHEN `ingestion/mock_email/adapter.py` maps a `COORDINATOR`-role email sender to `SourceType.COORDINATOR_WHATSAPP` and a `STUDENT`-role email sender to `SourceType.STUDENT_WHATSAPP` THEN the system misclassifies email-channel messages as WhatsApp-channel messages, incorrectly assigning authority ranks for coordinator and student email sources

1.13 WHEN the `ingestion/` package is initialized THEN `ingestion/__init__.py` is empty (zero bytes), providing no public API surface and no documentation of the package's purpose, inconsistent with every other package in the project which documents themselves in `__init__.py`

1.14 WHEN the `scripts/` directory contains `migrate_dev.py` THEN there is no `__init__.py` making it an implicit namespace package, inconsistent with the rest of the project

1.15 WHEN `alembic/env.py` exists alongside `api/main.py` which calls `init_db()` on startup THEN both `Base.metadata.create_all` (via `init_db`) and Alembic migrations can operate on the same database simultaneously, creating a risk of schema divergence in production

**Python Backend — Error Handling**

1.16 WHEN `api/routes/eligibility.py` catches the unique-constraint exception from `create_registration` THEN it uses a bare `except Exception: pass` block that silently swallows all exceptions including database connection errors, not just the intended `IntegrityError`

1.17 WHEN `api/main.py` registers the startup lifecycle with `@app.on_event("startup")` THEN the code uses the deprecated FastAPI lifecycle event decorator (deprecated since FastAPI 0.93 / Starlette 0.20) instead of the recommended `lifespan` context manager

**Frontend — TypeScript / React Quality**

1.18 WHEN `frontend/src/lib/api.ts` accesses `localStorage.getItem("pg_token")` directly inside the Axios request interceptor THEN the auth token key `"pg_token"` is hardcoded as a magic string, duplicating the constant already defined as `TOKEN_KEY` in `auth.ts`, meaning any key rename requires updating two files

1.19 WHEN `frontend/src/app/dashboard/page.tsx` declares the `loadDrives` async function inside the component body without wrapping it in `useCallback` THEN the `useEffect` dependency array uses `// eslint-disable-line` to suppress the exhaustive-deps warning instead of properly declaring `filter` and `loadDrives` as dependencies, masking a potential stale-closure bug

1.20 WHEN `frontend/src/app/drive/[driveId]/page.tsx` declares state variables THEN inconsistent alignment whitespace is used in multiple `useState` declarations (e.g., triple-space alignment), violating the project's Prettier/ESLint formatting expectations

1.21 WHEN `frontend/src/components/StatusBadge.tsx` defines a local `type Status` THEN the type is declared but never used as the prop type — the component accepts `{ status: string }` instead of `{ status: Status }`, losing compile-time exhaustiveness checking for all valid status values

1.22 WHEN `frontend/src/app/drive/[driveId]/page.tsx` uses `useParams()` THEN the `driveId` parameter is cast with `params?.driveId as string`, which will silently evaluate to `"undefined"` string if the param is absent rather than handling the impossible-but-typed `undefined` case

1.23 WHEN `frontend/next.config.js` is used in a TypeScript-first Next.js 14 project THEN the config file uses the `.js` extension instead of `next.config.ts`, inconsistent with `tailwind.config.ts` which does use TypeScript

**Frontend — Missing Error Boundaries / Accessibility**

1.24 WHEN the login form in `frontend/src/app/login/page.tsx` renders input fields THEN the `<input>` elements do not have explicit `id` attributes matched to their `<label>` elements via `htmlFor`, breaking the label–input association required for screen readers

---

### Expected Behavior (Correct)

**Python Backend — LLM Client Factory**

2.1 WHEN the OpenAI provider is selected THEN the system SHALL use a dedicated `openai_temperature` setting (defaulting to `settings.gemini_temperature` only as a fallback) so that provider-specific tuning is possible without touching Gemini configuration

2.2 WHEN the Claude provider is selected THEN the system SHALL use a dedicated `claude_temperature` setting (defaulting to `settings.gemini_temperature` only as a fallback) so that provider-specific tuning is possible without touching Gemini configuration

2.3 WHEN `get_llm_client()` module-level convenience aliases are defined THEN the system SHALL define them as named functions (e.g., `def get_gemini_client() -> LLMClient`) rather than bare lambda assignments, complying with PEP 8 E731 and enabling correct type inference

**Python Backend — Security**

2.4 WHEN the application starts without a `JWT_SECRET` environment variable THEN the system SHALL raise a `ValueError` during startup (via `validate_settings()`) rather than silently proceeding with a known-weak key, ensuring that misconfigured deployments fail fast

2.5 WHEN an unhandled exception occurs in `POST /ingest/notice` THEN the system SHALL return a generic error message (e.g., `"Notice ingestion failed. Please try again."`) and SHALL log the full exception server-side, preventing internal details from leaking to the client

**Python Backend — Duplicate Criterion Evaluators**

2.6 WHEN either `criterion_type = "branch"` or `criterion_type = "allowed_branches"` is evaluated THEN the system SHALL use a single shared normalization helper (e.g., `_normalize_branch_list`) referenced by both evaluators, so branch-matching logic has exactly one implementation

**Python Backend — Type Annotation Gaps and Import Issues**

2.7 WHEN `database/crud.py` declares return types THEN the system SHALL use built-in `list[...]` generic syntax (PEP 585) instead of `typing.List`, consistent with all other modules in the project

2.8 WHEN `core/schemas.py` validates USN format THEN the system SHALL pre-compile the USN regex pattern as a module-level constant (e.g., `_USN_PATTERN = re.compile(...)`) so the pattern is compiled once at import time, not on every validation call

2.9 WHEN `core/schemas.py` defines `EligibilityResult` THEN the schema SHALL include `explanation: str | None = None` and `summary: str | None = None` fields so that the explanation route and explanation generator can write and read those fields through the typed schema rather than relying on undeclared attributes

2.10 WHEN `api/routes/eligibility.py` is imported THEN the system SHALL NOT import `get_student` from `database.crud` since it is unused; the import SHALL be removed to keep the import block clean

2.11 WHEN `eval/run_eval.py` is imported THEN unused imports (`get_db_context`, bare `crud`) SHALL be removed; any actual usage of crud helpers SHALL be done through explicit named imports

**Python Backend — Package / Module Structure**

2.12 WHEN `ingestion/mock_email/adapter.py` maps an email sender to a `SourceType` THEN coordinator email senders SHALL map to `SourceType.PLACEMENT_CELL_EMAIL` or a new `SourceType.COORDINATOR_EMAIL`, and student email senders SHALL map to a student email source type, never to a `*_WHATSAPP` type

2.13 WHEN the `ingestion/` package is initialized THEN `ingestion/__init__.py` SHALL contain a module docstring describing the package's purpose and its public components, consistent with all other packages

2.14 WHEN the `scripts/` directory is part of the project THEN it SHALL contain an `__init__.py` file (even if empty with a docstring) to make it a proper Python package

2.15 WHEN `api/main.py` starts the application THEN `init_db()` SHALL only be called in development/testing environments (guarded by `settings.debug`) and Alembic migrations SHALL be the sole schema-management mechanism in production, preventing dual-schema-management conflicts

**Python Backend — Error Handling**

2.16 WHEN `api/routes/eligibility.py` catches a registration duplicate THEN the system SHALL catch `sqlalchemy.exc.IntegrityError` specifically (not bare `Exception`) so genuine database errors are not silently swallowed

2.17 WHEN `api/main.py` registers startup logic THEN the system SHALL use the `lifespan` async context manager pattern (`@asynccontextmanager` + `app = FastAPI(lifespan=lifespan)`) instead of the deprecated `@app.on_event("startup")` decorator

**Frontend — TypeScript / React Quality**

2.18 WHEN the Axios interceptor in `frontend/src/lib/api.ts` reads the JWT token THEN it SHALL import and use the `getToken()` helper from `@/lib/auth` (which already centralizes the `TOKEN_KEY` constant) rather than duplicating the magic string `"pg_token"`

2.19 WHEN `frontend/src/app/dashboard/page.tsx` defines `loadDrives` THEN the function SHALL be wrapped in `useCallback` with `filter` as a dependency, and the `useEffect` SHALL declare both `loadDrives` and `isLoggedIn` properly instead of suppressing the lint warning with `// eslint-disable-line`

2.20 WHEN `frontend/src/app/drive/[driveId]/page.tsx` declares state variables THEN alignment whitespace in `useState` declarations SHALL be consistent (single space after `=`), conforming to the project's Prettier configuration

2.21 WHEN `frontend/src/components/StatusBadge.tsx` defines the component prop type THEN the component SHALL accept `{ status: Status }` (using the locally defined `Status` union type) rather than `{ status: string }`, enabling TypeScript exhaustiveness checking

2.22 WHEN `frontend/src/app/drive/[driveId]/page.tsx` reads `params.driveId` THEN the code SHALL validate that `driveId` is a non-empty string and redirect or show an error if it is absent, rather than silently casting `undefined` to the string `"undefined"`

2.23 WHEN the Next.js configuration file is maintained THEN `next.config.js` SHALL be renamed to `next.config.ts` and typed with `import type { NextConfig }` to be consistent with `tailwind.config.ts` and the project's TypeScript-first convention

**Frontend — Accessibility**

2.24 WHEN the login form renders input fields THEN each `<input>` SHALL have an `id` attribute and its corresponding `<label>` SHALL use `htmlFor` matching that `id`, satisfying WCAG 1.3.1 (Info and Relationships) for screen reader users

---

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a valid JWT token is present and `JWT_SECRET` is properly configured THEN the system SHALL CONTINUE TO authenticate requests and return the correct student profile from `GET /auth/me`

3.2 WHEN a placement notice is submitted to `POST /ingest/notice` with valid inputs THEN the system SHALL CONTINUE TO extract facts via the LLM, persist them to the facts table, run reconciliation, and return the correct `facts_extracted` and `criteria_reconciled` counts

3.3 WHEN `POST /eligibility/check` is called by an eligible student THEN the system SHALL CONTINUE TO create a `Registration` record (write-once), return `status = "ELIGIBLE"`, and include the `registration_link` in the response

3.4 WHEN `POST /eligibility/check` is called by an ineligible student THEN the system SHALL CONTINUE TO return `status = "INELIGIBLE"` with the correct per-criterion `FAIL` reasons and no `registration_link`

3.5 WHEN two facts for the same `(drive_id, criterion_type, scope)` come from different authority ranks THEN the reconciliation engine SHALL CONTINUE TO select the higher-authority fact regardless of timestamp

3.6 WHEN a `min_cgpa` criterion is evaluated against a student with a `null` CGPA THEN the evaluator SHALL CONTINUE TO return `status = "UNKNOWN"` with the appropriate message

3.7 WHEN `GET /drives` is called THEN the system SHALL CONTINUE TO return all drives, optionally filtered by status, with correct pagination

3.8 WHEN `GET /timeline/{drive_id}` is called by an authenticated student THEN the system SHALL CONTINUE TO return the full chronological fact log and current reconciled criteria; the `registration_link` SHALL CONTINUE TO be withheld unless the student has already registered

3.9 WHEN the Gemini provider is configured and a USN-login request is made THEN the system SHALL CONTINUE TO sign a JWT and return it in the `LoginResponse`, unaffected by any changes to OpenAI/Claude temperature defaults

3.10 WHEN `criterion_type = "allowed_branches"` is evaluated with a list value such as `["CSE", "ISE"]` THEN the evaluator SHALL CONTINUE TO return `PASS` for a student in CSE and `FAIL` for a student in MECH

3.11 WHEN the evaluation harness `eval/run_eval.py` is executed THEN it SHALL CONTINUE TO print per-case pass/fail results and the overall accuracy, macro-F1, and latency metrics without requiring LLM credentials

3.12 WHEN the frontend login page is submitted with a valid USN and date of birth THEN the system SHALL CONTINUE TO call `POST /auth/login`, save the session token, and redirect to `/dashboard`

3.13 WHEN the `StatusBadge` component receives `status = "active"` or `status = "ELIGIBLE"` THEN it SHALL CONTINUE TO render the correct colour-coded badge with the status label

3.14 WHEN `GET /auth/me` is called with a valid bearer token THEN the system SHALL CONTINUE TO return the student's USN, name, branch, CGPA, and other profile fields

3.15 WHEN `POST /students` is called with a valid `StudentCreateRequest` body THEN the system SHALL CONTINUE TO create the student record and return a `201` response with the student profile
