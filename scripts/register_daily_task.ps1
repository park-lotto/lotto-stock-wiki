# 매일 아침 7시 브리핑 자동 실행 — Windows 작업 스케줄러 등록
$TaskName = "로또주식_데일리브리핑"
$PythonPath = (Get-Command python).Source
$ScriptPath = "c:\Users\TheRose\Desktop\로또의 주식\scripts\yt_daily_briefing.py"
$WorkDir = "c:\Users\TheRose\Desktop\로또의 주식"

# 기존 작업 제거 (있으면)
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument $ScriptPath `
    -WorkingDirectory $WorkDir

$Trigger = New-ScheduledTaskTrigger -Daily -At "07:00"

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -RestartCount 1 `
    -RestartInterval (New-TimeSpan -Minutes 10)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -RunLevel Highest `
    -Force

Write-Host ""
Write-Host "✅ 작업 등록 완료: '$TaskName'"
Write-Host "   실행 시간: 매일 오전 07:00"
Write-Host "   스크립트: $ScriptPath"
Write-Host ""
Write-Host "확인: Get-ScheduledTask -TaskName '$TaskName'"
Write-Host "수동실행: Start-ScheduledTask -TaskName '$TaskName'"
