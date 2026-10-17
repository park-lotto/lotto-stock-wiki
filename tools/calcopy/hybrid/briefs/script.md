# 브리프 — 대본·재료 초안 (소넷 워커 초안 → 오푸스 확정)

**목표**: `channel/yanshottem/하이브리드_<연예인>/{잇썸홈판,재미썸홈판}/대본.json·재료.json·근거.md` — 새 렌더러 입력 꼴(v2).
**정본(꼴을 그대로 베낀다)**: `C:/숏템_칼카피/yanshottem/_hybrid_pipeline_test/장윤정/doc/{잇썸홈판,재미썸홈판}/` (legacy_import 가 만든 v2 — 키 이름·구조가 렌더러 docstring 과 같다)
**규칙 문서**: `tools/calcopy/검수_매뉴얼.md` A 전부 · `tools/calcopy/hybrid/render_itssum.py` / `render_jaemi.py` 첫 docstring(필드 설명).

## 잇썸홈판 (박창수 TTS · 원음 → 잇썸홈 틀)
- lines: H(TTS 한마디, 전언체 '~다는') → O(원음 조각, 본인 말만 · `spans` 또는 `pieces` · `caps_rel`/`caps`) → B1~B5(1인칭 체험 → 손해 피하기 → 남들도/행동). TTS 문장 ≤35자, 조사·어미 다 있게(A13). 이름은 그대로 쓰고 `name_check` 가 tts 칸만 바꾼다.
- 재료 A: **H 컷도 연예인 얼굴**(사장님 10-18 "썸네일은 무조건 연예인" — 0초·H 구간 제품 컷 금지, 얼굴 1개·크게·가운데). O 컷은 원음 입 모양 그대로(at = 원음 이어 붙인 초). B 컷은 제품만(남의 얼굴·손 근접 금지, 원본 자막 띠 크롭 밖, `max` = 원본 샷 경계까지 초).
## 재미썸홈판 (필재 TTS · 원음 → F1 한마디 → 재미썸홈 t11 틀)
- orig(조각)·orig_caps(원본 초, 글) · lines(slot f1·bait·limit·more·twist·land) · pieces(자막 조각 ≤13자, 대사 글자 순서 그대로) · A(원음 밑 화면, at) · F1(from_piece) · B(pieces 번호 묶음, crop [x,y,h]).
- `tts_tempo`·`punct_at` 은 비워 둔다(자동). 렌더가 "문장부호 근처 무음 없음"으로 멈추면 그때만 손으로 적는다.
## 공통
- 줄마다 근거.md 한 줄(원본 초·댓글·기사). 없는 사실 금지. 금액·최상급 금지.
- 컷 시각은 `plan` 단계의 계획 시트(`plan/계획_시트.jpg`)로 눈 확인 → 컷마다 see(무엇이 보이나)·face(누구 얼굴)·text(남의 글자) 칸을 채운다.
- 같은 소스 ±3초 재사용 금지(B13) · A-B-A 끼움 금지(B16) · 끝 컷 ≥1.5초 · B 컷 ≥1.2초.
## 끝낼 때
`py tools/calcopy/hybrid/run.py <연예인> plan` 이 멈춤 없이 돌아야 한다(컷이 샷보다 길면 멈춘다). 멈춘 이유를 고친 뒤 넘긴다.
