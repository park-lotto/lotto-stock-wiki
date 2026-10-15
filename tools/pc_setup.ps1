# 새 PC 준비 — 로또의 주식 폴더 바로 열기 + 볼케이노 MCP 연결 (2026-10-15)
# 실행: 로또의 주식 폴더에서  powershell -ExecutionPolicy Bypass -File tools\pc_setup.ps1
# ★비밀값(키·로그인)은 여기 없다 — 볼케이노 로그인은 브라우저에서 사장님이 한다.

$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent $PSScriptRoot
Write-Host "== 로또의 주식 폴더: $repo"

# 1) claude 가 있나
$cl = Get-Command claude -ErrorAction SilentlyContinue
if (-not $cl) {
    Write-Host "[X] claude 가 없습니다. 먼저 설치하세요:  npm install -g @anthropic-ai/claude-code" -ForegroundColor Red
    exit 1
}
Write-Host "[O] claude: $($cl.Source)"

# 2) PowerShell 에서 '로또' 한 단어로 이 폴더 + claude
if (-not (Test-Path $PROFILE)) { New-Item -ItemType File -Force $PROFILE | Out-Null }
$line = "function 로또 { Set-Location `"$repo`"; claude }"
if (-not (Select-String -Path $PROFILE -Pattern "function 로또" -Quiet)) {
    Add-Content -Path $PROFILE -Value "`n$line" -Encoding UTF8
    Write-Host "[O] '로또' 명령 등록 — 새 PowerShell 창에서 로또 만 치면 됩니다"
} else {
    Write-Host "[=] '로또' 명령은 이미 있습니다"
}

# 3) 볼케이노 MCP 연결(원격 서버 주소 한 줄)
$has = (claude mcp list 2>$null) -match "volcano"
if (-not $has) {
    claude mcp add --scope user --transport http volcano https://volcano-mcp.groove1027.workers.dev
    Write-Host "[O] 볼케이노 연결 등록"
} else {
    Write-Host "[=] 볼케이노는 이미 등록돼 있습니다"
}

Write-Host ""
Write-Host "== 남은 것(사장님 손): claude 를 켜고  /mcp  → volcano → Authenticate → 브라우저에서 로그인" -ForegroundColor Yellow
Write-Host "   확인: claude mcp list 에 volcano 가 보이면 끝"
