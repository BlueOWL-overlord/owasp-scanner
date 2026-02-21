# GitHub Copilot Instructions — OWASP Dependency Scanner

## Project Overview
Full-stack web application for OWASP Dependency Check scanning with AI-powered false positive reduction using Claude Opus 4.6 (Anthropic). Runs natively on Windows 11.

## Tech Stack
- **Backend**: Python 3.11+, FastAPI, SQLModel (SQLite), python-jose (JWT), anthropic SDK
- **Frontend**: React 18, Vite, TailwindCSS, Axios, React Router, Recharts, Lucide React
- **Scanner**: OWASP Dependency Check CLI (`dependency-check.bat` on Windows)
- **AI**: Anthropic Claude Opus 4.6 (`claude-opus-4-6`) via `anthropic` Python SDK

## Project Structure
```
owasp-scanner/
├── backend/
│   └── app/
│       ├── main.py          # FastAPI app entrypoint — sets WindowsProactorEventLoopPolicy
│       ├── config.py        # Settings via pydantic-settings — auto-detects Windows paths
│       ├── database.py      # SQLModel engine + session
│       ├── auth/            # JWT auth: register, login, get_current_user
│       ├── scanner/
│       │   ├── owasp.py     # Runs dependency-check.bat via asyncio subprocess
│       │   └── router.py    # Upload, analyze, suppress, report endpoints
│       ├── ai/
│       │   └── analyzer.py  # Claude Opus 4.6 false positive analysis
│       └── integrations/    # Azure DevOps, Jenkins, AWS CodePipeline
└── frontend/
    └── src/
        ├── App.jsx          # Protected routes
        ├── pages/           # Login, Dashboard, Scan, Results, Integrations
        ├── components/      # FileUpload, ScanResults, VulnerabilityCard, CicdIntegration
        └── services/api.js  # Axios client with Bearer token injection
```

## Key Conventions

### Backend
- All routes are async FastAPI endpoints using `Depends(get_current_user)` for auth
- Background tasks via `BackgroundTasks` for long-running scans
- Models use SQLModel (combines SQLAlchemy + Pydantic) — `class Foo(SQLModel, table=True)`
- Settings come from `.env` via `app.config.settings` — never hardcode paths
- Windows subprocess: always prefix `dependency-check.bat` calls with `["cmd", "/c"]`
- Use `platform.system() == "Windows"` for OS-specific branching

### Frontend
- Tailwind utility classes only — no custom CSS files beyond `index.css`
- `src/services/api.js` is the single Axios instance — add new API calls there
- Protected routes check `localStorage.getItem('token')` in `App.jsx`
- Severity colours: CRITICAL=red-600, HIGH=orange-500, MEDIUM=yellow-500, LOW=blue-500

### AI Analysis — Privacy Rules (DO NOT BYPASS)
- Model: `claude-opus-4-6` with `thinking` enabled
- Response must be JSON: `{ is_false_positive, confidence, reasoning, risk_summary }`
- Stored in `vulnerability.ai_*` columns
- **ONLY `_build_safe_payload()` in `analyzer.py` may construct the LLM payload**
- Fields sent to Anthropic API: `library_name` (sanitized), `library_version`, `cve_id`, `severity`, `cvss_v2`, `cvss_v3`, `description`, `cwe_ids`
- Fields NEVER sent: `project_name`, `dependency_file`, raw `dependency_name` (may contain paths), any server paths, UUID-prefixed filenames
- `_sanitize_library_name()` strips: OS paths (`os.path.basename`), UUID upload prefix (`re` pattern)

## Common Patterns

### Adding a new backend endpoint
```python
@router.get("/new-endpoint")
async def new_endpoint(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    ...
```

### Adding a new frontend API call (api.js)
```javascript
export const newThing = (id) => api.get(`/api/resource/${id}`)
```

### Running OWASP DC subprocess (Windows)
```python
cmd = ["cmd", "/c", settings.OWASP_DC_PATH, "--scan", file_path, "--format", "JSON", "--out", report_dir]
proc = await asyncio.create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
```

## Environment Variables (Windows)
```
OWASP_DC_PATH=C:\dependency-check\bin\dependency-check.bat
OWASP_DC_DATA_DIR=C:\dependency-check-data
UPLOAD_DIR=C:\Users\<user>\owasp-scanner\uploads
REPORTS_DIR=C:\Users\<user>\owasp-scanner\reports
ANTHROPIC_API_KEY=sk-ant-...
SECRET_KEY=<random 32 char hex>
```

## Dev Commands (Windows)
```bat
:: Backend
cd backend && .venv\Scripts\activate && uvicorn app.main:app --reload --port 8000

:: Frontend
cd frontend && npm run dev
```
