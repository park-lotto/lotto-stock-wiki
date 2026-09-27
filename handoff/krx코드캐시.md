# krx코드캐시 — 핸드오프

## 2026-09-27 (PC: CH) — 서버 krx_codes.json 44B 사고 원복 + 방어 코드 배포 완료
- 사고: `pipeline/atoms/krx_codes.json`이 12:35에 `{"codes": {}}`(44B)로 덮임. 원인 `codemap.refresh_krx_cache`가 KRX(kind.krx.co.kr) **403** 실패 뒤 빈 dict 저장. `updated` 2026-09-09라 7일 규칙으로 로드마다 재시도.
- 조치: git 원본 원복(82,270B·2,595종목, 44B 사본 `/home/ubuntu/krx_codes.json.empty_2026-09-27`) → 방어(결과 비거나 절반 미만이면 파일 안 덮고 종전 표 반환) `5af53fa9d`, 테스트 `tests/test_codemap_keep_cache_on_empty.py` 2건(사보타주 빨강). finish → main `3505ee533`, 서버 14:09 반영, `stockbrain` 14:09:55 수동 재시작(사장님 "사람 없을 때"), 재시작 후 파일 2,595 유지.
- ⚠️ `pipeline/atoms/test_*.py`는 chromadb 없으면 conftest가 통째로 건너뛴다 → 테스트는 `tests/`에 둘 것. ⚠️ auto_deploy는 `pipeline/*.py` 변경을 "코드변경없음"으로 분류해 stockbrain을 재시작하지 않는다.
- ⏭ KRX 403 자체(갱신 불가)는 미해결 — 표는 09-09 기준으로 고정. 새 상장/변경 종목은 반영 안 됨. 다른 소스(wisereport 폴백 `_build_wisereport`)로 갱신할지 결정 필요.
