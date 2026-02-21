# OWASP Dependency Scanner

A full-stack web application for running OWASP Dependency Check scans with AI-powered false positive analysis using Claude Opus 4.6.

## Features

- **File Upload** — Scan JAR, WAR, EAR, ZIP, APK, NUPKG, and more
- **OWASP Dependency Check** — Detects 180,000+ CVEs from the NVD database
- **AI False Positive Reduction** — Claude Opus 4.6 with adaptive thinking analyzes vulnerabilities to identify false positives
- **CI/CD Integration** — Azure DevOps, Jenkins, and AWS CodePipeline support
- **Webhook Endpoint** — Receive scan requests from CI/CD pipelines
- **Severity Dashboard** — Visual breakdown of Critical/High/Medium/Low findings
- **Suppression** — Suppress known false positives per-vulnerability
- **Report Download** — Export full JSON reports

## Quick Start

### Option A — Windows Native (Recommended for local dev)

**Prerequisites:**
- Python 3.11+ — [python.org](https://python.org)
- Node.js 20+ — [nodejs.org](https://nodejs.org)
- Java 11+ — [adoptium.net](https://adoptium.net)
- OWASP Dependency Check — [GitHub Releases](https://github.com/jeremylong/DependencyCheck/releases) (extract to `C:\dependency-check`)

**One-click setup:**
```bat
setup-windows.bat
```

This script will:
1. Verify Python, Node, and Java are installed
2. Download and install OWASP Dependency Check to `C:\dependency-check`
3. Create upload/report directories under `%USERPROFILE%\owasp-scanner\`
4. Create the Python virtual environment and install packages
5. Prompt you to configure `.env` (set `SECRET_KEY` and `ANTHROPIC_API_KEY`)
6. Install frontend npm packages

**Start the app (two terminals):**
```bat
:: Terminal 1 — Backend (http://localhost:8000)
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000

:: Terminal 2 — Frontend (http://localhost:3000)
cd frontend
npm run dev
```

Access the app at **http://localhost:3000** | API docs at **http://localhost:8000/docs**

> **Note:** The first scan downloads the NVD database (~500 MB) to `C:\dependency-check-data`. This takes 10–20 minutes once. Subsequent scans use the cached data.

---

### Option B — Docker (Linux / WSL2)

**Prerequisites:**
- Docker & Docker Compose
- An Anthropic API key

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY and SECRET_KEY at minimum

# 2. Start all services
docker compose up --build
```

Access the app at **http://localhost:3000**

## Architecture

```
┌─────────────────┐     ┌──────────────────────────────────────┐
│   React Frontend │────▶│           FastAPI Backend             │
│  (Nginx, :3000) │     │                                      │
└─────────────────┘     │  ┌────────┐  ┌─────────┐  ┌──────┐ │
                         │  │  Auth  │  │  OWASP  │  │  AI  │ │
                         │  │  JWT   │  │   DC    │  │Claude│ │
                         │  └────────┘  └─────────┘  └──────┘ │
                         │                                      │
                         │  ┌───────────────────────────────┐  │
                         │  │      CI/CD Integrations       │  │
                         │  │   Azure  │ Jenkins │   AWS    │  │
                         │  └───────────────────────────────┘  │
                         └──────────────────────────────────────┘
                                          │
                                   SQLite Database
```

## CI/CD Integration

### Webhook
POST artifact URLs to trigger scans from your pipeline:

```bash
curl -X POST http://your-server:3000/api/integrations/webhook/TOKEN \
  -H "Content-Type: application/json" \
  -d '{
    "source": "jenkins",
    "project_name": "my-app-v1.2.3",
    "artifact_url": "https://your-nexus/my-app-1.2.3.jar"
  }'
```

### Supported CI/CD Systems
| System | Trigger Method |
|--------|---------------|
| Azure DevOps | REST API (PAT auth) |
| Jenkins | Remote Access API |
| AWS CodePipeline | StartPipelineExecution API |

## AI Analysis

The AI analysis uses **Claude Opus 4.6 with adaptive thinking** to:
1. Analyze each CVE against the affected dependency
2. Detect common false positive patterns (CPE mismatches, platform-specific issues, etc.)
3. Return a confidence score and reasoning for each finding
4. Provide remediation guidance for confirmed vulnerabilities

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register` | POST | Create account |
| `/api/auth/login` | POST | Login, get JWT |
| `/api/scans/upload` | POST | Upload file for scanning |
| `/api/scans/` | GET | List all scans |
| `/api/scans/{id}` | GET | Get scan + vulnerabilities |
| `/api/scans/{id}/analyze` | POST | AI false-positive analysis |
| `/api/scans/{id}/vulnerabilities/{vid}/suppress` | PATCH | Toggle suppression |
| `/api/scans/{id}/report` | GET | Download JSON report |
| `/api/integrations/` | GET/POST | Manage CI/CD integrations |
| `/api/integrations/{id}/trigger` | POST | Trigger a pipeline |
| `/api/integrations/webhook/{token}` | POST | Receive CI/CD webhooks |

Interactive API docs available at **http://localhost:8000/docs**

## Development

### Backend (Windows)
```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
:: Copy .env.example to backend\.env and configure it
uvicorn app.main:app --reload --port 8000
```

### Frontend (Windows)
```bat
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` calls to `http://localhost:8000` automatically.
No `VITE_API_URL` override needed for local Windows dev.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | JWT signing key (random 32+ chars) |
| `ANTHROPIC_API_KEY` | For AI | Claude API key |
| `AZURE_PAT` | For Azure | Azure DevOps Personal Access Token |
| `JENKINS_TOKEN` | For Jenkins | Jenkins API Token |
| `AWS_ACCESS_KEY_ID` | For AWS | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | For AWS | AWS credentials |
