<#
.SYNOPSIS
    Build a standalone Windows MSI installer for OWASP Dependency Scanner.

.DESCRIPTION
    Automates the full build pipeline:
      1. Verify prerequisites (Python, Node.js, WiX v3, PyInstaller)
      2. Build the React frontend  (npm run build)
      3. Bundle the Python backend with PyInstaller
      4. Optionally download + bundle OWASP Dependency Check
      5. Harvest bundled files with WiX heat.exe
      6. Compile + link the MSI with candle.exe / light.exe

.PARAMETER BundleOWASPDC
    Switch. If specified the script downloads OWASP Dependency Check and
    embeds it inside the MSI (adds ~200 MB).  Without the flag the tool is
    NOT bundled; users download it automatically on their first scan.

.PARAMETER SkipFrontendBuild
    Switch. Skip `npm run build` (useful if the frontend is already built).

.PARAMETER SkipPyInstaller
    Switch. Skip PyInstaller (useful when iterating on the installer only).

.PARAMETER Version
    Installer version string (default: 1.0.0).

.EXAMPLE
    # Standard build
    .\build-msi.ps1

    # Bundle OWASP DC for an offline installer
    .\build-msi.ps1 -BundleOWASPDC

    # Re-run only the WiX step (PyInstaller output already exists)
    .\build-msi.ps1 -SkipFrontendBuild -SkipPyInstaller
#>

[CmdletBinding()]
param(
    [switch]$BundleOWASPDC,
    [switch]$SkipFrontendBuild,
    [switch]$SkipPyInstaller,
    [string]$Version = "1.0.0"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Write-Step { param([string]$msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-OK   { param([string]$msg) Write-Host "    OK: $msg" -ForegroundColor Green }
function Write-Warn { param([string]$msg) Write-Host "    WARN: $msg" -ForegroundColor Yellow }
function Fail       { param([string]$msg) Write-Host "`nERROR: $msg" -ForegroundColor Red; exit 1 }

function Require-Command {
    param([string]$cmd, [string]$hint = "")
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        $msg = "Required command not found: $cmd"
        if ($hint) { $msg += "`n       $hint" }
        Fail $msg
    }
    Write-OK "$cmd found"
}

function Require-PythonPackage {
    param([string]$pkg)
    $installed = & python -m pip show $pkg 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Step "Installing Python package: $pkg"
        & python -m pip install $pkg | Out-Null
        if ($LASTEXITCODE -ne 0) { Fail "Failed to install $pkg" }
    }
    Write-OK "Python package $pkg present"
}

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
$Root        = $PSScriptRoot
$BackendDir  = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$InstallerDir= Join-Path $Root "installer"
$DistDir     = Join-Path $BackendDir "dist\owasp-scanner"   # PyInstaller output
$OWASPDCDir  = Join-Path $InstallerDir "dependency-check"   # bundled OWASP DC
$MsiOutput   = Join-Path $Root "owasp-scanner-$Version.msi"

# OWASP DC release to bundle (update as newer releases are available)
$OWASPDCVersion = "10.0.4"
$OWASPDCZipUrl  = "https://github.com/jeremylong/DependencyCheck/releases/download/v$OWASPDCVersion/dependency-check-$OWASPDCVersion-release.zip"
$OWASPDCZipPath = Join-Path $InstallerDir "dependency-check-$OWASPDCVersion-release.zip"

# ---------------------------------------------------------------------------
# Step 0: Check prerequisites
# ---------------------------------------------------------------------------
Write-Step "Checking prerequisites"

Require-Command "python"  "Install Python 3.11+ from https://python.org"
Require-Command "node"    "Install Node.js 20+ from https://nodejs.org"
Require-Command "npm"     "Install Node.js 20+ from https://nodejs.org"

# WiX v3 tools
foreach ($tool in @("heat", "candle", "light")) {
    if (-not (Get-Command "$tool.exe" -ErrorAction SilentlyContinue)) {
        Fail "$tool.exe not found.`n       Install WiX Toolset v3 from https://github.com/wixtoolset/wix3/releases`n       and ensure its bin directory is on your PATH."
    }
    Write-OK "$tool.exe found"
}

# PyInstaller
Require-PythonPackage "pyinstaller"

# Backend dependencies
Write-Step "Installing Python dependencies"
Push-Location $BackendDir
& python -m pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) { Fail "pip install failed" }
Write-OK "Backend dependencies installed"
Pop-Location

# ---------------------------------------------------------------------------
# Step 1: Build frontend
# ---------------------------------------------------------------------------
if (-not $SkipFrontendBuild) {
    Write-Step "Building React frontend"
    Push-Location $FrontendDir
    & npm install --silent
    if ($LASTEXITCODE -ne 0) { Fail "npm install failed" }
    & npm run build
    if ($LASTEXITCODE -ne 0) { Fail "npm run build failed" }
    Pop-Location
    Write-OK "Frontend built to frontend/dist"
} else {
    Write-Warn "Skipping frontend build (-SkipFrontendBuild)"
    if (-not (Test-Path (Join-Path $FrontendDir "dist"))) {
        Fail "frontend/dist does not exist. Build the frontend first."
    }
}

# ---------------------------------------------------------------------------
# Step 2: Bundle with PyInstaller
# ---------------------------------------------------------------------------
if (-not $SkipPyInstaller) {
    Write-Step "Bundling backend with PyInstaller"
    Push-Location $BackendDir
    # Clean previous build
    if (Test-Path "build")       { Remove-Item "build" -Recurse -Force }
    if (Test-Path "dist")        { Remove-Item "dist"  -Recurse -Force }

    & python -m PyInstaller owasp-scanner.spec --noconfirm
    if ($LASTEXITCODE -ne 0) { Fail "PyInstaller failed" }
    Pop-Location
    Write-OK "PyInstaller bundle created: $DistDir"
} else {
    Write-Warn "Skipping PyInstaller (-SkipPyInstaller)"
    if (-not (Test-Path $DistDir)) {
        Fail "PyInstaller output not found at $DistDir. Run without -SkipPyInstaller first."
    }
}

# ---------------------------------------------------------------------------
# Step 3 (optional): Download and stage OWASP Dependency Check
# ---------------------------------------------------------------------------
if ($BundleOWASPDC) {
    Write-Step "Staging OWASP Dependency Check v$OWASPDCVersion"

    if (-not (Test-Path $OWASPDCZipPath)) {
        Write-Host "    Downloading $OWASPDCZipUrl ..."
        Invoke-WebRequest -Uri $OWASPDCZipUrl -OutFile $OWASPDCZipPath -UseBasicParsing
        Write-OK "Downloaded"
    } else {
        Write-OK "Zip already downloaded"
    }

    if (Test-Path $OWASPDCDir) { Remove-Item $OWASPDCDir -Recurse -Force }
    Expand-Archive -Path $OWASPDCZipPath -DestinationPath $InstallerDir -Force
    # The zip extracts to a "dependency-check/" subdirectory
    Write-OK "OWASP DC extracted to $OWASPDCDir"
} else {
    Write-Warn "OWASP Dependency Check will NOT be bundled (-BundleOWASPDC not set)."
    Write-Warn "Users will download it automatically on their first scan."
    # Remove any leftover from a previous bundled build
    if (Test-Path $OWASPDCDir) { Remove-Item $OWASPDCDir -Recurse -Force }
}

# ---------------------------------------------------------------------------
# Step 4: Harvest files with WiX heat.exe
# ---------------------------------------------------------------------------
Write-Step "Harvesting PyInstaller output with heat.exe"

$AppFilesWxs = Join-Path $InstallerDir "AppFiles.wxs"
& heat.exe dir "$DistDir" `
    -nologo `
    -gg `
    -sfrag `
    -sreg `
    -srd `
    -suid `
    -cg AppFileComponents `
    -dr INSTALLFOLDER `
    -var var.AppSourceDir `
    -out "$AppFilesWxs"
if ($LASTEXITCODE -ne 0) { Fail "heat.exe failed for application files" }
Write-OK "AppFiles.wxs generated"

# Harvest OWASP DC (only if bundling)
$OWASPDCFilesWxs = Join-Path $InstallerDir "OWASPDCFiles.wxs"
if ($BundleOWASPDC -and (Test-Path $OWASPDCDir)) {
    & heat.exe dir "$OWASPDCDir" `
        -nologo `
        -gg `
        -sfrag `
        -sreg `
        -srd `
        -suid `
        -cg OWASPDCComponents `
        -dr OWASP_DC_FOLDER `
        -var var.OWASPDCSourceDir `
        -out "$OWASPDCFilesWxs"
    if ($LASTEXITCODE -ne 0) { Fail "heat.exe failed for OWASP DC" }
    Write-OK "OWASPDCFiles.wxs generated"
} else {
    # Generate an empty fragment so the main .wxs compiles regardless
    @'
<?xml version="1.0" encoding="utf-8"?>
<Wix xmlns="http://schemas.microsoft.com/wix/2006/wi">
  <Fragment>
    <ComponentGroup Id="OWASPDCComponents" />
  </Fragment>
</Wix>
'@ | Set-Content $OWASPDCFilesWxs -Encoding UTF8
    Write-OK "Empty OWASPDCFiles.wxs generated (OWASP DC not bundled)"
}

# ---------------------------------------------------------------------------
# Step 5: Compile with candle.exe
# ---------------------------------------------------------------------------
Write-Step "Compiling WiX sources with candle.exe"

$WxsSources = @(
    (Join-Path $InstallerDir "owasp-scanner.wxs"),
    $AppFilesWxs,
    $OWASPDCFilesWxs
)

$CandleArgs = @(
    "-nologo",
    "-arch", "x64",
    "-dVersion=$Version",
    "-dAppSourceDir=$DistDir",
    "-dOWASPDCSourceDir=$OWASPDCDir",
    "-ext", "WixUtilExtension",
    "-out", "$InstallerDir\"
) + $WxsSources

& candle.exe @CandleArgs
if ($LASTEXITCODE -ne 0) { Fail "candle.exe failed" }
Write-OK "WiX sources compiled"

# ---------------------------------------------------------------------------
# Step 6: Link with light.exe
# ---------------------------------------------------------------------------
Write-Step "Linking MSI with light.exe"

$ObjFiles = Get-ChildItem -Path $InstallerDir -Filter "*.wixobj" | Select-Object -ExpandProperty FullName

$LightArgs = @(
    "-nologo",
    "-ext", "WixUIExtension",
    "-ext", "WixUtilExtension",
    "-cultures:en-US",
    "-out", $MsiOutput
) + $ObjFiles

& light.exe @LightArgs
if ($LASTEXITCODE -ne 0) { Fail "light.exe failed" }

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " MSI built successfully!" -ForegroundColor Green
Write-Host " Output: $MsiOutput" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
if (-not $BundleOWASPDC) {
    Write-Host "NOTE: OWASP Dependency Check is NOT bundled in this installer." -ForegroundColor Yellow
    Write-Host "      On first scan the app will download it automatically (~150 MB)." -ForegroundColor Yellow
    Write-Host "      Re-run with -BundleOWASPDC for an offline installer." -ForegroundColor Yellow
    Write-Host ""
}
