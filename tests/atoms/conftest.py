"""원자 DB(pipeline.atoms) 테스트의 선택적 의존성 가드 (2026-08-10).

이 폴더의 테스트는 **무거운 선택적 라이브러리**를 import 시점에 요구한다:
    pandas    → test_excel_converter
    chromadb  → test_ingest / test_vector_db / test_pdf_ingest

이 둘은 위키·원자DB 파이프라인 전용이라 **쇼핑쇼츠 개발 환경엔 없다**.
없으면 pytest가 수집 단계에서 ImportError를 내고, `--co tests`가
"Interrupted: 4 errors during collection"으로 **424개를 수집하고도 멈춘다**(실측 2026-08-10).
즉 라이브러리 하나 없다고 저장소 전체 테스트가 안 돈다.

`importorskip`은 **없으면 조용히 skip, 있으면 정상 실행**이라 둘 다 만족한다.
- 이 PC(쇼핑쇼츠 작업): skip → 나머지 테스트가 전부 돈다
- 위키·파이프라인 환경(pandas·chromadb 설치됨): 그대로 실행 → 검사 안 잃는다

⚠️ 테스트를 지우거나 skip 마크를 박지 않은 이유: 지우면 그 기능의 안전망이 영구히
사라지고, 무조건 skip이면 설치된 환경에서도 안 돈다. 의존성 유무로 자동 판정해야 한다.
"""
import pytest

# collect_ignore와 달리 이건 '모듈이 없을 때만' 건너뛴다.
pytest.importorskip("pandas", reason="pandas 미설치 — 원자DB 엑셀 변환 테스트 건너뜀")
pytest.importorskip("chromadb", reason="chromadb 미설치 — 원자DB 벡터 테스트 건너뜀")
