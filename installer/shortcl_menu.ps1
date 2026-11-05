# 숏클 시작 메뉴 — 파워쉘을 켜면 프로필이 부른다(관제 294, 사장님 11-01 "계정 보이고 숫자 한 번").
# 엔터만 치면 일반 파워쉘로 넘어간다.
param([string]$Work, [switch]$LoginOnly)
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
$local = Join-Path $env:USERPROFILE '.local\bin'
if (-not (Get-Command claude -ErrorAction SilentlyContinue) -and (Test-Path (Join-Path $local 'claude.exe'))) { $env:Path = "$local;$env:Path" }
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { return }
# Claude 로그인(판단 주인 — install.ps1 도 -LoginOnly 로 이것을 부른다. 관제 310)
#   claude auth login 의 코드 칸은 붙인 글이 안 보이고 컨트롤+V 가 안 들어간다(11-03 샌드박스 실측, 오른쪽 클릭만 됨).
#   그래서 코드는 파워쉘 입력 칸(보이고 컨트롤+V 됨)에서 받아 claude 표준입력으로 넘긴다(넘긴 코드도 검사됨 — 11-03 실측).
function Invoke-ShortclLogin {
    $cmd = Get-Command claude -ErrorAction SilentlyContinue
    if (-not $cmd -or $cmd.CommandType -ne 'Application') { & claude auth login; return }   # 시험(가짜 claude)
    for ($try = 1; $try -le 3; $try++) {
        $psi = New-Object Diagnostics.ProcessStartInfo
        $psi.FileName = $cmd.Source
        $psi.Arguments = 'auth login'
        $psi.UseShellExecute = $false
        $psi.RedirectStandardInput = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $p = [Diagnostics.Process]::Start($psi)
        $errT = $p.StandardError.ReadToEndAsync()
        $buf = New-Object Text.StringBuilder
        $arr = New-Object char[] 4096
        $sw = [Diagnostics.Stopwatch]::StartNew()
        $ready = $false
        while ($sw.Elapsed.TotalSeconds -lt 60) {          # 'Paste code here' 가 뜰 때까지 — 모든 기다림에 시간 상한(출력이 멈추면 창도 멈춘다)
            $t = $p.StandardOutput.ReadAsync($arr, 0, $arr.Length)
            if (-not $t.Wait([int](60000 - $sw.ElapsedMilliseconds) + 1)) { break }
            if ($t.Result -le 0) { break }
            [void]$buf.Append($arr, 0, $t.Result)
            if ($buf.ToString() -match 'Paste code here') { $ready = $true; break }
        }
        if (-not $ready) {
            try { $p.Kill() } catch {}
            Write-Host '  로그인 창을 열지 못했습니다. 다시 시도합니다.' -ForegroundColor Yellow
            continue
        }
        $url = [regex]::Match($buf.ToString(), 'https://\S+').Value
        Write-Host '  브라우저에서 Claude 에 로그인하고 [승인]을 누르세요. 코드 화면이 나오면 [복사].'
        if ($url) { Write-Host "  브라우저가 안 열리면 이 주소를 여세요: $url" -ForegroundColor DarkGray }
        $code = ''
        while (-not $code) {
            $raw = Read-Host '  코드를 붙여 넣고 엔터 (컨트롤+V 또는 오른쪽 클릭)'
            $raw = ($raw -replace '\s', '')
            if ($raw -match '^[A-Za-z0-9_\-]{20,}#[A-Za-z0-9_\-]{10,}$') { $code = $raw }
            elseif ($raw) { Write-Host '  코드 모양이 아닙니다. 브라우저 코드 화면의 [복사]를 다시 누르고 붙여 넣어 주세요.' -ForegroundColor Yellow }
        }
        $outT = $p.StandardOutput.ReadToEndAsync()
        try { $p.StandardInput.WriteLine($code); $p.StandardInput.Close() } catch {}
        if (-not $p.WaitForExit(60000)) { try { $p.Kill() } catch {} }
        $rest = ''
        if ($outT.Wait(5000)) { $rest += $outT.Result }
        if ($errT.Wait(5000)) { $rest += $errT.Result }
        $st = $null
        try { $st = (& claude auth status 2>$null | Out-String) | ConvertFrom-Json } catch {}
        if ($st -and $st.loggedIn) { Write-Host "  로그인 완료: $($st.email)" -ForegroundColor Green; return }
        $why = [regex]::Match($rest, 'Login failed:[^\r\n]*').Value
        if ($why) { Write-Host "  $why" -ForegroundColor DarkGray }
        if ($try -lt 3) { Write-Host '  코드가 받아들여지지 않았습니다(만료·이전 코드). 로그인 창을 새로 엽니다 — 새 코드로 다시 붙여 주세요.' -ForegroundColor Yellow }
        else { Write-Host '  3번 모두 받아들여지지 않았습니다.' -ForegroundColor Yellow }
    }
}
if ($LoginOnly) { Invoke-ShortclLogin; return }
$info = $null
try { $info = (& claude auth status 2>$null | Out-String) | ConvertFrom-Json } catch {}
$who = if ($info -and $info.loggedIn) { "$($info.email) · $($info.subscriptionType)" } else { '로그인 안 됨' }
Write-Host ''
Write-Host '  숏클메이커' -ForegroundColor Green
Write-Host "  현재 계정: $who"
Write-Host ''
Write-Host '  [1] 숏클 시작'
Write-Host '  [2] 다른 Claude 계정으로 로그인 (관리자 승인 필요)'
Write-Host '  [엔터] 일반 파워쉘'
Write-Host ''
$loggedIn = [bool]($info -and $info.loggedIn)
# 번호 칸에 다른 글을 넣어도 조용히 끝내지 않는다(11-02 사장님 '많은 사람들이 계속 저래') — 로그인 코드면 로그인 창을 다시 열고, 그 밖의 글이면 다시 묻는다
while ($true) {
    $pick = (Read-Host '  번호').Trim()
    if ($pick -in @('', '1', '2') -or $pick -match "^\`$env:SHORTEM_START=") { break }
    if ($pick -match '^[A-Za-z0-9_\-]{20,}#[A-Za-z0-9_\-]{10,}$' -and -not $loggedIn) {
        Write-Host '  이 칸은 번호 칸이라 코드가 들어가지 않았습니다. 로그인 창을 다시 엽니다.' -ForegroundColor Yellow
        Write-Host '  브라우저에서 승인을 다시 누르고, 새 코드를 이 아래 입력 칸에 붙여 넣어 주세요.' -ForegroundColor Yellow
        $pick = '1'
        break
    }
    Write-Host '  1 또는 2 를 누르고 엔터를 쳐 주세요(일반 파워쉘은 엔터만).' -ForegroundColor Yellow
}
# 이 칸에 설치 줄을 붙여 넣는 회원이 많다(11-02 실측) — 우리 주소의 그 한 줄만 그대로 이어서 실행한다
if ($pick -match "^\`$env:SHORTEM_START='[A-Za-z0-9._-]+';\s*irm https://stmaker\.kr/api/claude/start\.ps1 \| iex$") {
    Invoke-Expression $pick
    return
}
if ($pick -eq '2' -or ($pick -eq '1' -and -not $loggedIn)) {
    if ($pick -eq '2') { & claude auth logout 2>$null | Out-Null }
    Invoke-ShortclLogin
    $pick = '1'
    $after = $null
    try { $after = (& claude auth status 2>$null | Out-String) | ConvertFrom-Json } catch {}
    if (-not ($after -and $after.loggedIn)) {
        Write-Host '  로그인이 끝나지 않았습니다. 파워쉘을 새로 열고 1 을 눌러 다시 해 주세요.' -ForegroundColor Yellow
        return
    }
}
if ($pick -eq '1') {
    Set-Location -LiteralPath $Work
    & claude
}
