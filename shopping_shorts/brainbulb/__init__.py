"""brainbulb — 뇌전구(볼케이노) 규격 숏폼을 서버 없이 로컬에서 만드는 파이프라인.

설계 논쟁 기록: docs/superpowers/specs/2026-09-12-brainbulb-design.md (페이블·아스트라)
규격 근거: channel/volcano/뇌전구_역분석_8편_2026-09-12.md (8편 실측)

원칙 (볼케이노에서 가져온 것):
  - 디자인은 상수다 (spec.py). 채널 추가 = spec 교체.
  - 규칙은 판정으로만 존재한다 (lint.py). 판정은 데이터를 고치지 않는다 — 반려와 사유만.
  - 단계 배열 하나가 상태기계다 (pipeline.py). 화면·호출자는 next_step만 따른다.
  - 검증은 실제 산출물과 대조한다 (tests/fixtures/brainbulb/*).
"""
