@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ================================================
echo  트랙 청소 - 라이브에 이미 반영된 트랙만 삭제
echo  기준 커밋(서버 실측): b31a9c4fa
echo  대상: 33개 트랙 + 4개 finish 찌꺼기 = 약 32GB
echo  ※ 장면분량 등 미반영 34개는 건드리지 않음
echo ================================================
echo.
pause

set OK=0
set FAIL=0

for %%T in (
  PC등록해제 effect-mining-workers 경계NBSP 경계침묵 경보상주목록
  고객검색가입폼 공용목소리404 대본씹힘 랭킹12시간기본 렌즈검색어제품명
  렌즈검색어제품명2 목소리이음매 미리보기비율 소구점확장 소스분석진행표시
  썸네일확대돋보기 유튜브검색어 인스타수집확대 장면꾸미기서버렌더 장면꾸미기재편
  챌린지관리 청소후미리보기갱신 컷경계스냅 컷편집경합 쿠팡검색근거
  크롤링관측판 파워검색썸네일 핀터레스트오픈 필름조각소실 회원키실패율
  효과음실측 효과음타점 휴지통띠제거
) do (
  echo [닫는 중] %%T
  py tools\track.py close %%T
  if errorlevel 1 (
    set /a FAIL+=1
    echo    ^^! 실패: %%T
  ) else (
    set /a OK+=1
  )
)

echo.
echo === finish 임시 작업장 정리 ^(브랜치 없는 찌꺼기^) ===
for %%S in (_merge-가입자동승인 _merge-랭킹렌더상한 _merge-필름자막구간 _stage_자막수동) do (
  if exist ".tracks\%%S" (
    echo [지우는 중] %%S
    git worktree remove --force ".tracks\%%S" 2>nul || rmdir /s /q ".tracks\%%S"
  )
)
git worktree prune

echo.
echo ================================================
echo  완료:  성공 !OK! / 실패 !FAIL!
echo ================================================
py tools\track.py list
echo.
echo 남은 용량:
powershell -NoProfile -Command "'{0:N1} GB 여유' -f ((Get-PSDrive C).Free/1GB)"
echo.
pause
