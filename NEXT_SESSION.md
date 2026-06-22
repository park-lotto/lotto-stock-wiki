# NEXT_SESSION — 2026-06-22 (회사PC)

## ⚡ 한 줄
**위키 종합엔진**(원자→종목 페이지 자동 녹이기)을 설계·구현했으나 **수율 14%·claude -p 페이지파괴**로 미완. 단순화 재설계 필요.

---

## 세션 요약
오늘 인제스트한 5소스(뉴스·텔레·리포트·유튜브·블로그) 원자를 종목 페이지 골드 포맷에 자동으로 녹이는 "종합엔진"을 brainstorming→spec→plan→구현(서브에이전트 TDD)까지 진행. 반도체 프로토타입으로 실증.

## ✅ 완료
- **엔진 코드** `pipeline/atoms/synth_*.py` (17 테스트 통과):
  - `synth_qc.py` 중복제거+asset_level 라우팅 / `verify_gate.py` 검증등급 / `synth_engine.py` 종합+파괴가드 / `synth_rollup.py` 섹터인덱스 / `synth_run.py` 오케스트레이터 / `db.py` source_pub·certainty 컬럼
- **풍부 라우팅 수정**: 저신뢰(텔레·뉴스)=숨김 → **반영하되 ⚠️미검증 태그** (staging은 고위험만). 88%버려짐 → 95%반영
- **파괴방지 가드** `validate_synthesis()`: 출력이 원본보다 짧거나 변경요약문이면 쓰기 거부
- **반도체 5종목 풍부 갱신** (출처·등급 정상): SK하이닉스·삼성전자·삼성전기·한솔케미칼·LX세미콘
- 설계문서 `docs/superpowers/specs/2026-06-22-위키-종합엔진-design.md` / 플랜 `docs/superpowers/plans/2026-06-22-위키-종합엔진.md`

## 🔴 미완료 — 3구멍 + 재설계 (수율 14%의 원인)
당장 같은 5종목·14% 수율인 이유 = 3구멍:
1. **날짜 윈도우 함정**: `synth_run --days 14`가 *내용 날짜*로 잘라 오늘 인제스트한 6월초 백로그 95개(67%) 제외. → `created_at`(인제스트일) 기준으로 바꾸거나 윈도우 확대.
2. **섹터 페이지 실패**: `sector_반도체.md` 1007줄(정적 딥리서치 포함) 통째 재작성하다 claude -p 죽음 → 섹터레벨 20개 증발. → **섹션타겟 갱신**(시장국면 섹션만).
3. **기타 오분류**: "반도체·HBM·메모리" 내용인데 sector='기타'로 분류된 22개 누락. → 분류 보강.

추가:
4. **종합 재설계 (핵심)**: `claude -p`는 에이전트라 stdout에 잡담/요약 섞여 페이지 파괴(삼성전자 사례, 복구함). → **서브에이전트가 Write로 파일 직접 쓰기**로 전환(무료·안전, 삼성전기로 증명됨).
5. **7AM 자동화 연결** (atom_pipeline에 STEP 추가) — 위 안정화 후.

## 💡 핵심 교훈 (다음 세션 시작 전 명심)
> **"제대로 만들었나"만 검증하지 말고 "쓸모있나(수율)"를 먼저 검증하라.**
> 복잡한 엔진 짓기 전에 가장 단순한 버전("오늘 바뀐 종목마다 서브에이전트 1개가 그 페이지 갱신")으로 값어치부터 확인. 14일 윈도우·복잡 라우팅은 과설계였음.

## 관련 파일
- 코드: `pipeline/atoms/synth_qc.py · verify_gate.py · synth_engine.py · synth_rollup.py · synth_run.py`
- 테스트: `pipeline/atoms/test_synth_*.py · test_verify_gate.py`
- 설계/플랜: `docs/superpowers/specs|plans/2026-06-22-위키-종합엔진*.md`
- 결과물: `wiki/L5_섹터/반도체/stock/stock_{SK하이닉스·삼성전자·삼성전기·한솔케미칼·LX세미콘}.md`, `index_auto.md`
- 진행원장: `.superpowers/sdd/progress.md` (gitignore)
- 브랜치: `feat/synth-engine` → main 머지
