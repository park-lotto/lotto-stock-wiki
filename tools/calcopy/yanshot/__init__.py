# -*- coding: utf-8 -*-
"""얜샷템 한 명령 제작 파이프라인 (관제 097, 2026-10-17).

벤치 쇼츠 URL 하나 → 바탕화면 완성본. 단계 = 함수 하나, 주인 = 아래 모듈 하나.
  ① bench.bench(url, W)            받기·자막·설명란·프레임 시트·출처 표기·벤치 수치
  ② trace.trace(B, W)              출처 원본 확정 + 원음 구간(지문 대조 → 문장 끝까지 → 무음 경계)
  ③ script.script(B, T, W)         나레 2줄(만템 결) — 무료 제미나이 1회 + script_engine 검사 재사용
  ④ plan.plan(B, T, S, W)          컷 계획(원음 = 본인 화면, 장면 중복·되감김·점프 줌·남의 신체 금지)
  ⑤ render.make(B, T, S, P, W)     미나 TTS 1회 → 8.4자/초 → 렌더(정본 make_render 길)
  ⑥ check.check(B, T, S, P, R, W)  1초 시트·이음매·원음 받아쓰기·규칙표 → B표.md → 바탕화면
CLI: PYTHONUTF8=1 py tools/calcopy/yanshot/make.py <벤치 URL> --slug <소재> [--until plan]
엔진 코드(narr_video·hottem_audio·check_seams·bench_one·script_engine·mina_tts·gemini_free)는 부르기만 한다.
"""
