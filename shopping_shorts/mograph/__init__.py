# -*- coding: utf-8 -*-
"""모션그래픽 엔진 패키지(관제 244, 2026-10-20) — 별도 서비스로 떼어 갈 경계.
설계: docs/superpowers/specs/2026-10-20-모션자산작업대-design.md
  ledger.py   부품·레퍼런스·프리셋 장부(주인)      sources.py  원본 소스(CHA 등) 폴더 스캔
  render.py   HyperFrames 렌더 → mp4·프레임 시트·시간 기록
app.py 는 길목(권한·파일 서빙·JSON)만 둔다."""
