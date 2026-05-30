# setup_nightwatch.ps1
# STOCK BRAIN 나이트워치를 Windows 작업 스케줄러에 등록
# 관리자 권한으로 실행하세요: 우클릭 → "PowerShell로 실행"

$ProjectDir = "c:\Users\TheRose\Desktop\로또의 주식"
$PythonPath = (Get-Command python).Source
$ScriptPath = "$ProjectDir\night_watch.py"
$LogPath    = "$ProjectDir\out\night_logs\scheduler.log"
$TaskName   = "STOCK_BRAIN_NightWatch"

Write-Host "STOCK BRAIN 나이트워치 스케줄러 등록 중..." -ForegroundColor Cyan

# 기존 태스크 제거 (있으면)
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# 매일 밤 11시에 night_watch.py 실행
$Action  = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$ScriptPath`"" `
    -WorkingDirectory $ProjectDir

$Trigger = New-ScheduledTaskTrigger `
    -Daily `
    -At "23:00"

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 10) `
    -RestartCount 1 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "STOCK BRAIN AI 직원 10명 밤새 자동 실행" `
    -RunLevel Highest

Write-Host ""
Write-Host "등록 완료!" -ForegroundColor Green
Write-Host "태스크명: $TaskName"
Write-Host "실행 시각: 매일 밤 23:00"
Write-Host "로그 경로: $LogPath"
Write-Host ""
Write-Host "확인 명령어:" -ForegroundColor Yellow
Write-Host "  Get-ScheduledTask -TaskName '$TaskName'"
Write-Host "  지금 바로 테스트: python night_watch.py --now"
