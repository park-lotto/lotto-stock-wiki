# agy 판독 정확도 실측 (2026-11-04, 관제 319 Task 1)

도구: `PYTHONUTF8=1 py -m tools.calcopy.engine.agy_check <mp4…> --out <영문 폴더>` (360p 변환 후 agy 에 영상 통째로, `--mode plan`).
agy = C:/Users/CH/AppData/Local/agy/bin/agy · 프로그램 숫자 = `kal_analyze.media_of`(duration · n_cuts).

| 채널/편 | 길이 프로그램 | 길이 agy | 컷 프로그램 | 컷 agy | 첫 자막(agy) | 눈 대조(t=1초 프레임) | 걸린 초 |
|---|---|---|---|---|---|---|---|
| annapick 1편_한고은채소통 | 22.2 | 22 | 9 | 9 | 정말 난 너무 놀랬어 | 일치 | 48.4 |
| foreignshowshow 11편_CopperCow | 45.53 | 46 | 26 | 27 | 이런 건 처음 봐요 (+상단 고정 자막 설명) | 일치 | 39.8 |
| hottemreport 현장썰_07_주걱 | 27.8 | 28 | 13 | 12 | 싸구려 복제품 소리를 들은 | 일치 | 19.6 |

- 길이 차 ±1초 이내(3/3). 컷 수 차 0 · +1 · -1 (3편뿐 — 크다고 말할 근거 없음, 결정은 Jev).
- 역할 경계(합성 영상 4초: 빨강 0.2초 t=0.5 · 초록 0.4초 t=1.5 · 파랑 1.0초 t=2.5): agy 는 파랑 1.0초 하나만 보고(시작 3초로 답) 0.2·0.4초는 못 봤다. = 1초 미만은 agy 에 안 묻는다(설계서 §6-1과 같은 경계).
  재측정: `py -m tools.calcopy.engine.agy_check --synth --out <영문 폴더>`
- 참고: 벤치 mp4 는 `C:/숏템_칼카피/<slug>/.../render/final.mp4` 에 있다(`mp4/` 폴더 아님).
