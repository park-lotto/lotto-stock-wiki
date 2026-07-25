@echo off
chcp 65001 >nul
title 캡컷 자동 설정 - 쇼핑쇼츠
echo.
echo   ============================================
echo      캡컷 자동 설정  (최초 한 번만 실행)
echo   ============================================
echo.
echo   - 폴더 만들기: C:\capcutproject\CapCut Drafts
echo   - 캡컷 프로젝트 저장 위치를 그 폴더로 설정
echo.

REM 1) 캡컷이 실행 중이면 중단 (실행 중 고치면 캡컷이 종료할 때 되돌려버림)
tasklist /fi "imagename eq CapCut.exe" 2>nul | find /i "CapCut.exe" >nul
if not errorlevel 1 (
  echo   [!] 캡컷이 켜져 있습니다. 캡컷을 완전히 종료한 뒤 이 파일을 다시 실행해 주세요.
  echo.
  pause
  exit /b 1
)

REM 2) 폴더 생성
if not exist "C:\capcutproject\CapCut Drafts" mkdir "C:\capcutproject\CapCut Drafts"

REM 3) 캡컷 설정 파일 확인
set "CFG=%LOCALAPPDATA%\CapCut\User Data\Config\globalSetting"
if not exist "%CFG%" (
  echo   [!] 캡컷 설정 파일을 찾지 못했습니다.
  echo       캡컷을 한 번 실행하고 로그인까지 한 뒤 다시 시도해 주세요.
  echo.
  pause
  exit /b 1
)

REM 4) 저장 위치 설정 (currentCustomDraftPath) — 백슬래시는 [char]92로 더블 생성(캡컷 형식),
REM    다른 설정은 그대로 두고 그 한 줄만 교체, 원본은 .bak으로 백업
powershell -NoProfile -Command "$c=$env:LOCALAPPDATA+'\CapCut\User Data\Config\globalSetting'; Copy-Item -LiteralPath $c -Destination ($c+'.bak') -Force; $d=[char]92+[char]92; $v='currentCustomDraftPath=C:'+$d+'capcutproject'+$d+'CapCut Drafts'; $found=$false; $out=foreach($ln in (Get-Content -LiteralPath $c)){ if($ln -like 'currentCustomDraftPath=*'){ $found=$true; $v } else { $ln } }; if(-not $found){ $out+=$v }; $enc=New-Object System.Text.UTF8Encoding($false); [System.IO.File]::WriteAllLines($c,$out,$enc)"

if errorlevel 1 (
  echo   [!] 설정 중 오류가 발생했습니다. 다시 시도하거나 문의해 주세요.
  echo.
  pause
  exit /b 1
)

echo.
echo   [O] 설정 완료!  이제 캡컷을 켜시면 됩니다.
echo.
echo       제작소에서 [캡컷으로 보내기]를 누르면
echo       프로젝트가 이 폴더에 자동으로 만들어집니다.
echo.
pause
exit /b 0
