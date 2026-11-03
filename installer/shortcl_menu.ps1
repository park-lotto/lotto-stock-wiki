# 숏클 시작 메뉴 — 파워쉘을 켜면 프로필이 부른다(관제 294, 사장님 11-01 "계정 보이고 숫자 한 번").
# 엔터만 치면 일반 파워쉘로 넘어간다.
param([string]$Work)
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
$local = Join-Path $env:USERPROFILE '.local\bin'
if (-not (Get-Command claude -ErrorAction SilentlyContinue) -and (Test-Path (Join-Path $local 'claude.exe'))) { $env:Path = "$local;$env:Path" }
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { return }
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
    Write-Host '  브라우저에서 승인하세요. 코드 화면이 나오면 [복사]를 눌러 여기에 붙여 넣고 엔터. 다른 글자를 넣어 Invalid code 가 떠도 그대로 코드만 다시 붙이면 됩니다.'
    & claude auth login
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
