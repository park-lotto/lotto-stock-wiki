@echo off
title 캡컷 자동 설정 - 숏템메이커
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

REM 3) 캡컷 설정 파일 확인 - 없는 이유를 갈라서 알려준다(2026-08-25).
REM    예전엔 "찾지 못했습니다" 한 줄뿐이라 고객이 뭘 해야 하는지 몰랐다.
REM    캡컷 미설치 / 설치는 했는데 로그인 전 - 이 둘은 처방이 다르다.
set "CFG=%LOCALAPPDATA%\CapCut\User Data\Config\globalSetting"
if not exist "%CFG%" (
  echo.
  if not exist "%LOCALAPPDATA%\CapCut" (
    echo   [!] 이 PC에 캡컷이 설치되어 있지 않습니다.
    echo.
    echo       먼저 캡컷 PC 버전을 설치해 주세요.
    echo       설치 주소: https://www.capcut.com/ko-kr/
    echo       설치한 뒤 캡컷을 한 번 켜서 로그인까지 하시고,
    echo       이 파일을 다시 더블클릭해 주세요.
  ) else (
    echo   [!] 캡컷은 설치되어 있는데, 설정 파일이 아직 없습니다.
    echo.
    echo       캡컷을 한 번도 켜지 않았거나 로그인을 안 하신 경우입니다.
    echo       캡컷은 로그인을 해야 설정 파일을 만듭니다.
    echo.
    echo       1. 캡컷을 켜고 로그인하세요
    echo       2. 캡컷을 완전히 종료하세요
    echo       3. 이 파일을 다시 더블클릭하세요
  )
  echo.
  echo   ------------------------------------------------
  echo   폴더는 만들어 두었습니다: C:\capcutproject\CapCut Drafts
  echo   ------------------------------------------------
  echo.
  pause
  exit /b 1
)

REM 4) 저장 위치 설정 (currentCustomDraftPath) - 백슬래시는 [char]92로 더블 생성(캡컷 형식),
REM    다른 설정은 그대로 두고 그 한 줄만 교체, 원본은 .bak으로 백업
powershell -NoProfile -Command "$c=$env:LOCALAPPDATA+'\CapCut\User Data\Config\globalSetting'; Copy-Item -LiteralPath $c -Destination ($c+'.bak') -Force; $d=[char]92+[char]92; $v='currentCustomDraftPath=C:'+$d+'capcutproject'+$d+'CapCut Drafts'; $found=$false; $out=foreach($ln in (Get-Content -LiteralPath $c)){ if($ln -like 'currentCustomDraftPath=*'){ $found=$true; $v } else { $ln } }; if(-not $found){ $out+=$v }; $enc=New-Object System.Text.UTF8Encoding($false); [System.IO.File]::WriteAllLines($c,$out,$enc)"

if errorlevel 1 (
  echo   [!] 설정 중 오류가 발생했습니다. 다시 시도하거나 문의해 주세요.
  echo.
  pause
  exit /b 1
)

REM 5) 진짜로 들어갔는지 다시 읽어서 확인한다(2026-08-25).
REM    powershell이 exit 0을 줘도 값이 안 들어갈 수 있다. "완료!"만 띄우면
REM    고객은 됐다고 믿고 캡컷을 켰다가 프로젝트가 안 보여 다시 문의한다.
REM    실제 파일에서 값을 되읽어 화면에 보여주면 캡쳐 한 장으로 판별된다.
set "VERIFY="
for /f "delims=" %%A in ('findstr /i /b /c:"currentCustomDraftPath=" "%CFG%"') do set "VERIFY=%%A"

echo.
echo   ============================================
if defined VERIFY (
  echo      [O] 설정 완료!  이제 캡컷을 켜시면 됩니다.
  echo   ============================================
  echo.
  echo   확인된 저장 위치:
  echo     %VERIFY%
) else (
  echo      [!] 설정이 기록되지 않았습니다.
  echo   ============================================
  echo.
  echo   캡컷을 완전히 끈 상태에서 다시 더블클릭해 주세요.
  echo   그래도 같으면 이 화면을 캡쳐해서 문의해 주세요.
  echo.
  pause
  exit /b 1
)
echo.
echo       제작소에서 [캡컷으로 보내기]를 누르면
echo       프로젝트가 이 폴더에 자동으로 만들어집니다.
echo.
echo       캡컷이 이미 켜져 있었다면 껐다가 다시 켜주세요.
echo.
pause
exit /b 0
