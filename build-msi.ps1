<#
.SYNOPSIS
    Build a fully self-contained Windows MSI for OWASP Dependency Scanner.

.DESCRIPTION
    Everything is bundled -- Java JRE, OWASP Dependency Check, and the Python
    backend.  The resulting MSI installs and runs without any prerequisites on
    the target machine.

    Build-time requirements (on the machine running this script):
      - Python 3.11+  (python.exe on PATH)
      - Node.js 20+   (node / npm on PATH)
      WiX v3, Eclipse Temurin JRE, and OWASP DC are downloaded automatically.

.PARAMETER SkipFrontendBuild
    Skip `npm run build` (use when frontend/dist already exists).

.PARAMETER SkipPyInstaller
    Skip PyInstaller step (use when dist/owasp-scanner already exists).

.PARAMETER SkipDownloads
    Skip downloading WiX / JRE / OWASP DC (assume they are already cached in
    the installer/ directory).

.PARAMETER Version
    Version string embedded in the MSI (default: 1.0.0).

.EXAMPLE
    .\build-msi.ps1                          # full build
    .\build-msi.ps1 -SkipFrontendBuild       # skip npm build
    .\build-msi.ps1 -SkipPyInstaller         # WiX-only iteration
    .\build-msi.ps1 -SkipDownloads           # all assets already cached
#>

[CmdletBinding()]
param(
    [switch]$SkipFrontendBuild,
    [switch]$SkipPyInstaller,
    [switch]$SkipDownloads,
    [string]$Version = "1.0.0"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── helpers ─────────────────────────────────────────────────────────────────
function Step  { param([string]$m) Write-Host "`n==> $m" -ForegroundColor Cyan }
function OK    { param([string]$m) Write-Host "    OK: $m" -ForegroundColor Green }
function Warn  { param([string]$m) Write-Host "    WARN: $m" -ForegroundColor Yellow }
function Fail  { param([string]$m) Write-Host "`nERROR: $m" -ForegroundColor Red; exit 1 }

function Download {
    param([string]$Url, [string]$Dest)
    if (Test-Path $Dest) { OK "Already cached: $(Split-Path $Dest -Leaf)"; return }
    Write-Host "    Downloading $(Split-Path $Dest -Leaf) ..."
    Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing
    OK "Downloaded"
}

# ── paths ────────────────────────────────────────────────────────────────────
$Root         = $PSScriptRoot
$BackendDir   = Join-Path $Root "backend"
$FrontendDir  = Join-Path $Root "frontend"
$InstallerDir = Join-Path $Root "installer"
$CacheDir     = Join-Path $InstallerDir "_cache"      # downloaded archives
$WiXDir       = Join-Path $InstallerDir "_wix"        # extracted WiX binaries
$JREDir       = Join-Path $InstallerDir "jre"         # bundled JRE
$OWASPDCDir   = Join-Path $InstallerDir "dependency-check"  # bundled OWASP DC
$PyDistDir    = Join-Path $BackendDir "dist\owasp-scanner"  # PyInstaller output
$MsiOut       = Join-Path $Root "owasp-scanner-$Version.msi"

New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null

# ── pinned versions & URLs ───────────────────────────────────────────────────
$WiXVersion   = "3.14.1"
$WiXUrl       = "https://github.com/wixtoolset/wix3/releases/download/wix3141rtm/wix314-binaries.zip"
$WiXZip       = Join-Path $CacheDir "wix314-binaries.zip"

# Eclipse Temurin JRE 21 LTS -- Windows x64 zip
$JREVersion   = "21.0.5+11"
$JREUrl       = "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.5%2B11/OpenJDK21U-jre_x64_windows_hotspot_21.0.5_11.zip"
$JREZip       = Join-Path $CacheDir "temurin-jre-21-win-x64.zip"

# OWASP Dependency Check
$OWASPDCVer   = "10.0.4"
$OWASPDCUrl   = "https://github.com/jeremylong/DependencyCheck/releases/download/v$OWASPDCVer/dependency-check-$OWASPDCVer-release.zip"
$OWASPDCZip   = Join-Path $CacheDir "dependency-check-$OWASPDCVer.zip"

# ── locate / bootstrap WiX ──────────────────────────────────────────────────
Step "Locating WiX Toolset v3"
$HeatExe   = Get-Command "heat.exe"   -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
$CandleExe = Get-Command "candle.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
$LightExe  = Get-Command "light.exe"  -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source

if (-not ($HeatExe -and $CandleExe -and $LightExe)) {
    Warn "WiX not on PATH -- downloading WiX $WiXVersion binaries..."

    if (-not $SkipDownloads) { Download $WiXUrl $WiXZip }

    if (Test-Path $WiXDir) { Remove-Item $WiXDir -Recurse -Force }
    Expand-Archive -Path $WiXZip -DestinationPath $WiXDir -Force
    OK "WiX extracted to $WiXDir"

    $HeatExe   = Join-Path $WiXDir "heat.exe"
    $CandleExe = Join-Path $WiXDir "candle.exe"
    $LightExe  = Join-Path $WiXDir "light.exe"

    foreach ($exe in @($HeatExe, $CandleExe, $LightExe)) {
        if (-not (Test-Path $exe)) { Fail "$exe not found after extracting WiX." }
    }
} else {
    OK "heat=$HeatExe"
    OK "candle=$CandleExe"
    OK "light=$LightExe"
}

# ── check Python / Node ──────────────────────────────────────────────────────
Step "Checking Python and Node.js"
foreach ($cmd in @("python", "node", "npm")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Fail "$cmd not found on PATH.  Install Python 3.11+ and Node.js 20+."
    }
    OK "$cmd found"
}

# ── build virtual environment ─────────────────────────────────────────────────
# Use a dedicated venv so we never need admin rights on the system Python.
$BuildVenv   = Join-Path $BackendDir ".build-venv"
$PythonExe   = Join-Path $BuildVenv "Scripts\python.exe"
$PyInstExe   = Join-Path $BuildVenv "Scripts\pyinstaller.exe"

Step "Setting up build virtual environment ($BuildVenv)"
if (-not (Test-Path $PythonExe)) {
    & python -m venv $BuildVenv
    if ($LASTEXITCODE -ne 0) { Fail "Failed to create build venv" }
    OK "venv created"
} else {
    OK "venv already exists"
}

# Upgrade pip silently
& $PythonExe -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) { Fail "pip upgrade failed" }

Step "Installing PyInstaller into build venv"
& $PythonExe -m pip install pyinstaller --quiet
if ($LASTEXITCODE -ne 0) { Fail "pip install pyinstaller failed" }
OK "pyinstaller installed"

Step "Installing backend dependencies into build venv"
& $PythonExe -m pip install -r (Join-Path $BackendDir "requirements.txt") --quiet
if ($LASTEXITCODE -ne 0) { Fail "pip install -r requirements.txt failed" }
OK "backend dependencies installed"

# ── frontend build ───────────────────────────────────────────────────────────
if (-not $SkipFrontendBuild) {
    Step "Building React frontend"
    Push-Location $FrontendDir
    & npm install --silent
    if ($LASTEXITCODE -ne 0) { Fail "npm install failed" }
    & npm run build
    if ($LASTEXITCODE -ne 0) { Fail "npm run build failed" }
    Pop-Location
    OK "Frontend built -> frontend/dist"
} else {
    Warn "Skipping frontend build"
    if (-not (Test-Path (Join-Path $FrontendDir "dist"))) {
        Fail "frontend/dist missing -- run without -SkipFrontendBuild first."
    }
}

# ── PyInstaller ──────────────────────────────────────────────────────────────
if (-not $SkipPyInstaller) {
    Step "Bundling backend with PyInstaller"
    Push-Location $BackendDir
    if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
    if (Test-Path "dist")  { Remove-Item "dist"  -Recurse -Force }
    & $PyInstExe owasp-scanner.spec --noconfirm
    if ($LASTEXITCODE -ne 0) { Fail "PyInstaller failed" }
    Pop-Location
    OK "Bundle -> $PyDistDir"
} else {
    Warn "Skipping PyInstaller"
    if (-not (Test-Path $PyDistDir)) {
        Fail "PyInstaller output missing -- run without -SkipPyInstaller first."
    }
}

# ── download + stage Eclipse Temurin JRE 21 ─────────────────────────────────
Step "Staging Eclipse Temurin JRE 21 LTS"
if (-not $SkipDownloads) { Download $JREUrl $JREZip }

if (Test-Path $JREDir) { Remove-Item $JREDir -Recurse -Force }

# Extract to a clean temp path to avoid issues with '+' in the versioned dir name
$JRETmp = Join-Path $InstallerDir "_jre_tmp"
if (Test-Path $JRETmp) { Remove-Item $JRETmp -Recurse -Force }
Write-Host "    Extracting JRE..."
Expand-Archive -Path $JREZip -DestinationPath $JRETmp -Force

$JREExtracted = Get-ChildItem -Path $JRETmp -Directory | Select-Object -First 1
if (-not $JREExtracted) { Fail "Could not find extracted JRE directory under $JRETmp" }

# Move the versioned dir to the stable 'jre' name
Move-Item -Path $JREExtracted.FullName -Destination $JREDir
Remove-Item $JRETmp -Recurse -Force -ErrorAction SilentlyContinue
OK "JRE staged at $JREDir"

# ── download + stage OWASP Dependency Check ──────────────────────────────────
Step "Staging OWASP Dependency Check v$OWASPDCVer"
if (-not $SkipDownloads) { Download $OWASPDCUrl $OWASPDCZip }

if (Test-Path $OWASPDCDir) { Remove-Item $OWASPDCDir -Recurse -Force }
Write-Host "    Extracting OWASP DC..."
Expand-Archive -Path $OWASPDCZip -DestinationPath $InstallerDir -Force
# Zip extracts to dependency-check/
if (-not (Test-Path $OWASPDCDir)) { Fail "Expected $OWASPDCDir after extraction." }
OK "OWASP DC staged at $OWASPDCDir"

# ── WiX heat -- harvest all three directories ─────────────────────────────────
Step "Harvesting file manifests with heat.exe"

function Heat {
    param([string]$SrcDir, [string]$CgId, [string]$DirRef, [string]$VarName,
          [string]$OutFile, [string]$IdPrefix)

    # Run heat without -suid so it generates path-based unique IDs
    & $HeatExe dir "$SrcDir" -nologo -gg -sfrag -sreg -srd `
        -cg $CgId -dr $DirRef -var "var.$VarName" -out "$OutFile"
    if ($LASTEXITCODE -ne 0) { Fail "heat.exe failed for $CgId" }

    # Post-process: prefix Component/@Id, File/@Id, and Directory/@Id with
    # $IdPrefix to prevent duplicate-symbol errors when the same Windows DLL
    # appears in both the PyInstaller bundle and the JRE.
    # ComponentGroup/@Id is intentionally NOT prefixed -- it is referenced
    # by name from owasp-scanner.wxs.
    $xml = [xml](Get-Content $OutFile -Encoding UTF8)
    foreach ($node in $xml.GetElementsByTagName("Component")) {
        $id = $node.GetAttribute("Id")
        if ($id) { $node.SetAttribute("Id", $IdPrefix + $id) }
    }
    foreach ($node in $xml.GetElementsByTagName("File")) {
        $id = $node.GetAttribute("Id")
        if ($id) { $node.SetAttribute("Id", $IdPrefix + $id) }
    }
    foreach ($node in $xml.GetElementsByTagName("Directory")) {
        $id = $node.GetAttribute("Id")
        # Never rename the anchor directory references set by -dr
        if ($id -and $id -notin @("INSTALLFOLDER","JRE_FOLDER","OWASPDC_FOLDER","TARGETDIR")) {
            $node.SetAttribute("Id", $IdPrefix + $id)
        }
    }
    # ComponentRef/@Id must match the newly prefixed Component/@Id values
    foreach ($node in $xml.GetElementsByTagName("ComponentRef")) {
        $id = $node.GetAttribute("Id")
        if ($id) { $node.SetAttribute("Id", $IdPrefix + $id) }
    }
    $xml.Save($OutFile)
    OK "$OutFile generated (prefix: $IdPrefix)"
}

Heat $PyDistDir  "AppFileComponents"  "INSTALLFOLDER"   "AppSourceDir"    (Join-Path $InstallerDir "AppFiles.wxs")   "App_"
Heat $JREDir     "JREComponents"      "JRE_FOLDER"      "JRESourceDir"    (Join-Path $InstallerDir "JREFiles.wxs")   "JRE_"
Heat $OWASPDCDir "OWASPDCComponents"  "OWASPDC_FOLDER"  "OWASPDCSourceDir" (Join-Path $InstallerDir "OWASPDCFiles.wxs") "DC_"

# ── WiX candle ──────────────────────────────────────────────────────────────
Step "Compiling WiX sources with candle.exe"

$WxsSources = @(
    (Join-Path $InstallerDir "owasp-scanner.wxs"),
    (Join-Path $InstallerDir "AppFiles.wxs"),
    (Join-Path $InstallerDir "JREFiles.wxs"),
    (Join-Path $InstallerDir "OWASPDCFiles.wxs")
)

& $CandleExe -nologo -arch x64 `
    "-dVersion=$Version" `
    "-dAppSourceDir=$PyDistDir" `
    "-dJRESourceDir=$JREDir" `
    "-dOWASPDCSourceDir=$OWASPDCDir" `
    -ext WixUtilExtension `
    -out "$InstallerDir\" `
    @WxsSources
if ($LASTEXITCODE -ne 0) { Fail "candle.exe failed" }
OK "WiX sources compiled"

# ── WiX light ───────────────────────────────────────────────────────────────
Step "Linking MSI with light.exe"

$ObjFiles = Get-ChildItem -Path $InstallerDir -Filter "*.wixobj" |
    Select-Object -ExpandProperty FullName

& $LightExe -nologo `
    -ext WixUIExtension `
    -ext WixUtilExtension `
    -cultures:en-US `
    -out $MsiOut `
    @ObjFiles
if ($LASTEXITCODE -ne 0) { Fail "light.exe failed" }

# ── done ─────────────────────────────────────────────────────────────────────
$MsiSize = [math]::Round((Get-Item $MsiOut).Length / 1MB, 1)
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  MSI built successfully!" -ForegroundColor Green
Write-Host "  $MsiOut  ($MsiSize MB)" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Upload to GitHub release:" -ForegroundColor Cyan
Write-Host "  gh release upload v$Version `"$MsiOut`"" -ForegroundColor White
Write-Host ""
