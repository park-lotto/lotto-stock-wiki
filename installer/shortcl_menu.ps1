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
$pick = (Read-Host '  번호').Trim()
# 이 칸에 설치 줄을 붙여 넣는 회원이 많다(11-02 실측) — 우리 주소의 그 한 줄만 그대로 이어서 실행한다
if ($pick -match "^\`$env:SHORTEM_START='[A-Za-z0-9._-]+';\s*irm https://stmaker\.kr/api/claude/start\.ps1 \| iex$") {
    Invoke-Expression $pick
    return
}
if ($pick -eq '2' -or ($pick -eq '1' -and -not ($info -and $info.loggedIn))) {
    if ($pick -eq '2') { & claude auth logout 2>$null | Out-Null }
    Write-Host '  브라우저에서 승인하세요. 코드 화면이 나오면 [복사]를 눌러 여기에 붙여 넣고 엔터. 다른 글자를 넣어 Invalid code 가 떠도 그대로 코드만 다시 붙이면 됩니다.'
    & claude auth login
    $pick = '1'
}
if ($pick -eq '1') {
    Set-Location -LiteralPath $Work
    & claude
}
