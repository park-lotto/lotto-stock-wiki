"""칼카피 틀 설명서(frame.json) — 설계 docs/superpowers/specs/2026-10-15-칼카피엔진-design.md §5·§6-3.

schema.validate(frame)      : 설명서 한 장을 검사·정규화한다(판단의 주인 — 무엇이 유효한 틀인가)
to_snapshot.to_snapshot(..) : 설명서 → 라이브 장면꾸미기 스냅샷(customFrame 행을 실어 보낸다)
그리기는 out/precision20-ui.js 의 renderSpec 한 곳(편집 화면·렌더 레이어·썸네일이 같은 함수를 부른다).
"""
