# ============================================================
#  PYRA - Run Script (the one way to start the project)
#  Usage:  .\run.ps1 [options]
#
#  Options:
#    -Port <int>   Port to serve on (default: 8000)
#    -Planner      Planner to use: auto | offline | claude | groq (default: auto)
#    -Build        Rebuild data/pyra.db from data/factsheets/verified first
#    -Check        Run data-quality checks on the database, then exit
#    -Tests        Run the Python and flame-model test suites, then exit
#    -TestAgent    Run the research agent tests, then exit
#    -NoBrowser    Do not open the browser
#    -Help         Show this help message
#
#  The app opens at http://127.0.0.1:<Port>. The 3D flame demo is at /demo/.
#  Keys (GROQ_API_KEY, ANTHROPIC_API_KEY, ...) are read from .env if present.
# ============================================================

param(
    [int]$Port = 8000,
    [ValidateSet("auto", "offline", "claude", "groq")]
    [string]$Planner = "auto",
    [switch]$Build,
    [switch]$Check,
    [switch]$Tests,
    [switch]$TestAgent,
    [switch]$NoBrowser,
    [switch]$Help
)

Set-StrictMode -Version Latest
# Not "Stop": in Windows PowerShell 5.1 any stderr output from python.exe
# (warnings, tracebacks) would then abort the script. Exit codes are checked instead.
$ErrorActionPreference = "Continue"

# -- Resolve project root (the folder this script lives in) ------------------
$Root = $PSScriptRoot
Set-Location $Root

# -- Colour helpers -----------------------------------------------------------
function Write-Header($msg) { Write-Host "`n$msg" -ForegroundColor Cyan }
function Write-Ok($msg)     { Write-Host "  OK   $msg" -ForegroundColor Green }
function Write-Warn($msg)   { Write-Host "  WARN $msg" -ForegroundColor Yellow }
function Write-Err($msg)    { Write-Host "  ERR  $msg" -ForegroundColor Red }
function Write-Step($msg)   { Write-Host "  >>   $msg" -ForegroundColor DarkCyan }

# -- Help ---------------------------------------------------------------------
if ($Help) {
    Get-Content $PSCommandPath -TotalCount 17 | ForEach-Object { $_ -replace '^#\s?', '' }
    exit 0
}

# -- Banner (plain ASCII: PowerShell 5.1 misreads other characters in a file without a BOM)
Write-Host ""
Write-Host "  PYRA - Predictive Hazard & Reliability Atlas" -ForegroundColor Magenta
Write-Host "  NASA Space Apps Hackathon" -ForegroundColor Magenta

# -- Python check -------------------------------------------------------------
Write-Header "Checking Python..."
$python = $null
foreach ($cmd in @("python", "python3")) {
    try {
        if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { continue }
        $ver = ((& $cmd --version 2>&1) | Out-String).Trim()
        if ($ver -match "Python 3\.(\d+)") {
            $minor = [int]$Matches[1]
            if ($minor -ge 11) {
                $python = $cmd
                Write-Ok "$ver  ($cmd)"
                break
            } else {
                Write-Warn "$ver found but Python 3.11+ is required."
            }
        }
    } catch { }
}
if (-not $python) {
    Write-Err "Python 3.11 or later not found. Install it from https://python.org and re-run."
    exit 1
}

# -- Load .env (KEY=value lines; real environment variables win) -----------
$envFile = Join-Path $Root ".env"
if (Test-Path $envFile) {
    Write-Header "Loading .env..."
    foreach ($line in Get-Content $envFile) {
        $line = $line.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) { continue }
        $name, $value = $line.Split("=", 2)
        $name = $name.Trim() -replace '^export\s+', ''
        $value = $value.Trim().Trim('"').Trim("'")
        if (-not [Environment]::GetEnvironmentVariable($name, "Process")) {
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
            Write-Ok "$name loaded"
        }
    }
}

# -- Run tests ----------------------------------------------------------------
if ($Tests) {
    Write-Header "Running the Python test suite..."
    & $python -m unittest discover tests
    $code = $LASTEXITCODE
    if (Get-Command node -ErrorAction SilentlyContinue) {
        Write-Header "Running the flame model tests..."
        & node --test (Join-Path $Root "tests\flame_model.test.js")
        if ($LASTEXITCODE -ne 0) { $code = $LASTEXITCODE }
    } else {
        Write-Warn "Node.js not found, skipping tests\flame_model.test.js."
    }
    if ($code -eq 0) { Write-Ok "All tests passed." } else { Write-Err "Some tests failed (see above)." }
    exit $code
}

if ($TestAgent) {
    Write-Header "Running the research agent tests..."
    & $python -m unittest discover tests -p "test_agent*.py"
    exit $LASTEXITCODE
}

# -- Optional model packages and keys -----------------------------------------
Write-Header "Checking optional dependencies..."
function Test-PyPackage($name) {
    (& $python -c "import importlib.util as u; print('yes' if u.find_spec('$name') else 'no')" 2>$null) -eq "yes"
}
$claudeReady = (Test-PyPackage "anthropic") -and ($env:ANTHROPIC_API_KEY -or $env:ANTHROPIC_AUTH_TOKEN)
$groqReady   = (Test-PyPackage "openai") -and $env:GROQ_API_KEY

if ($claudeReady) { Write-Ok "Claude planner available (anthropic + ANTHROPIC_API_KEY)" }
elseif ($Planner -eq "claude") {
    Write-Err "-Planner claude needs 'pip install anthropic' and ANTHROPIC_API_KEY (in .env or the environment)."
    exit 1
}

if ($groqReady) { Write-Ok "Groq planner available (openai + GROQ_API_KEY, model $(if ($env:GROQ_MODEL) { $env:GROQ_MODEL } else { 'openai/gpt-oss-120b' }))" }
elseif ($Planner -eq "groq") {
    if (-not $env:GROQ_API_KEY) { Write-Err "-Planner groq needs GROQ_API_KEY. Add GROQ_API_KEY=gsk_... to .env." }
    else { Write-Err "-Planner groq needs the openai package: pip install openai" }
    exit 1
}

if ($Planner -eq "auto") {
    $picked = if ($claudeReady) { "claude" } elseif ($groqReady) { "groq" } else { "offline" }
    Write-Step "auto planner will use: $picked"
}

# -- Build database ------------------------------------------------------------
$dbPath = Join-Path $Root "data\pyra.db"
if ($Build -or -not (Test-Path $dbPath)) {
    if (-not $Build) { Write-Warn "data\pyra.db not found, building it now." }
    Write-Header "Building the database from verified fact sheets..."
    Write-Step "python -m pyra build"
    & $python -m pyra build
    if ($LASTEXITCODE -ne 0) { Write-Err "Build failed."; exit 1 }
    Write-Ok "Database built -> data/pyra.db"
}

# -- Data-quality check --------------------------------------------------------
if ($Check) {
    Write-Header "Running data-quality checks..."
    & $python -m pyra check
    exit $LASTEXITCODE
}

$verified = @(Get-ChildItem (Join-Path $Root "data\factsheets\verified") -Filter *.json -ErrorAction SilentlyContinue)
if ($verified.Count -eq 0) {
    Write-Warn "data\factsheets\verified has no fact sheets, so the evidence views will be empty."
    Write-Step "Add verified sheets there, then run .\run.ps1 -Build"
}

# -- Free the port if an earlier PYRA server still holds it ---------------------
$holders = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
foreach ($holder in $holders) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($holder.OwningProcess)" -ErrorAction SilentlyContinue
    if ($proc -and $proc.CommandLine -match "-m pyra") {
        Write-Step "Stopping the earlier PYRA server on port $Port (PID $($proc.ProcessId))"
        Stop-Process -Id $proc.ProcessId -Force
        Start-Sleep -Milliseconds 300
    } else {
        Write-Err "Port $Port is used by another program. Pick a different one with -Port."
        exit 1
    }
}

# -- Launch server -------------------------------------------------------------
Write-Header "Starting PYRA server..."
$serverArgs = @("--port", "$Port", "--planner", $Planner)
Write-Step "python -m pyra.server $serverArgs"
Write-Host ""
Write-Host "  App      ->  http://127.0.0.1:$Port" -ForegroundColor White
Write-Host "  3D demo  ->  http://127.0.0.1:$Port/demo/" -ForegroundColor White
Write-Host "  Press Ctrl+C to stop.`n" -ForegroundColor DarkGray

if (-not $NoBrowser) {
    # Open the page once the server is listening, without blocking the server itself.
    Start-Job -ScriptBlock {
        param($url)
        for ($i = 0; $i -lt 40; $i++) {
            try { Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 1 | Out-Null; break } catch { Start-Sleep -Milliseconds 250 }
        }
        Start-Process $url
    } -ArgumentList "http://127.0.0.1:$Port" | Out-Null
}

& $python -m pyra.server @serverArgs
