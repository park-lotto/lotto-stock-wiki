; 숏템 설치팩(윈도 x64) — NSIS 3 · Unicode · 사용자 단위 설치(관리자 권한 불필요)
; 빌드: win/build_win.py 가 makensis /INPUTCHARSET UTF8 /DSTAGE=... /DOUTFILE=... /DVERSION=... 로 부른다.
; 무인 설치:  shortem-setup-win-x64.exe /S [/SANDBOX] [/OPENMCPB] [/D=<설치 폴더>]   (/D 는 맨 끝, 따옴표 없이)
;   /SANDBOX  시험용: 제거 프로그램 등록 키·환경변수 이름을 시험용으로 바꾸고 바탕화면 대신 설치 폴더 안 _sandbox_desktop 에 둔다
;   /OPENMCPB 무인 설치에서도 마지막에 shortem.mcpb 를 연다(기본: 무인이면 안 연다)

Unicode true
ManifestDPIAware true
RequestExecutionLevel user
SetCompressor /SOLID lzma
SetCompressorDictSize 64

!ifndef STAGE
  !error "STAGE(설치할 Shortem 폴더) 를 /DSTAGE= 로 주세요"
!endif
!ifndef OUTFILE
  !define OUTFILE "shortem-setup-win-x64.exe"
!endif
!ifndef VERSION
  !define VERSION "1.0.0"
!endif
!ifndef VERSION4
  !define VERSION4 "${VERSION}.0"
!endif

!define PRODUCT "숏템"
!define PUBLISHER "숏템메이커"
!define UNINST_ROOT "Software\Microsoft\Windows\CurrentVersion\Uninstall"

!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"
!include "WinMessages.nsh"

Name "${PRODUCT}"
Caption "${PRODUCT} 설치팩 ${VERSION}"
OutFile "${OUTFILE}"
InstallDir "$LOCALAPPDATA\Shortem"
BrandingText "${PRODUCT} ${VERSION}"
ShowInstDetails show
ShowUninstDetails show

VIProductVersion "${VERSION4}"
VIAddVersionKey /LANG=1042 "ProductName" "${PRODUCT}"
VIAddVersionKey /LANG=1042 "CompanyName" "${PUBLISHER}"
VIAddVersionKey /LANG=1042 "FileDescription" "${PRODUCT} 설치팩"
VIAddVersionKey /LANG=1042 "FileVersion" "${VERSION}"
VIAddVersionKey /LANG=1042 "ProductVersion" "${VERSION}"
VIAddVersionKey /LANG=1042 "LegalCopyright" "${PUBLISHER}"

; 코드서명 자리 — 인증서가 주어질 때만 build_win.py 가 /DSIGN_CMD="..." 를 넘긴다(%1 = 서명할 파일)
!ifdef SIGN_CMD
  !uninstfinalize '${SIGN_CMD}'
  !finalize '${SIGN_CMD}'
!endif

!define MUI_ICON "${__FILEDIR__}\shortem.ico"
!define MUI_UNICON "${__FILEDIR__}\shortem.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "숏템 설치를 시작합니다"
!define MUI_WELCOMEPAGE_TEXT "숏템이 영상을 만드는 데 쓰는 실행 도구(렌더러·ffmpeg·파이썬)와 숏템 로컬 서버를 이 컴퓨터에 설치합니다.$\r$\n$\r$\n관리자 권한은 필요 없고, 인터넷에서 따로 내려받는 것도 없습니다.$\r$\n$\r$\n설치 위치: 내 사용자 폴더(AppData\Local\Shortem)"
!define MUI_FINISHPAGE_TITLE "숏템 설치가 끝났습니다"
!define MUI_FINISHPAGE_TEXT "Claude Desktop 을 쓰면 아래 '연결하기'를 켠 채로 마침을 누르세요. Claude Desktop 설치 창이 뜨면 라이선스 키를 붙여 넣습니다.$\r$\n$\r$\nClaude Code 를 쓰면 바탕화면 '숏템작업' 폴더의 시작.md 를 Claude Code 입력창에 끌어다 놓고 엔터를 누르세요."
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Claude Desktop 에 숏템 연결하기(shortem.mcpb 열기)"
!define MUI_FINISHPAGE_RUN_FUNCTION OpenMcpb
!define MUI_FINISHPAGE_SHOWREADME
!define MUI_FINISHPAGE_SHOWREADME_TEXT "바탕화면 '숏템작업' 폴더 열기"
!define MUI_FINISHPAGE_SHOWREADME_FUNCTION OpenWorkFolder

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Korean"

Var Sandbox
Var OpenMcpbSilent
Var RegKey
Var EnvSuffix
Var DesktopBase

!macro SetMode
  ${If} $Sandbox == "1"
    StrCpy $RegKey "${UNINST_ROOT}\ShortemSandboxTest"
    StrCpy $EnvSuffix "_SANDBOXTEST"
    StrCpy $DesktopBase "$INSTDIR\_sandbox_desktop"
  ${Else}
    StrCpy $RegKey "${UNINST_ROOT}\Shortem"
    StrCpy $EnvSuffix ""
    StrCpy $DesktopBase "$DESKTOP"
  ${EndIf}
!macroend

Function .onInit
  StrCpy $Sandbox "0"
  StrCpy $OpenMcpbSilent "0"
  ${GetParameters} $R0
  ClearErrors
  ${GetOptions} $R0 "/SANDBOX" $R1
  ${IfNot} ${Errors}
    StrCpy $Sandbox "1"
  ${EndIf}
  ClearErrors
  ${GetOptions} $R0 "/OPENMCPB" $R1
  ${IfNot} ${Errors}
    StrCpy $OpenMcpbSilent "1"
  ${EndIf}
FunctionEnd

Section "숏템" SecMain
  SectionIn RO
  !insertmacro SetMode
  ; 윈도 경로 260자 한계: 설치 폴더 안 가장 긴 상대 경로가 약 125자라 설치 폴더는 120자 이하만 받는다
  StrLen $0 "$INSTDIR"
  ${If} $0 > 120
    ${IfNot} ${Silent}
      MessageBox MB_OK|MB_ICONSTOP "설치 폴더 경로가 너무 깁니다($0자). 기본 위치(AppData\Local\Shortem)에 설치해 주세요."
    ${EndIf}
    SetErrorLevel 4
    Abort
  ${EndIf}
  SetOutPath "$INSTDIR"
  ; 다시 설치(업데이트)면 옛 실행 도구·서버를 비운다 — 숏템 설치 폴더임이 확인될 때만
  ${If} ${FileExists} "$INSTDIR\tools\tools.manifest.json"
    DetailPrint "이전 설치를 정리합니다"
    RMDir /r "$INSTDIR\tools"
    RMDir /r "$INSTDIR\server"
    RMDir /r "$INSTDIR\claude-plugin"
  ${EndIf}
  File /r "${STAGE}\*.*"
  ${If} $Sandbox == "1"
    FileOpen $0 "$INSTDIR\.sandbox" w
    FileWrite $0 "sandbox"
    FileClose $0
  ${EndIf}
  WriteUninstaller "$INSTDIR\uninstall.exe"

  DetailPrint "설치 마무리(시작.md·작업 폴더)"
  nsExec::ExecToLog '"$INSTDIR\tools\node\node.exe" "$INSTDIR\postinstall.js" --home "$INSTDIR" --desktop "$DesktopBase" --version "${VERSION}"'
  Pop $0
  ${If} $0 != "0"
    DetailPrint "설치 마무리 실패(코드 $0)"
    ${IfNot} ${Silent}
      MessageBox MB_OK|MB_ICONSTOP "설치한 파일 확인에 실패했습니다(코드 $0). 디스크 여유를 확인하고 설치팩을 다시 실행해 주세요."
    ${EndIf}
    SetErrorLevel 3
  ${EndIf}

  ; Claude Code 플러그인이 동봉 node·설치 폴더를 찾는 환경변수(사용자 단위)
  WriteRegExpandStr HKCU "Environment" "SHORTEM_INSTALL$EnvSuffix" "$INSTDIR"
  WriteRegExpandStr HKCU "Environment" "SHORTEM_NODE$EnvSuffix" "$INSTDIR\tools\node\node.exe"
  SendMessage ${HWND_BROADCAST} ${WM_SETTINGCHANGE} 0 "STR:Environment" /TIMEOUT=3000

  ; 제거 프로그램 등록(설정 ▸ 앱)
  ${GetSize} "$INSTDIR" "/S=0K" $1 $2 $3
  IntFmt $1 "0x%08X" $1
  WriteRegStr HKCU "$RegKey" "DisplayName" "${PRODUCT}"
  WriteRegStr HKCU "$RegKey" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "$RegKey" "Publisher" "${PUBLISHER}"
  WriteRegStr HKCU "$RegKey" "DisplayIcon" "$INSTDIR\uninstall.exe"
  WriteRegStr HKCU "$RegKey" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "$RegKey" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKCU "$RegKey" "QuietUninstallString" '"$INSTDIR\uninstall.exe" /S'
  WriteRegDWORD HKCU "$RegKey" "EstimatedSize" $1
  WriteRegDWORD HKCU "$RegKey" "NoModify" 1
  WriteRegDWORD HKCU "$RegKey" "NoRepair" 1

  ${If} ${Silent}
  ${AndIf} $OpenMcpbSilent == "1"
    Call OpenMcpb
  ${EndIf}
SectionEnd

Function OpenMcpb
  ; Claude Desktop 이 .mcpb 를 열 수 있게 등록돼 있을 때만 연다(없으면 안내)
  ReadRegStr $0 HKCU "Software\Classes\.mcpb" ""
  ${If} $0 == ""
    ReadRegStr $0 HKCR ".mcpb" ""
  ${EndIf}
  ${If} $0 == ""
    ${IfNot} ${Silent}
      MessageBox MB_OK|MB_ICONINFORMATION "이 컴퓨터에서 Claude Desktop 을 찾지 못했습니다.$\r$\n$\r$\nClaude Desktop 을 설치한 뒤 '$INSTDIR\shortem.mcpb' 파일을 두 번 누르거나, Claude Desktop ▸ 설정 ▸ 확장 프로그램 ▸ 고급 ▸ 확장 프로그램 설치에서 이 파일을 고르세요.$\r$\n$\r$\nClaude Code 만 쓴다면 바탕화면 '숏템작업' 폴더의 시작.md 를 쓰면 됩니다."
    ${EndIf}
  ${Else}
    ExecShell "open" "$INSTDIR\shortem.mcpb"
  ${EndIf}
FunctionEnd

Function OpenWorkFolder
  ${If} $Sandbox == "1"
    ExecShell "open" "$INSTDIR\_sandbox_desktop\숏템작업"
  ${Else}
    ExecShell "open" "$DESKTOP\숏템작업"
  ${EndIf}
FunctionEnd

Function un.onInit
  StrCpy $Sandbox "0"
  ${If} ${FileExists} "$INSTDIR\.sandbox"
    StrCpy $Sandbox "1"
  ${EndIf}
FunctionEnd

Section "Uninstall"
  !insertmacro SetMode
  ; 숏템 설치 폴더가 맞을 때만 지운다(엉뚱한 폴더를 통째로 지우지 않게)
  ${If} ${FileExists} "$INSTDIR\tools\tools.manifest.json"
    RMDir /r "$INSTDIR\tools"
    RMDir /r "$INSTDIR\server"
    RMDir /r "$INSTDIR\claude-plugin"
    RMDir /r "$INSTDIR\node_modules"
    RMDir /r "$INSTDIR\_sandbox_desktop"
    Delete "$INSTDIR\*.*"
    RMDir "$INSTDIR"
  ${Else}
    DetailPrint "숏템 설치 폴더가 아니어서 파일은 지우지 않았습니다: $INSTDIR"
  ${EndIf}
  DeleteRegValue HKCU "Environment" "SHORTEM_INSTALL$EnvSuffix"
  DeleteRegValue HKCU "Environment" "SHORTEM_NODE$EnvSuffix"
  SendMessage ${HWND_BROADCAST} ${WM_SETTINGCHANGE} 0 "STR:Environment" /TIMEOUT=3000
  DeleteRegKey HKCU "$RegKey"
  ; 바탕화면 '숏템작업'(내 영상)과 ~/.shortem(키·캐시)은 고객 자료라 남긴다
SectionEnd
