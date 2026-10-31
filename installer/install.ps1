# 숏클 설치 - 회원이 받은 시작.md 의 한 줄이 부른다(관제 294, 사장님 11-01 "시작md 만 넣으면 바로").
# 회원 입력 0: 인증값(SHORTEM_START)은 시작.md 에 들어 있고, 키는 이 스크립트가 받아 파일로만 저장한다(화면·대화에 내지 않는다).
# 판단 주인: 키·인증 = shopping_shorts/claude_portal.py start_redeem · 묶음 = install_info · 풀기 후 검사 = postinstall.js.
# 시험 환경변수: SHORTEM_BASE · SHORTEM_INSTALL_DIR · SHORTEM_NO_PERSIST(사용자 환경변수 안 씀) · SHORTEM_NO_LAUNCH(새 창 안 띄움)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Say($m) { Write-Host "[숏클] $m" }
function Die($m) { Write-Host "[숏클] 설치를 마치지 못했습니다: $m" -ForegroundColor Red; throw $m }

$base = if ($env:SHORTEM_BASE) { $env:SHORTEM_BASE.TrimEnd('/') } else { '__BASE__' }
$token = $env:SHORTEM_START
if (-not $token) { Die '시작.md 를 숏템메이커 페이지에서 새로 받아 주세요' }

Say '회원 확인 중'
try {
    $auth = Invoke-RestMethod -Method Post -Uri "$base/api/claude/start/redeem" -Headers @{ 'X-Shortem-Start' = $token }
} catch {
    Die '회원 확인이 안 됐습니다. 페이지에서 시작.md 를 새로 받아 주세요'
}
$key = [string]$auth.key
if (-not $key) { Die '회원 확인 응답이 비었습니다' }

Say '설치 묶음 확인 중'
$info = Invoke-RestMethod -Uri "$base/api/claude/install?plat=win-x64" -Headers @{ Authorization = "Bearer $key" }
if (-not $info.ready) { Die '설치 묶음이 아직 준비되지 않았습니다. 잠시 뒤 다시 해 주세요' }
if ($info.version -notmatch '^\d+\.\d+\.\d+$' -or $info.sha256 -notmatch '^[0-9a-f]{64}$') { Die '서버 응답이 올바르지 않습니다' }

# 바탕화면 경로가 빈 값인 환경이 있다(11-01 빈 사용자 시험) — 없으면 사용자 폴더 아래로 만든다
$desktop = [Environment]::GetFolderPath('Desktop')
if (-not $desktop) { $desktop = Join-Path $env:USERPROFILE 'Desktop' }
New-Item -ItemType Directory -Force -Path $desktop | Out-Null

$homeDir = if ($env:SHORTEM_INSTALL_DIR) { $env:SHORTEM_INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA 'Shortem' }
$parent = Split-Path $homeDir -Parent
New-Item -ItemType Directory -Force -Path $parent | Out-Null
$node = Join-Path $homeDir 'tools\node\node.exe'

$current = $null
try { $current = (Get-Content (Join-Path $homeDir 'install.json') -Raw -Encoding UTF8 | ConvertFrom-Json).version } catch {}
if ($current -eq $info.version -and (Test-Path $node)) {
    Say "이미 최신입니다($current)"
} else {
    $drive = (Get-Item $parent).PSDrive
    $needGb = [math]::Ceiling(([double]$info.size) * 4 / 1GB)
    if ($drive.Free -lt ([double]$info.size) * 4) { Die "디스크 여유가 부족합니다. ${needGb}GB 이상 비워 주세요" }
    $gb = [math]::Round(([double]$info.size) / 1GB, 1)
    Say "내려받는 중(약 ${gb}GB, 끊겨도 이어 받습니다)"
    $zip = Join-Path $parent 'Shortem.download.part'
    $url = if ($info.url -like "http*") { $info.url } else { "$base/" + ([string]$info.url).TrimStart("/") }
    & curl.exe -# -fL --retry 5 --retry-delay 5 -C - -o $zip $url
    if ($LASTEXITCODE -ne 0) {
        Remove-Item $zip -Force -ErrorAction SilentlyContinue
        Die "내려받기 실패(curl $LASTEXITCODE). 다시 시도해 주세요"
    }
    Say '받은 파일 확인 중'
    if ((Get-FileHash $zip -Algorithm SHA256).Hash.ToLower() -ne $info.sha256) {
        Remove-Item $zip -Force -ErrorAction SilentlyContinue
        Die '받은 파일 확인값이 다릅니다. 다시 시도해 주세요'
    }
    Say '푸는 중(몇 분 걸립니다)'
    $fresh = "$homeDir.new"
    if (Test-Path $fresh) { Remove-Item $fresh -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $fresh | Out-Null
    & "$env:SystemRoot\System32\tar.exe" -xf $zip -C $fresh
    if ($LASTEXITCODE -ne 0) { Die "풀기 실패(tar $LASTEXITCODE)" }
    if (-not (Test-Path (Join-Path $fresh 'tools\tools.manifest.json')) -or -not (Test-Path (Join-Path $fresh 'server\index.js'))) { Die '풀린 묶음이 덜 찼습니다' }
    $old = $null
    if (Test-Path $homeDir) { $old = "$homeDir.old-$(Get-Date -Format yyyyMMddHHmmss)"; Rename-Item $homeDir $old }
    Rename-Item $fresh $homeDir
    & $node (Join-Path $homeDir 'postinstall.js') --home $homeDir --version $info.version --desktop $desktop
    if ($LASTEXITCODE -ne 0) {
        Remove-Item $homeDir -Recurse -Force
        if ($old) { Rename-Item $old $homeDir }
        Die "설치 파일 확인 실패($LASTEXITCODE)"
    }
    Remove-Item $zip -Force -ErrorAction SilentlyContinue
    if ($old) { Remove-Item $old -Recurse -Force -ErrorAction SilentlyContinue }
}

Say '회원 키 저장 중'
$lic = [Uri]::new((Join-Path $homeDir 'server\license.js')).AbsoluteUri
$env:SHORTEM_K = $key
& $node --input-type=module -e "const m=await import('$lic');m.saveLicense(process.env.SHORTEM_K)"
$saved = $LASTEXITCODE
Remove-Item Env:SHORTEM_K
Remove-Variable key
if ($saved -ne 0) { Die '회원 키 저장 실패' }

if (-not $env:SHORTEM_NO_PERSIST) {
    [Environment]::SetEnvironmentVariable('SHORTEM_INSTALL', $homeDir, 'User')
    [Environment]::SetEnvironmentVariable('SHORTEM_NODE', $node, 'User')
}
$env:SHORTEM_INSTALL = $homeDir
$env:SHORTEM_NODE = $node

if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    $local = Join-Path $env:USERPROFILE '.local\bin'
    if (-not (Test-Path (Join-Path $local 'claude.exe'))) {
        Say 'Claude Code 설치 중'
        # 별도 창 없이 자식 프로세스로 — 같은 범위에서 iex 하면 공식 스크립트가 이 스크립트 변수를 덮어쓴다(11-01 새 PC 시험)
        & powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://claude.ai/install.ps1 | iex"
    }
    $env:Path = "$local;$env:Path"
    if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { Die 'Claude Code 설치를 확인하지 못했습니다' }
    if (-not $env:SHORTEM_NO_PERSIST) {     # 공식 설치는 PATH 를 안 넣는다 — 다음에 켜는 창에서도 찾게 사용자 PATH 에 넣는다
        $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
        if (($userPath -split ';') -notcontains $local) {
            [Environment]::SetEnvironmentVariable('Path', ($userPath.TrimEnd(';') + ";$local"), 'User')
        }
    }
}

Say '숏클 연결 중'
$eap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$plugin = (Join-Path $homeDir 'claude-plugin')
$null = & claude plugin marketplace add $plugin 2>&1
$null = & claude plugin marketplace update shortem 2>&1
$null = & claude plugin install 'shortem@shortem' 2>&1
$listed = (& claude plugin list 2>&1 | Out-String)
$ErrorActionPreference = $eap
if ($listed -notmatch 'shortem') { Die '숏클 플러그인 등록을 확인하지 못했습니다' }

$work = Join-Path $desktop '숏템작업'
New-Item -ItemType Directory -Force -Path $work | Out-Null

# 첫 실행의 글자 스타일 선택·폴더 신뢰 확인을 미리 끝낸다(회원이 누를 것을 없앤다, 11-01 첫 화면 실측). 로그인은 회원 몫이다.
$cfgDir = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { $null }
$cfg = if ($cfgDir) { Join-Path $cfgDir '.claude.json' } else { Join-Path $env:USERPROFILE '.claude.json' }
$seed = @'
const fs = require('fs');
const [cfg, work] = process.argv.slice(1);
let j = {};
if (fs.existsSync(cfg)) j = JSON.parse(fs.readFileSync(cfg, 'utf8'));
if (!j.theme) j.theme = 'dark';
j.hasCompletedOnboarding = true;
j.hasCompletedClaudeInChromeOnboarding = true;      // 크롬 확장이 있는 PC 에서 첫 화면이 멈춘다(11-01 실측)
if (j.claudeInChromeDefaultEnabled === undefined) j.claudeInChromeDefaultEnabled = false;
j.projects = j.projects || {};
const key = work.replace(/\\/g, '/');
j.projects[key] = Object.assign({}, j.projects[key], { hasTrustDialogAccepted: true });
const tmp = cfg + '.shortem.tmp';
fs.writeFileSync(tmp, JSON.stringify(j, null, 2));
fs.renameSync(tmp, cfg);
'@
& $node -e $seed $cfg $work
if ($LASTEXITCODE -ne 0) { Say '첫 화면 설정은 건너뜁니다' }
$local = Join-Path $work '.claude'
New-Item -ItemType Directory -Force -Path $local | Out-Null
$allow = Join-Path $local 'settings.json'
if (-not (Test-Path $allow)) {
    $rules = '{"permissions":{"allow":["mcp__plugin_shortem_shortem","Skill(shortem:setup)","Skill(shortem:make)","Skill(shortem:script)"]}}'
    [IO.File]::WriteAllText($allow, $rules, (New-Object Text.UTF8Encoding($false)))
}
# 파워쉘을 켜면 뜨는 시작 메뉴. 프로필에는 영문 표시 구간만 넣는다(기존 내용은 그대로, 다시 설치해도 한 번만).
$menuRaw = Invoke-RestMethod -Uri "$base/api/claude/start_menu.ps1"
$menu = Join-Path $homeDir 'shortcl_menu.ps1'
[IO.File]::WriteAllText($menu, ($menuRaw -replace "^\uFEFF", ''), (New-Object Text.UTF8Encoding($true)))
$prof = if ($env:SHORTEM_PROFILE) { $env:SHORTEM_PROFILE } else { $PROFILE.CurrentUserCurrentHost }
New-Item -ItemType Directory -Force -Path (Split-Path $prof -Parent) | Out-Null
$block = @"
# >>> shortcl >>>
if ([Environment]::UserInteractive -and `$Host.Name -eq 'ConsoleHost' -and -not `$env:CLAUDECODE -and ([Environment]::GetCommandLineArgs().Count -le 1)) { & '$menu' -Work '$work' }
# <<< shortcl <<<
"@
$old = if (Test-Path $prof) { [IO.File]::ReadAllText($prof) } else { '' }
$new = [regex]::Replace($old, '(?s)\r?\n?# >>> shortcl >>>.*?# <<< shortcl <<<\r?\n?', '')
$new = $new.TrimEnd() + $(if ($new.Trim()) { "`r`n" } else { '' }) + $block + "`r`n"
[IO.File]::WriteAllText($prof, $new, (New-Object Text.UTF8Encoding($true)))
if (-not $env:SHORTEM_NO_PERSIST -and (Get-ExecutionPolicy -Scope CurrentUser) -in @('Undefined', 'Restricted') -and (Get-ExecutionPolicy) -eq 'Restricted') {
    Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
}

Say '설치 완료'
if (-not $env:SHORTEM_NO_LAUNCH) {
    # 온보딩을 건너뛰면 Claude 가 로그인 화면을 안 띄우고 /login 을 치라고만 한다(11-01 실측) — 여기서 먼저 로그인시킨다
    $eap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $logged = (& claude auth status 2>&1 | Out-String) -match '"loggedIn":\s*true'
    if (-not $logged) {
        Say '브라우저가 열립니다. Claude 에 로그인하고 승인 버튼만 눌러 주세요'
        & claude auth login
        $logged = (& claude auth status 2>&1 | Out-String) -match '"loggedIn":\s*true'
    }
    $ErrorActionPreference = $eap
    if (-not $logged) { Die 'Claude 로그인이 끝나지 않았습니다. 같은 줄을 다시 붙여 넣고 엔터를 눌러 주세요' }
    Say '준비 점검을 시작합니다'
    if ($env:CLAUDECODE) {
        # Claude 안에서 실행됐으면 그 안에 또 띄울 수 없어 새 창으로 연다(-WorkingDirectory 는 Windows Terminal 에서 무시돼 창 안에서 옮긴다)
        $env:SHORTEM_WORK_DIR = $work
        Start-Process powershell -ArgumentList '-NoExit', '-Command', 'Set-Location -LiteralPath $env:SHORTEM_WORK_DIR; claude ''숏클 점검 준비해줘'''
    } else {
        # 창이 둘이면 헷갈린다(사장님 11-01) — 붙여 넣은 그 창이 그대로 Claude 가 된다
        Set-Location -LiteralPath $work
        & claude '숏클 점검 준비해줘'
    }
}
