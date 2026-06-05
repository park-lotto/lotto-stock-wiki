# StockBrainBriefing — 평일(월~금) 07:40만 실행으로 변경
# 관리자 PowerShell에서 실행: ! powershell -ExecutionPolicy Bypass -File "C:\Users\CH\Desktop\로또의 주식\scripts\briefing\set_schedule_weekday.ps1"

$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At "07:40AM"
Set-ScheduledTask -TaskName "StockBrainBriefing" -Trigger $trigger
Write-Host "✅ StockBrainBriefing → 평일(월~금) 07:40 설정 완료"

# 확인
$t = (Get-ScheduledTask -TaskName "StockBrainBriefing").Triggers
Write-Host "다음 실행: $((Get-ScheduledTask -TaskName 'StockBrainBriefing' | Get-ScheduledTaskInfo).NextRunTime)"
