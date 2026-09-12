# ============================================================================
#  클로드코덱스 설치팩 — 새 PC를 사무실 PC(2026-09-11 실측)와 똑같이 세팅한다
#
#  실행 (관리자 아님, 그냥 PowerShell):
#      Set-ExecutionPolicy -Scope Process Bypass -Force
#      .\install.ps1
#
#  멱등이다 — 몇 번 돌려도 된다. 이미 된 건 건너뛴다.
#  사람이 직접 해야 하는 것(로그인·키·확장·샌드박스 승인)은 마지막에 목록으로 띄운다.
# ============================================================================
$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$PACK    = $PSScriptRoot
$HOME_   = $env:USERPROFILE
$PROJECT = Join-Path $HOME_ 'Desktop\로또의 주식'
$REPO    = 'https://github.com/park-lotto/lotto-stock-wiki.git'

function Step($t){ Write-Host "`n==== $t" -ForegroundColor Cyan }
function Ok($t){ Write-Host "  ✅ $t" -ForegroundColor Green }
function Skip($t){ Write-Host "  ↷ $t (이미 됨)" -ForegroundColor DarkGray }
function Warn($t){ Write-Host "  ⚠ $t" -ForegroundColor Yellow }
function Has($cmd){ [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function RefreshPath(){
  $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
}
function AddUserPath($p){
  $cur = [Environment]::GetEnvironmentVariable('Path','User')
  if (($cur -split ';') -notcontains $p) {
    [Environment]::SetEnvironmentVariable('Path', ($cur.TrimEnd(';') + ';' + $p), 'User'); Ok "PATH 추가: $p"
  }
}

# ---------------------------------------------------------------------------
Step '0. winget 확인'
if (-not (Has winget)) { Warn 'winget 이 없다 — Microsoft Store 에서 "앱 설치 관리자" 를 먼저 설치하고 다시 실행'; exit 1 }
Ok "winget $(winget --version)"

# ---------------------------------------------------------------------------
Step '1. 기본 도구 (winget) — Git · Node 24 · Python 3.12 · ffmpeg · gh · uv · bun'
# 사무실 PC 실측: node v24.15.0 · python 3.12.10 · ffmpeg 8.1.1(watch·영상) · uv(notebooklm-mcp) · bun(gstack /browse)
# ★배열 원소 뒤에 주석을 달면 PowerShell 5.1 파서가 "Missing expression after ','" 로 죽는다 — 주석은 위에만.
$pkgs = @(
  @{id='Git.Git';              cmd='git'},
  @{id='OpenJS.NodeJS';        cmd='node'},
  @{id='Python.Python.3.12';   cmd='python'},
  @{id='Gyan.FFmpeg';          cmd='ffmpeg'},
  @{id='GitHub.cli';           cmd='gh'},
  @{id='astral-sh.uv';         cmd='uv'},
  @{id='Oven-sh.Bun';          cmd='bun'}
)
foreach ($p in $pkgs) {
  if (Has $p.cmd) { Skip "$($p.id)" ; continue }
  winget install --id $p.id -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
  RefreshPath
  if (Has $p.cmd) { Ok "$($p.id)" } else { Warn "$($p.id) 설치 확인 실패 — 창을 새로 열고 다시 실행해 보세요" }
}
# ★Windows 스토어 python 스텁이 진짜 python 을 가리는 문제(사무실 PC 실사고) — 진짜 경로를 PATH 앞에 둔다
$pyDir = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312'
if (Test-Path $pyDir) { AddUserPath "$pyDir\Scripts\"; AddUserPath "$pyDir\" }
RefreshPath

# ---------------------------------------------------------------------------
Step '2. Claude Code (공식 설치기 → ~/.local/bin/claude.exe)'
if (Has claude) { Skip "claude $(claude --version 2>$null)" }
else {
  irm https://claude.ai/install.ps1 | iex
  AddUserPath (Join-Path $HOME_ '.local\bin'); RefreshPath
  if (Has claude) { Ok "claude $(claude --version 2>$null)" } else { Warn 'claude 설치 확인 실패' }
}

# ---------------------------------------------------------------------------
Step '3. Codex CLI + npm 전역 (사무실 PC와 동일)'
foreach ($n in @('@openai/codex','myagentmemory','@higgsfield/cli')) {
  $name = ($n -split '@')[-1]; if ($n.StartsWith('@')) { $name = $n }
  $have = (npm ls -g --depth=0 2>$null) -match [regex]::Escape($n)
  if ($have) { Skip $n } else { npm install -g $n | Out-Null; Ok $n }
}
AddUserPath (Join-Path $env:APPDATA 'npm'); RefreshPath

# ---------------------------------------------------------------------------
Step '4. 저장소 받기 + 프로젝트 의존성'
if (Test-Path (Join-Path $PROJECT '.git')) { Skip "저장소 $PROJECT" }
else { git clone $REPO $PROJECT; if (Test-Path (Join-Path $PROJECT '.git')) { Ok '저장소 clone' } else { Warn 'clone 실패' } }
if (Test-Path (Join-Path $PROJECT 'shopping_shorts\requirements.txt')) {
  python -m pip install -q --upgrade pip
  python -m pip install -q -r (Join-Path $PROJECT 'shopping_shorts\requirements.txt')
  python -m pip install -q tzdata playwright httpx      # 사무실 PC 실측 전역 패키지 (tzdata 없으면 ZoneInfo 테스트가 깨진다)
  python -m playwright install chromium 2>$null | Out-Null
  Ok 'python 패키지'
}
if (Test-Path (Join-Path $PROJECT 'package.json')) { Push-Location $PROJECT; npm install --silent | Out-Null; Pop-Location; Ok 'npm install (puppeteer 등)' }
# notebooklm-mcp는 2026-09-12 뺌(만료 쿠키로 로그인 크롬창이 반복해서 뜸)

# ---------------------------------------------------------------------------
Step '5. Claude 설정 복사 (~/.claude)'
$CL = Join-Path $HOME_ '.claude'
New-Item -ItemType Directory -Force -Path $CL, (Join-Path $CL 'dashboard'), (Join-Path $CL 'skills') | Out-Null
# settings.json — 팩의 템플릿에서 사용자 경로만 치환. 이미 있으면 백업 뒤 덮어쓴다(사무실과 동일하게).
$settingsT = Get-Content (Join-Path $PACK 'claude\settings.json.template') -Raw -Encoding UTF8
$settingsT = $settingsT.Replace('__USERPROFILE__', $HOME_.Replace('\','\\'))
$settingsP = Join-Path $CL 'settings.json'
if (Test-Path $settingsP) { Copy-Item $settingsP "$settingsP.bak-$(Get-Date -Format yyyyMMddHHmm)" }
[IO.File]::WriteAllText($settingsP, $settingsT, (New-Object Text.UTF8Encoding $false)); Ok 'settings.json (훅·권한·플러그인 목록·모델)'
# ★사무실 PC 절대경로가 박힌 텍스트 파일은 복사하면서 새 PC 홈으로 바꿔 쓴다 (실측 2026-09-11:
#   전역 CLAUDE.md 의 fablize 팩 경로 3줄, dashboard/config.json 의 path_hints, dashboard_cli.py 의 _REPO_LOG).
#   안 바꾸면 fablize 규칙 파일을 못 찾고, Stop 훅이 프로젝트를 '스탁브레인'으로 못 알아본다.
$OFFICE_HOME_BS = 'C:\Users\TheRose'; $OFFICE_HOME_FS = 'C:/Users/TheRose'
function CopyRewrite($src, $dst){
  $t = [IO.File]::ReadAllText($src, [Text.Encoding]::UTF8)
  $t = $t.Replace($OFFICE_HOME_BS.Replace('\','\\'), $HOME_.Replace('\','\\')).Replace($OFFICE_HOME_BS, $HOME_).Replace($OFFICE_HOME_FS, $HOME_.Replace('\','/'))
  [IO.File]::WriteAllText($dst, $t, (New-Object Text.UTF8Encoding $false))
}
CopyRewrite (Join-Path $PACK 'claude\CLAUDE.md') (Join-Path $CL 'CLAUDE.md');                 Ok '전역 CLAUDE.md (한국어 규칙·fablize — 경로 치환)'
Copy-Item (Join-Path $PACK 'claude\keybindings.json') (Join-Path $CL 'keybindings.json') -Force; Ok 'keybindings.json'
Get-ChildItem (Join-Path $PACK 'claude\dashboard') -File | ForEach-Object {
  if ($_.Extension -in '.py','.json','.md','.html') { CopyRewrite $_.FullName (Join-Path $CL "dashboard\$($_.Name)") }
  else { Copy-Item $_.FullName (Join-Path $CL "dashboard\$($_.Name)") -Force }
}
Ok 'dashboard/ (Stop 훅 스크립트 — 경로 치환)'
# ~/.claude.json 의 mcpServers 병합 (키 없음 — 전부 stdio 커맨드)
$cj = Join-Path $HOME_ '.claude.json'
$mcp = Get-Content (Join-Path $PACK 'claude\mcpServers.json') -Raw -Encoding UTF8
$mcp = $mcp.Replace('__USERPROFILE__', $HOME_.Replace('\','/'))
$mcpObj = $mcp | ConvertFrom-Json
if (Test-Path $cj) { $root = Get-Content $cj -Raw -Encoding UTF8 | ConvertFrom-Json } else { $root = New-Object psobject }
if (-not $root.PSObject.Properties['mcpServers']) { $root | Add-Member -NotePropertyName mcpServers -NotePropertyValue (New-Object psobject) }
foreach ($prop in $mcpObj.PSObject.Properties) {
  if ($root.mcpServers.PSObject.Properties[$prop.Name]) { $root.mcpServers.($prop.Name) = $prop.Value } else { $root.mcpServers | Add-Member -NotePropertyName $prop.Name -NotePropertyValue $prop.Value }
}
[IO.File]::WriteAllText($cj, ($root | ConvertTo-Json -Depth 20), (New-Object Text.UTF8Encoding $false)); Ok '~/.claude.json mcpServers 4개 (firecrawl·browsermcp·elevenlabs·AfterEffects)'
# 자동 메모리 (프로젝트 경로 키는 사용자명에 따라 달라진다 → 여기서 계산)
$projKey = ($PROJECT -replace '[^A-Za-z0-9]', '-')
$memDst = Join-Path $CL "projects\$projKey\memory"
New-Item -ItemType Directory -Force -Path $memDst | Out-Null
Copy-Item (Join-Path $PACK 'claude\memory\*') $memDst -Force -Recurse; Ok "자동 메모리 $((Get-ChildItem $memDst).Count)개 → projects\$projKey\memory"
# watch 플러그인 키 파일 자리
$wenv = Join-Path $HOME_ '.config\watch\.env'
if (-not (Test-Path $wenv)) { New-Item -ItemType Directory -Force -Path (Split-Path $wenv) | Out-Null; Copy-Item (Join-Path $PACK 'claude\watch.env.template') $wenv; Warn "~/.config/watch/.env 만들었음 — GROQ_API_KEY 를 채우세요(영상 /watch 용)" }

# ---------------------------------------------------------------------------
Step '6. gstack (Claude 안에서 /codex·/browse·/review 등을 주는 스킬 묶음)'
$gs = Join-Path $CL 'skills\gstack'
if (Test-Path (Join-Path $gs 'setup')) { Skip 'gstack' }
else {
  git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git $gs
  $bash = 'C:\Program Files\Git\bin\bash.exe'
  if (Test-Path $bash) { & $bash -lc "cd '$($gs.Replace('\','/'))' && ./setup" } else { Warn 'Git Bash 가 없어 gstack ./setup 을 못 돌렸다 — Git 설치 후 다시' }
  if (Test-Path (Join-Path $CL 'skills\codex\SKILL.md')) { Ok 'gstack + /codex 스킬' } else { Warn 'gstack setup 확인 실패 — README 6번 참고' }
}

# ---------------------------------------------------------------------------
Step '7. After Effects MCP (선택 — 사무실 PC에 있어서 같이 둔다)'
$ae = Join-Path $HOME_ 'tools\after-effects-mcp'
if (Test-Path (Join-Path $ae 'build\index.js')) { Skip 'after-effects-mcp' }
else {
  New-Item -ItemType Directory -Force -Path (Split-Path $ae) | Out-Null
  git clone https://github.com/Dakkshin/after-effects-mcp.git $ae 2>$null
  if (Test-Path $ae) { Push-Location $ae; npm install --silent 2>$null | Out-Null; npm run build --silent 2>$null | Out-Null; Pop-Location }
  if (Test-Path (Join-Path $ae 'build\index.js')) { Ok 'after-effects-mcp' } else { Warn 'after-effects-mcp 빌드 실패 — AE 안 쓰면 무시해도 됨' }
}

# ---------------------------------------------------------------------------
Step '8. Codex 설정 (~/.codex/config.toml · cmd 자동실행 · 바탕화면 바로가기)'
$cx = Join-Path $HOME_ '.codex'; New-Item -ItemType Directory -Force -Path $cx | Out-Null
$cfg = Get-Content (Join-Path $PACK 'codex\config.toml.template') -Raw -Encoding UTF8
$cfg = $cfg.Replace('__PROJECT_DIR_LOWER__', $PROJECT.ToLower())
$cfgP = Join-Path $cx 'config.toml'
if (Test-Path $cfgP) { Copy-Item $cfgP "$cfgP.bak-$(Get-Date -Format yyyyMMddHHmm)" }
[IO.File]::WriteAllText($cfgP, $cfg, (New-Object Text.UTF8Encoding $false)); Ok 'config.toml (astra 기본 · 승인창 끔 · 전체접근 · elevated 샌드박스)'
# cmd 열면 Codex — 한글 REM 이 있어 cmd 가 읽는 ANSI(cp949)로 저장한다
$ar = Get-Content (Join-Path $PACK 'codex\codex-autorun.cmd.template') -Raw -Encoding UTF8
$ar = $ar.Replace('__PROJECT_DIR__', $PROJECT)
$arP = Join-Path $HOME_ '.codex-autorun.cmd'
[IO.File]::WriteAllText($arP, $ar, [Text.Encoding]::GetEncoding(949))
New-Item -Path 'HKCU:\Software\Microsoft\Command Processor' -Force | Out-Null
New-ItemProperty -Path 'HKCU:\Software\Microsoft\Command Processor' -Name AutoRun -Value "`"$arP`"" -PropertyType String -Force | Out-Null
Ok 'cmd AutoRun → .codex-autorun.cmd (끄기: reg delete "HKCU\Software\Microsoft\Command Processor" /v AutoRun /f)'
$lnk = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $HOME_ 'Desktop\코덱스.lnk'))
$lnk.TargetPath = 'C:\Windows\System32\cmd.exe'; $lnk.Arguments = "/k cd /d `"$PROJECT`" && codex"; $lnk.WorkingDirectory = $PROJECT; $lnk.Save()
Ok '바탕화면 코덱스.lnk'

# ---------------------------------------------------------------------------
Step '9. Claude 플러그인 마켓플레이스 등록 (설치는 Claude 안에서 /plugin — 아래 안내)'
$mps = @('anthropics/claude-plugins-official','ckelsoe/prompt-architect','obra/superpowers','bradautomates/claude-video','Lum1104/Understand-Anything','rohitg00/agentmemory','muratcankoylan/Agent-Skills-for-Context-Engineering','fivetaku/fablize')
if (Has claude) { foreach ($m in $mps) { claude plugin marketplace add $m 2>$null | Out-Null }; Ok "마켓플레이스 $($mps.Count)개 등록 시도 (실패해도 Claude 안에서 /plugin 으로 됨)" }

# ---------------------------------------------------------------------------
Step '끝 — 사람이 직접 해야 하는 것'
Write-Host @"

  1) 로그인
     claude                → 브라우저 로그인 (사무실과 같은 Anthropic 계정)
     codex login           → ChatGPT 계정 (Pro 여야 gpt-6-astra 가 목록에 뜬다)
     gh auth login         → (선택) GitHub

  2) Codex 첫 실행
     codex  →  "1. Set up default sandbox" 선택  →  관리자 창에서 '예'  →  Sandbox ready
     (이걸 안 하면 집에서 겪은 "권한이 안 된다" 가 그대로 난다)

  3) 키 파일 — USB로 직접 복사 (팩에는 일부러 안 넣었다)
     사무실 PC  C:\Users\TheRose\Desktop\로또의 주식\.env      →  $PROJECT\.env   (69줄)
     사무실 PC  C:\Users\TheRose\.config\watch\.env             →  $HOME_\.config\watch\.env

  4) Claude 플러그인 8개 — claude 를 열고 /plugin 에서 설치 (settings.json 에 이미 '켬' 으로 적혀 있어 설치만 하면 된다)
     superpowers · frontend-design (claude-plugins-official)
     prompt-architect · watch(claude-video) · understand-anything · context-engineering · agentmemory · fablize

  5) 크롬 확장 (둘 다 사람이 눌러야 깔린다)
     Claude in Chrome  — https://claude.ai/chrome
     Codex chrome 플러그인 — codex 안에서:  codex plugin add chrome@openai-bundled  → 확장 설치 안내 따라가기

  6) 확인
     claude --version / codex --version / python --version / node --version
     cd "$PROJECT"; py tools/track.py list
     PowerShell 새로 열기 → cmd 를 열면 Codex 가 바로 떠야 한다

"@ -ForegroundColor White
