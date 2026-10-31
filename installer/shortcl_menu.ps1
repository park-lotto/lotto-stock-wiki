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
Write-Host '  [2] 다른 Claude 계정으로 로그인'
Write-Host '  [엔터] 일반 파워쉘'
Write-Host ''
$pick = (Read-Host '  번호').Trim()
if ($pick -eq '2' -or ($pick -eq '1' -and -not ($info -and $info.loggedIn))) {
    if ($pick -eq '2') { & claude auth logout 2>$null | Out-Null }
    & claude auth login
    $pick = '1'
}
if ($pick -eq '1') {
    Set-Location -LiteralPath $Work
    & claude
}
