# 이 PC 를 관제 구성으로 맞춘다 (카드 046). 여러 번 돌려도 같은 결과(멱등).
#   powershell -ExecutionPolicy Bypass -File tools\pc_setup.ps1 -Label 회사
# 하는 일: PC 이름(.claude-pc.json) · 창 설정/감시기/관제창.bat 복사 · 전역 settings.json 에
#          텔레그램 플러그인 끔(관제창.bat 만 켬) + 원격 조종 자동. 바꿀 것을 먼저 보여주고 Y/N.
param([Parameter(Mandatory)][ValidateSet('집', '회사')][string]$Label)
$ErrorActionPreference = 'Stop'
$src = Join-Path $PSScriptRoot 'pc'
$userDir = $env:USERPROFILE
$plan = @()

# 1) PC 이름
$pcJson = Join-Path $userDir '.claude-pc.json'
$want = (@{ label = $Label } | ConvertTo-Json -Compress)
if (-not (Test-Path $pcJson) -or (Get-Content $pcJson -Raw -Encoding UTF8).Trim() -ne $want) {
    $plan += "PC 이름 = $Label ($pcJson)"
}

# 2) 사용자 폴더 설치물
$copies = @(
    @{ from = 'claude-remote-settings.json'; to = (Join-Path $userDir 'claude-remote-settings.json') },
    @{ from = 'claude-telegram-on.json';     to = (Join-Path $userDir 'claude-telegram-on.json') },
    @{ from = 'telegram-guard.ps1';          to = (Join-Path $userDir 'telegram-guard.ps1') },
    @{ from = '관제창.bat';                   to = (Join-Path ([Environment]::GetFolderPath('Desktop')) '관제창.bat') }
)
foreach ($c in $copies) {
    $f = Join-Path $src $c.from
    if (-not (Test-Path $c.to) -or (Get-FileHash $f).Hash -ne (Get-FileHash $c.to).Hash) {
        $plan += "복사 $($c.from) → $($c.to)"
    }
}

# 3) 전역 설정: 텔레그램 플러그인 끔(봇 수신자는 관제창 하나 — 409) + 모든 창 원격 조종
$settings = Join-Path $userDir '.claude\settings.json'
$s = if (Test-Path $settings) { Get-Content $settings -Raw -Encoding UTF8 | ConvertFrom-Json } else { [pscustomobject]@{} }
$needTg = -not ($s.enabledPlugins -and $s.enabledPlugins.'telegram@claude-plugins-official' -eq $false)
$needRc = -not ($s.remoteControlAtStartup -eq $true)
if ($needTg) { $plan += 'settings.json: 텔레그램 플러그인 끔 (관제창.bat 만 켬)' }
if ($needRc) { $plan += 'settings.json: remoteControlAtStartup = true' }

if (-not $plan) { Write-Host '바꿀 것 없음 — 이미 관제 구성' -ForegroundColor Green; exit 0 }
Write-Host "`n바꿀 것:" -ForegroundColor Yellow
$plan | ForEach-Object { Write-Host "  - $_" }
if ((Read-Host "`n진행할까요? (Y/N)") -ne 'Y') { Write-Host '취소'; exit 1 }

[IO.File]::WriteAllText($pcJson, $want, (New-Object Text.UTF8Encoding $false))
foreach ($c in $copies) { Copy-Item (Join-Path $src $c.from) $c.to -Force }
if ($needTg -or $needRc) {
    if (Test-Path $settings) { Copy-Item $settings "$settings.bak-pcsetup" -Force }
    if (-not $s.enabledPlugins) { $s | Add-Member enabledPlugins ([pscustomobject]@{}) }
    $s.enabledPlugins | Add-Member 'telegram@claude-plugins-official' $false -Force
    $s | Add-Member remoteControlAtStartup $true -Force
    [IO.File]::WriteAllText($settings, ($s | ConvertTo-Json -Depth 20), (New-Object Text.UTF8Encoding $false))
}
Write-Host "`n완료. 남은 것:" -ForegroundColor Green
Write-Host '  1) 바탕화면 관제창.bat 을 켜고 그 안에서  /telegram:configure <이 PC 봇 토큰>'
Write-Host "  2) PowerShell 프로필 계정 메뉴의  `$PcLabel = '$Label'  확인"
