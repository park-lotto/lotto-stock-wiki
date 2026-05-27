@echo off
chcp 65001 > nul
cd /d "C:\Users\TheRose\Desktop\로또의 주식"

echo.
echo ========================================
echo  매일 데이터 추출 파이프라인
echo ========================================
echo.

echo [1/6] 유동성 체크.xlsm  →  수급빈집(통합순위) + 리포트신고가 + 가속화모멘텀
powershell -ExecutionPolicy Bypass -File "raw\market\extract_유동성.ps1"

echo.
echo [2/6] 유동성 컨센등등.xlsm  →  컨센신고가 + SIO(시장온도) + 50일신고가
python extract_유동성컨센.py

echo.
echo [3/6] 오실레이터_업종.xlsm  →  주도업종 Top12 + 급증업종 + 관심테마 수급
python extract_업종오실레이터.py

echo.
echo [4/7] 오실레이터_종목별.xlsm  →  수급빈집 전종목 스캔 (A/B등급 + 재진입 신호)
python extract_빈집.py

echo.
echo [5/7] 추정이익변경 + 컨센서프쇼크 + 일정수주잔고 + 투자아이디어 + 액티브ETF + 페어트레이딩  →  Gemini 분석
python raw\extract_daily.py

echo.
echo [6/7] raw\report\ PDF파일들  →  Gemini 종목/산업/시황 리포트 추출
python raw\report\extract_report.py

echo.
echo [7/7] 매일요약\변화.md  →  wiki\stock 파일 자동 행 삽입
python wiki_patch.py

echo.
echo ========================================
echo  완료! Claude에게 /ingest today 실행 [7단계]
echo ========================================
pause
