#Requires -Version 5.1
<#
.SYNOPSIS
    Fully automated Windows setup for OWASP Dependency Scanner.
.DESCRIPTION
    Auto-installs Python, Node.js, Java via winget, downloads OWASP Dependency Check,
    creates directories, installs packages, and generates .env.
    Run as Administrator (required for C:\ writes and winget).
#>

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'

$ROOT       = $PSScriptRoot
$DC_VERSION = "10.0.4"
$DC_DIR     = "C:\dependency-check"
$DC_DATA    = "C:\dependency-check-data"
$UPLOAD_DIR = Join-Path $env:USERPROFILE "owasp-scanner\uploads"
$REPORT_DIR = Join-Path $env:USERPROFILE "owasp-scanner\reports"
$DATA_DIR   = Join-Path $ROOT "backend\data"

function Write-Step  { param($n, $total, $msg) Write-Host "`n[$n/$total] $msg" -ForegroundColor Cyan }
function Write-OK    { param($msg) Write-Host "  [OK] $msg" -ForegroundColor Green  }
function Write-Info  { param($msg) Write-Host "  [>>] $msg" -ForegroundColor Yellow }
function Write-Err   { param($msg) Write-Host "  [!!] $msg" -ForegroundColor Red    }

function Ensure-Package {
    param($WingetId, $DisplayName, $TestCmd)
    if (Get-Command $TestCmd -ErrorAction SilentlyContinue) {
        $ver = (& $TestCmd --version 2>&1) | Select-Object -First 1
        Write-OK "$DisplayName already installed: $ver"
        return
    }
    Write-Info "Installing $DisplayName via winget..."
    winget install --id $WingetId --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Err "winget install failed for $DisplayName. Install manually then re-run."
        exit 1
    }
    # Refresh PATH in current session
    $machinePath = [System.Environment]::GetEnvironmentVariable("PATH", "Machine")
    $userPath    = [System.Environment]::GetEnvironmentVariable("PATH", "User")
    $env:PATH    = "$machinePath;$userPath"
    Write-OK "$DisplayName installed."
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host "  OWASP Dependency Scanner - Automated Windows Setup"        -ForegroundColor Magenta
Write-Host "============================================================" -ForegroundColor Magenta

# ── Step 1: Prerequisites ─────────────────────────────────────────────────────
Write-Step 1 7 "Checking prerequisites (Python, Node.js, Java)..."

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Err "winget not found. Install 'App Installer' from the Microsoft Store then re-run."
    exit 1
}

Ensure-Package "Python.Python.3.12"             "Python 3.12"        "python"
Ensure-Package "OpenJS.NodeJS.LTS"              "Node.js LTS"        "node"
Ensure-Package "EclipseAdoptium.Temurin.21.JDK" "Java 21 (Temurin)" "java"

$pyVer   = (python --version 2>&1) | Select-Object -First 1
$nodeVer = node --version
$javaVer = (java -version 2>&1)   | Select-Object -First 1
Write-OK "Python : $pyVer"
Write-OK "Node   : $nodeVer"
Write-OK "Java   : $javaVer"

# ── Step 2: OWASP Dependency Check ───────────────────────────────────────────
Write-Step 2 7 "Setting up OWASP Dependency Check $DC_VERSION..."

$dcBat = Join-Path $DC_DIR "bin\dependency-check.bat"
if (Test-Path $dcBat) {
    Write-OK "Already installed at $DC_DIR"
} else {
    $zipUrl  = "https://github.com/jeremylong/DependencyCheck/releases/download/v$DC_VERSION/dependency-check-$DC_VERSION-release.zip"
    $zipPath = Join-Path $env:TEMP "dependency-check-$DC_VERSION.zip"

    Write-Info "Downloading dependency-check-$DC_VERSION-release.zip..."
    try {
        Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing
    } catch {
        Write-Err "Download failed: $_"
        Write-Err "Download manually from https://github.com/jeremylong/DependencyCheck/releases"
        Write-Err "and extract so that $dcBat exists."
        exit 1
    }

    Write-Info "Extracting to C:\..."
    Expand-Archive -Path $zipPath -DestinationPath "C:\" -Force
    Remove-Item $zipPath -Force

    if (-not (Test-Path $dcBat)) {
        Write-Err "Extraction done but $dcBat not found. Check the archive structure."
        exit 1
    }
    Write-OK "OWASP Dependency Check installed at $DC_DIR"
}

# ── Step 3: Directories ───────────────────────────────────────────────────────
Write-Step 3 7 "Creating application directories..."

foreach ($dir in @($UPLOAD_DIR, $REPORT_DIR, $DC_DATA, $DATA_DIR)) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-OK "Created : $dir"
    } else {
        Write-OK "Exists  : $dir"
    }
}

# ── Step 4: Python venv + packages ───────────────────────────────────────────
Write-Step 4 7 "Setting up Python backend..."

$venvPath = Join-Path $ROOT "backend\.venv"
$venvPy   = Join-Path $venvPath "Scripts\python.exe"
$venvPip  = Join-Path $venvPath "Scripts\pip.exe"

if (-not (Test-Path $venvPy)) {
    Write-Info "Creating virtual environment..."
    python -m venv $venvPath
    Write-OK "Virtual environment created."
} else {
    Write-OK "Virtual environment already exists."
}

Write-Info "Upgrading pip..."
& $venvPip install --upgrade pip --quiet

Write-Info "Installing Python packages (this may take a minute)..."
& $venvPip install -r (Join-Path $ROOT "backend\requirements.txt") --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Info "Retrying with prebuilt wheels only..."
    & $venvPip install -r (Join-Path $ROOT "backend\requirements.txt") --only-binary ":all:" --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Err "pip install failed. Check output above."
        exit 1
    }
}
Write-OK "Python packages installed."

# ── Step 5: npm packages ──────────────────────────────────────────────────────
Write-Step 5 7 "Installing frontend npm packages..."

$frontendDir = Join-Path $ROOT "frontend"
Push-Location $frontendDir
try {
    npm install 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "npm install exited with code $LASTEXITCODE" }
    Write-OK "Frontend packages installed."
} catch {
    Pop-Location
    Write-Err "npm install failed: $_"
    exit 1
}
Pop-Location

# ── Step 6: Generate .env ─────────────────────────────────────────────────────
Write-Step 6 7 "Configuring environment file (.env)..."

$envPath = Join-Path $ROOT ".env"

if (Test-Path $envPath) {
    Write-OK ".env already exists - skipping generation."
} else {
    $secretKey = & $venvPy -c "import secrets; print(secrets.token_hex(32))"

    Write-Host ""
    Write-Host "  Anthropic API key is needed for AI false-positive analysis." -ForegroundColor Yellow
    Write-Host "  Get one at: https://console.anthropic.com"                   -ForegroundColor Yellow
    Write-Host "  Leave blank to skip AI (can be added later in .env)."        -ForegroundColor Yellow
    Write-Host ""
    $anthropicKey = Read-Host "  Enter ANTHROPIC_API_KEY"

    # Build .env lines as an array - avoids here-string encoding issues
    $lines = @(
        "# OWASP Dependency Scanner - Environment (Windows)",
        "# Auto-generated by setup-windows.ps1",
        "",
        "SECRET_KEY=$secretKey",
        "ACCESS_TOKEN_EXPIRE_MINUTES=60",
        "",
        "DATABASE_URL=sqlite:///./data/app.db",
        "",
        "ANTHROPIC_API_KEY=$anthropicKey",
        "",
        "OWASP_DC_PATH=$DC_DIR\bin\dependency-check.bat",
        "OWASP_DC_DATA_DIR=$DC_DATA",
        "",
        "UPLOAD_DIR=$UPLOAD_DIR",
        "REPORTS_DIR=$REPORT_DIR",
        "",
        "AZURE_ORG_URL=",
        "AZURE_PAT=",
        "",
        "JENKINS_URL=",
        "JENKINS_USER=",
        "JENKINS_TOKEN=",
        "",
        "AWS_ACCESS_KEY_ID=",
        "AWS_SECRET_ACCESS_KEY=",
        "AWS_REGION=us-east-1"
    )

    $lines | Set-Content -Path $envPath -Encoding UTF8
    Write-OK ".env written with auto-generated SECRET_KEY."
    Write-OK "SECRET_KEY prefix: $($secretKey.Substring(0, 8))..."
}

# ── Step 7: Verify ───────────────────────────────────────────────────────────
Write-Step 7 7 "Verifying installation..."

$uvicornExe    = Join-Path $venvPath "Scripts\uvicorn.exe"
$nodeModules   = Join-Path $ROOT "frontend\node_modules"

$checks = @(
    [PSCustomObject]@{ Label = "Python venv (uvicorn)"; OK = (Test-Path $uvicornExe) },
    [PSCustomObject]@{ Label = "OWASP DC bat";          OK = (Test-Path $dcBat)      },
    [PSCustomObject]@{ Label = "Upload dir";            OK = (Test-Path $UPLOAD_DIR) },
    [PSCustomObject]@{ Label = "Reports dir";           OK = (Test-Path $REPORT_DIR) },
    [PSCustomObject]@{ Label = ".env file";             OK = (Test-Path $envPath)    },
    [PSCustomObject]@{ Label = "node_modules";          OK = (Test-Path $nodeModules) }
)

$allOk = $true
foreach ($c in $checks) {
    if ($c.OK) {
        Write-OK $c.Label
    } else {
        Write-Err "$($c.Label) - NOT FOUND"
        $allOk = $false
    }
}

# ── Done ─────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================================" -ForegroundColor Magenta

if ($allOk) {
    Write-Host "  Setup complete!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Start the app:  start-windows.bat"   -ForegroundColor White
    Write-Host ""
    Write-Host "  Or manually:"
    Write-Host "    Terminal 1:  cd backend  && .venv\Scripts\activate && uvicorn app.main:app --reload --port 8000"
    Write-Host "    Terminal 2:  cd frontend && npm run dev"
    Write-Host ""
    Write-Host "  App:       http://localhost:3000"
    Write-Host "  API docs:  http://localhost:8000/docs"
} else {
    Write-Host "  Setup finished with errors - review [!!] messages above." -ForegroundColor Red
}

Write-Host "============================================================" -ForegroundColor Magenta
Write-Host ""
