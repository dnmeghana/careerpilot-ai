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
