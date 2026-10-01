# 020 · 컷 규칙 상수 한 곳 + MAX_SLOWMO 서버 주입 (#30·#4)

- 쉬운 설명: 컷 길이 상수(최대 2.2초 등)를 한 곳에서 정하게
- 상태: 분배
- 등록: 2026-09-28 23:42
- 제보: 함수전수표
- 판단 주인: shopping_shorts/config.py(상수) → scene_play.js DATA 주입
- 분배: 주장번호시험
- 됐다의 기준: MAX_SHOT/MIN_CLIP/CUT_MIN/MAX_SLOWMO 정의 1곳, ownership 예외(edit_plan·config·scene_play) 삭제
- 승인 필요: 아니오
- 승인: 
- 병합: 
- 서버 반영: 
- 라이브 실측: 
- 재발: 

## 요청

(원문 없음)

## 이력

- 2026-09-28 23:42 등록
- 2026-10-01 00:40 쉬운 설명: 컷 길이 상수(최대 2.2초 등)를 한 곳에서 정하게
- 2026-10-01 16:08 분배 → 주장번호시험
- 2026-10-01 19:10 영향 없음: shopping_shorts/screen_clips_runner.js — planClips 안의 늦추기 상한 숫자만 서버 값(maxSlowmo)으로 바뀌었고 컷 계획 규칙·출력 모양은 그대로
- 2026-10-01 19:11 영향 없음: shopping_shorts/static/scene_lab.html — planClips 호출 인자·반환 모양 불변, DATA.max_slowmo 는 서버가 주입(scene_lab 코드 변경 없음)
