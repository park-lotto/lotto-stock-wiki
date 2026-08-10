"""원자 DB 파이프라인 테스트의 선택적 의존성 가드 (2026-08-10).

`tests/atoms/conftest.py`와 같은 이유 — 여기 테스트도 import 시점에 chromadb를
요구한다(test_post_ingest_helpers / test_telegram_ingest_helpers). 없으면 수집 에러가
나고 저장소 전체 pytest가 "Interrupted: errors during collection"으로 멈춘다.

없으면 skip / 있으면 정상 실행. 지우지 않는 이유도 같다 — 위키 파이프라인 환경에선
이 테스트들이 실제로 돌아야 한다.
"""
import pytest

pytest.importorskip("chromadb", reason="chromadb 미설치 — 원자DB 인제스트 테스트 건너뜀")
