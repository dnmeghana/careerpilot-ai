# CareerPilot

## Project Overview

CareerPilot is a full-stack career workspace for organizing resumes, saved job opportunities, applications, interview preparation, mock interviews, skill gaps, and resume-to-job analysis.

It is designed to keep a job search in one authenticated workspace. The application currently uses local analysis and interview-generation implementations by default, with an optional OpenAI-compatible provider configured through environment variables.

## Problem Statement

Job searches often spread information across resumes, job boards, notes, spreadsheets, and interview-preparation documents. CareerPilot brings those records together so a user can compare a resume with a role, track application progress, prepare for interviews, practice answers, and review career analytics in one place.

## Features

- Account registration, login, bearer-token authentication, session restoration, and logout.
- Resume PDF upload, text extraction, active-resume selection, listing, and deletion.
- Job creation, editing, listing, viewing, and deletion.
- Application tracking with statuses including wishlist, applied, screening, interview, technical interview, final round, offer, and rejected.
- Application search, filtering, sorting, and table/board views.
- Resume-to-job analysis with match percentage, matching skills, missing skills, keywords, recommendations, and improvement suggestions.
- Skill-gap visualization based on analysis results.
- Interview preparation plans with generated questions, notes, regeneration, and completion tracking.
- Mock interviews with answer evaluation, scores, feedback, strengths, weaknesses, and recommendations.
- AI career assistant using the authenticated user's resume, jobs, applications, skill gaps, and interview context.
- Dashboard analytics for application totals, offers, rejections, interviews, upcoming interviews, skill gaps, and recent activity.
- Synthetic development seed data that is opt-in and never runs during application startup.
- **V2 Agentic Job Application Automation**:
  - Resilient Playwright browser automation engine for career portals.
  - Multi-company adapter architecture (Generic adapter, Greenhouse/Lever/Workday/Taleo support, extensible BaseAdapter).
  - 12-state transition engine with pause, resume, cancel, and human-in-the-loop interventions.
  - Self-healing Scenario Memory: learns unknown form fields and saves reusable, user-approved patterns.
  - AI reasoning agent with DOM context extractor and deterministic local fallback.
  - Candidate application profile with normalized personal, contact, work authorization, and demographic fields.
  - Comprehensive safety guards: hard pause on CAPTCHA/bot challenges, auto-pause on sensitive/legal/demographic questions, and approval required for final submission.
  - Automation dashboard with live run tracker, human intervention queue, scenario memory editor, and profile settings.
  - Periodic background scheduler with daily application rate-limiting and duplicate prevention.

## Technology Stack

### Frontend

- React 19 and TypeScript
- Vite
- React Router
- Axios
- Recharts
- Tailwind CSS
- Vitest, Testing Library, and jsdom

### Backend

- Python 3.11+
- FastAPI
- Pydantic and Pydantic Settings
- SQLAlchemy 2
- Alembic
- PostgreSQL through `psycopg`
- `pypdf` for PDF text extraction
- `pwdlib` with Argon2 for password hashing
- PyJWT for access tokens
- Pytest and HTTPX for tests

## Architecture

The primary request path is:

```text
React
  |
  v
FastAPI
  |
  v
SQLAlchemy
  |
  v
PostgreSQL
```

The application also has a separate analysis path:

```text
Resume/Job Data
      |
      v
AI Service
      |
      v
Career Analysis
```

The AI service selects an optional OpenAI-compatible HTTP provider when configured. Otherwise, it uses local implementations for resume analysis, interview questions, answer evaluation, and assistant responses. Provider responses are parsed and validated before they are returned or stored.

```mermaid
flowchart TD
    Browser[React frontend] -->|Bearer HTTP requests| API[FastAPI API]
    API --> Auth[Authentication and ownership checks]
    API --> Services[Domain services]
    Services --> ORM[SQLAlchemy]
    ORM --> DB[(PostgreSQL)]
    Services --> Local[Local analysis and interview logic]
    Services --> Optional[Optional OpenAI-compatible provider]
    Local --> Results[Career analysis and preparation results]
    Optional --> Results
```

## Folder Structure

```text
careerpilot-ai/
├── .env.example
├── README.md
├── backend/
│   ├── app/
│   │   ├── auth.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── seed_demo.py
│   │   ├── routers/
│   │   └── services/
│   ├── migrations/
│   ├── tests/
│   ├── requirements.txt
│   └── alembic.ini
└── frontend/
    ├── src/
    │   ├── App.tsx
    │   ├── components/
    │   ├── lib/
    │   └── test/
    ├── public/
    ├── package.json
    └── vite.config.ts
```

## Database Design

The SQLAlchemy models represent the following main entities:

- `users`: account identity and password hash.
- `resumes`: uploaded PDF metadata and extracted text, owned by a user.
- `jobs`: saved job opportunities, owned by a user.
- `applications`: a user's tracking record for a job, including status, dates, salary, recruiter details, and notes.
- `skills`: normalized skill names.
- `resume_skills` and `job_skills`: many-to-many resume and job skill relationships.
- `skill_gaps`: prioritized missing skills for a user, resume, and job combination.
- `interviews` and `interview_questions`: interview preparation plans and generated questions.
- `mock_interviews` and `mock_interview_answers`: practice sessions, answer scores, and feedback.
- `ai_analyses`: stored resume/job analysis results.

Foreign keys and ownership fields scope user data. Relationships use cascading deletes for user-owned records where appropriate. Schema creation and updates are managed with Alembic migrations; the API does not create tables during startup.

## API Overview

The API is served under `/api`. FastAPI generates interactive documentation at `/docs` and an OpenAPI document at `/openapi.json`.

| Area | Endpoints |
| --- | --- |
| Health | `GET /api/health` |
| Authentication | `POST /api/auth/register`, `POST /api/auth/login` |
| Users | `GET /api/auth/me` |
| Resumes | `POST /api/resumes`, `GET /api/resumes`, `GET /api/resumes/{id}`, `PUT /api/resumes/{id}/active`, `DELETE /api/resumes/{id}` |
| Jobs | `POST /api/jobs`, `GET /api/jobs`, `GET /api/jobs/{id}`, `PUT /api/jobs/{id}`, `DELETE /api/jobs/{id}` |
| Applications | `POST /api/applications`, `GET /api/applications`, `GET /api/applications/{id}`, `PUT /api/applications/{id}`, `DELETE /api/applications/{id}` |
| Analysis | `POST /api/analysis/resume-job` |
| Skills | `GET /api/analysis/skill-gap` |
| Interviews | `POST /api/interviews`, `GET /api/interviews`, `GET /api/interviews/{id}`, `PATCH /api/interviews/{id}`, `POST /api/interviews/{id}/regenerate` |
| Mock Interviews | `POST /api/mock-interviews`, `GET /api/mock-interviews`, `GET /api/mock-interviews/{id}`, `POST /api/mock-interviews/{id}/answers/{answer_id}` |
| AI Assistant | `POST /api/assistant/chat` |
| Analytics | `GET /api/dashboard` |
| Automation | `GET/PUT /api/automation/profile`, `GET /api/automation/runs`, `GET /api/automation/runs/{id}`, `POST /api/automation/runs/trigger`, `POST /api/automation/runs/{id}/pause`, `POST /api/automation/runs/{id}/resume`, `POST /api/automation/runs/{id}/intervene`, `GET/PATCH/DELETE /api/automation/scenarios`, `GET/PUT /api/automation/settings` |

All protected routes require a bearer access token. Resource lookups include the authenticated user's ID, so another user's resources are not exposed through an ID alone.

## Authentication Approach

1. A user registers or logs in through `/api/auth/register` or `/api/auth/login`.
2. The backend hashes passwords with Argon2 through `pwdlib` and never returns password hashes.
3. The backend issues a signed JWT containing the user ID subject and an expiration time.
4. The frontend stores the access token in `sessionStorage` and Axios sends it as `Authorization: Bearer <token>`.
5. Protected backend routes depend on `get_current_user`, which validates the token and loads the user.
6. A `401` response clears the frontend session and dispatches an unauthorized event.

The JWT secret must be provided through `JWT_SECRET` in production. The backend also accepts the legacy `JWT_SECRET_KEY` variable for compatibility. If no development secret is provided, a random per-process development secret is generated.

## AI Integration

AI integration is isolated in `backend/app/services/ai_service.py`.

- Local implementations are used when no provider is configured.
- The optional remote adapter expects an OpenAI-compatible JSON API.
- `AI_PROVIDER=openai_compatible`, `AI_API_URL`, `AI_API_KEY`, and `AI_MODEL` select the remote provider.
- Analysis, question-generation, and answer-evaluation responses are validated before use.
- Network, timeout, malformed-response, and unsupported-provider failures fall back to local behavior where supported.

The frontend does not contain or receive the private AI API key. AI credentials are read only by the backend.

## Local Development Setup

### Prerequisites

- Node.js 20+
- Python 3.11+
- PostgreSQL 14+ or another reachable PostgreSQL-compatible development database

### Configure the environment

The root `.env.example` documents the combined configuration contract. For local
execution, copy the service-specific examples because the backend loads `.env`
from the `backend` working directory and Vite loads it from `frontend`:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Use real local values in ignored `.env` files. Never commit them.

Create the PostgreSQL database named in `DATABASE_URL` before running the
migrations. For the default local URL, one possible command is:

```bash
createdb careerpilot
```

The database user, password, host, and port must match `DATABASE_URL`.

## Environment Variables

### Backend

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy database URL, such as `postgresql+psycopg://user:password@host:5432/careerpilot`. |
| `JWT_SECRET` | Secret used to sign access tokens. Required to be at least 32 characters in production. |
| `AI_API_KEY` | Private key for the optional backend AI provider. Never put this in the frontend. |
| `AI_MODEL` | Model name sent to the optional AI provider. |
| `FRONTEND_URL` | Allowed frontend origin for CORS. Production must use HTTPS. |
| `ENVIRONMENT` | Environment name, such as `development` or `production`. |
| `AI_PROVIDER` | Set to `openai_compatible` to enable the remote adapter. |
| `AI_API_URL` | URL of the OpenAI-compatible provider endpoint. |
| `JWT_ALGORITHM` | JWT signing algorithm; defaults to `HS256`. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token lifetime. |

### Frontend

| Variable | Purpose |
| --- | --- |
| `VITE_API_URL` | Public backend API base URL, for example `http://localhost:8000/api` locally or the deployed API URL in production. |

Only `VITE_*` variables are exposed to Vite client code. Do not place `AI_API_KEY`, `JWT_SECRET`, database credentials, or other private values in frontend environment files.

## Running the Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
.venv/bin/alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

The API runs at `http://localhost:8000`. Interactive API documentation is
available at `http://localhost:8000/docs`; check availability with:

```bash
curl http://localhost:8000/api/health
```

## Running the Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The Vite development server normally runs at `http://localhost:5173`. Set `VITE_API_URL` in `frontend/.env` if the backend is running elsewhere.

## Running Tests

Backend tests:

```bash
cd backend
PYTHONPATH=. .venv/bin/python -m pytest -q
```

Frontend tests, build, and lint:

```bash
cd frontend
npm test -- --run
npm run build
npm run lint
```

The backend tests use isolated database fixtures. The frontend tests use Vitest, jsdom, React Testing Library, and mocked API boundaries.

## Demo Data

Synthetic development data is opt-in. It is never created when the API starts and is disabled for production and staging environments.

After running migrations from `backend`:

```bash
.venv/bin/python -m app.seed_demo --confirm
```

The seed creates one synthetic account, resumes, jobs, varied application statuses, skills, skill gaps, interview preparation questions, a completed mock interview, and resume/job analysis data. Rerunning it replaces only the synthetic demo account.

The local demo credentials are printed by the command. They are for development only and must not be reused in a deployed environment.

## V2 Agentic Job Application Automation Platform

CareerPilot V2 extends the core platform with autonomous browser automation, company career portal adapters, scenario-based self-healing memory, and strict human-in-the-loop safety.

```mermaid
flowchart TD
    User[User / Background Scheduler] -->|Trigger Run| Engine[Automation Engine]
    Engine --> SM[12-State Machine]
    SM --> Adapter[Company Adapter Registry]
    Adapter --> Portal[Career Portal Page via Playwright]
    Portal --> FormState[Form Analysis]
    FormState -->|Match Pattern| ScenReg[Scenario Registry]
    FormState -->|Unknown Field| AIDOM[DOM Extractor + AI Agent]
    AIDOM --> Confidence[Confidence Evaluator]
    Confidence -->|HIGH >= 0.85| AutoFill[Auto-fill Field]
    Confidence -->|MEDIUM/LOW < 0.85| HITL[Pause & Await Human Input]
    FormState -->|CAPTCHA / Bot Detected| HardStop[Pause: Manual Action Required]
    FormState -->|Demographic / Legal / Sensitive| SafetyGuard[Pause: User Review Required]
    HITL --> UserInput[User Answers in Dashboard]
    UserInput --> Memory[Self-Healing Scenario Memory]
    Memory --> ScenReg
    AutoFill --> FinalCheck{Auto-submit Enabled?}
    FinalCheck -->|No default| ConfirmSubmit[Pause: Final Review Required]
    FinalCheck -->|Yes| Submit[Submit Application]
    ConfirmSubmit --> UserConfirm[User Approves Submission]
    UserConfirm --> Submit
    Submit --> Success[Update Application to APPLIED & Save Run]
```

### Key Architectural Pillars

1. **State Machine (`app/automation/state_machine.py`)**:
   Enforces a deterministic 12-state lifecycle: `DISCOVERED`, `APPLICATION_STARTED`, `PORTAL_OPENED`, `FORM_IN_PROGRESS`, `FILL_FIELDS`, `UPLOAD_RESUME`, `UNKNOWN_SCENARIO`, `AI_RESOLUTION`, `WAITING_FOR_USER`, `REVIEW_REQUIRED`, `SUBMITTED`, `FAILED`, and `PAUSED`. Every state change is recorded with timestamps and actionable messages.

2. **Generic & Company-Specific Adapters (`app/automation/companies/`)**:
   - `BaseCompanyAdapter`: Standard interface defining `can_handle()`, `extract_job_details()`, `fill_personal_info()`, `upload_resume()`, `fill_experience()`, `fill_questions()`, `handle_multi_page()`, and `submit_application()`.
   - `GenericCompanyAdapter`: Uses resilient, multi-tiered semantic heuristics (labels, ARIA roles, names, placeholders, IDs) to handle any modern job portal (Greenhouse, Lever, Workday, Taleo, etc.).
   - `CompanyAdapterRegistry`: Registers and selects the best adapter by URL matching or name priority.

3. **Confidence-Driven Decision Engine (`app/automation/confidence.py`)**:
   - Scores every action: `HIGH` (0.85 - 1.0), `MEDIUM` (0.60 - 0.84), `LOW` (0.00 - 0.59).
   - High confidence with non-sensitive fields executes autonomously.
   - Low/Medium confidence, sensitive fields, or unknown dropdowns pause with `WAITING_FOR_USER` to prevent errors.

4. **Scenario Memory & Self-Healing (`app/automation/scenarios/`)**:
   - Solves the brittle-selector problem of traditional web scrapers.
   - When an unknown question is encountered, the DOM context is extracted and human feedback is requested.
   - Once answered, the pattern is persisted in PostgreSQL as a reusable `AutomationScenario`.
   - Subsequent applications matching the page signature or field key reuse the verified answer without re-prompting.

5. **AI Reasoning Agent (`app/automation/ai/`)**:
   - `DOMContextExtractor`: Extracts clean, sanitized form context (labels, surrounding text, input types, options, aria attributes).
   - `AutomationAIAgent`: Evaluates the context against the candidate's profile and returns structured recommendations (`action_type`, `target_value`, `confidence`, `confidence_reason`).
   - Automatically falls back to deterministic local rule evaluation when no remote LLM API key is present.

6. **Safety & Responsible Automation Guarantees (`app/automation/safety.py`)**:
   - **Zero CAPTCHA / Bot Challenge Bypass**: Never attempts to bypass Cloudflare, reCAPTCHA, or hCaptcha. Immediately pauses with clear status `"Manual action required: CAPTCHA / Bot verification"`.
   - **No Hallucinated Candidate Information**: Never guesses unprovided candidate data. Missing information transitions to human intervention.
   - **Demographic & Legal Question Protection**: EEO, diversity, veteran, disability, and non-compete questions require explicit opt-in and user approval.
   - **Default Final Submission Gate**: `auto_submit` is disabled by default. Applications require the user to review the filled form and click "Submit".

7. **Background Scheduler (`app/automation/scheduler.py`)**:
   - Runs asynchronous background checks for newly discovered jobs.
   - Prevents duplicate applications to the same job.
   - Respects user-configured daily limits (`max_daily_applications`) and action delays (`delay_between_actions_ms`).

### Playwright Browser Setup

Playwright is required for browser automation. After installing python requirements:

```bash
cd backend
.venv/bin/playwright install chromium
```

### Automation Test Suite (Unit & 12 Scenario Tests)

The test suite covers all 12 edge cases against an in-memory HTTP mock portal:

```bash
cd backend
PYTHONPATH=. .venv/bin/python -m pytest tests/test_automation_playwright_scenarios.py -v
PYTHONPATH=. .venv/bin/python -m pytest tests/test_automation_unit.py -v
```

Scenarios verified:
1. `test_scenario_1_standard_application_flow`: Clean multi-field form completion.
2. `test_scenario_2_file_upload_resume`: Resume PDF attachment to input[type=file].
3. `test_scenario_3_multi_page_application`: Stepped form navigation (Next -> Submit).
4. `test_scenario_4_unknown_form_field_hitl`: Pause and scenario memory learning on novel fields.
5. `test_scenario_5_captcha_bot_challenge_pause`: Immediate hard stop on CAPTCHA.
6. `test_scenario_6_dynamic_dropdown_and_radio`: Native and custom selects/radio groups.
7. `test_scenario_7_validation_error_recovery`: Form validation error detection and self-healing.
8. `test_scenario_8_session_timeout_handling`: Session expiration detection without crash.
9. `test_scenario_9_work_authorization_sponsorship`: Sensitive legal guard pause.
10. `test_scenario_10_voluntary_demographic_disclosure`: EEO/Demographic opt-in pause.
11. `test_scenario_11_duplicate_application_prevention`: Duplicate submission prevention.
12. `test_scenario_12_human_intervention_resume`: Dashboard human intervention approval and execution.

## Deployment Instructions

The repository does not include a provider-specific deployment manifest. A deployment should provide the following application-level steps:

1. Install frontend dependencies, set `VITE_API_URL` to the public HTTPS API base URL, and build the frontend with `npm run build`. Serve the generated `frontend/dist` assets through a static host or web server.
2. Run the backend with a production ASGI process, for example `uvicorn app.main:app --host 0.0.0.0 --port 8000`, behind a reverse proxy or managed service.
3. Set `ENVIRONMENT=production`.
4. Set a unique random `JWT_SECRET` of at least 32 characters.
5. Set a production `DATABASE_URL` and run `.venv/bin/alembic upgrade head` before starting the API.
6. Set `FRONTEND_URL` to the exact HTTPS frontend origin.
7. Set `VITE_API_URL` at frontend build time to the public HTTPS API base URL.
8. Keep `AI_API_KEY` and database credentials in the deployment secret manager, never in frontend assets or committed files.
9. Do not run the demo seed against production or staging databases.

Production TLS termination, process supervision, database backups, monitoring, and secret-manager configuration depend on the hosting platform and are not provided by this repository.

## Future Improvements

Potential next steps, consistent with the current architecture, include:

- Add provider-specific deployment configurations and CI workflows.
- Add refresh-token or server-managed session rotation if longer-lived sessions are needed.
- Add pagination and query-level analytics aggregation for larger datasets.
- Split the largest frontend route module into page and feature modules.
- Add background processing for large resume files and remote AI requests.
- Add richer job-import integrations and calendar integrations.
- Expand observability with structured request metrics and tracing.
- Add end-to-end browser tests against a disposable backend and database.
# CareerPilot
