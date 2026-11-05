# 쿠팡도우미를 윈도 시작 프로그램에 등록(최소화). 유튜브릴레이.lnk 와 같은 방식(관제 315).
$root = Split-Path -Parent $PSScriptRoot
$lnk = Join-Path ([Environment]::GetFolderPath('Startup')) '쿠팡도우미.lnk'
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath = Join-Path $root 'tools\coupang_relay_start.bat'
$s.WorkingDirectory = $root
$s.WindowStyle = 7
$s.Save()
Write-Output "등록: $lnk -> $($s.TargetPath)"
