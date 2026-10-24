# readline_tools — 줄판독 픽셀 실측 도구 (관제 263 지시서 13 · 표준 §11 ⑫)

06 워커(잇템로그·홈디자인노트·이븐쇼핑, 10-24~25)가 세션 임시 폴더에 짜서 쓰던 도구를 저장소로 옮겼다. **알고리즘은 바꾸지 않았다**(잇템로그 SbWTqCnleC8 재실행 값 = 옛 산출물, 아래 재현 표).
줄판독 도구는 **이 폴더만** 쓴다. 세션 임시 폴더에 새 도구를 짜지 않는다 — 다음 세션·다른 PC·회원 PC 가 재현 못 한다.

| 도구 | 무엇을 재나 | 입력 → 출력 |
|---|---|---|
| `capseg.py` | 자막 띠 30fps 매 프레임 '검정 외곽 옆 밝은 채움' 잉크 마스크가 바뀌는 곳 = 자막 덩어리 경계 · 채움 hex · y 범위 | mp4 y0 y1 → `[{t0,t1,n,ink,hex,yr}]` |
| `cutdet.py` | 창 안 프레임차·히스토그램차 = 컷 · 종류(cut/black/flash/zoomblur) · 샷별 움직임 chg | mp4 y0 y1 → `{n,cuts,shots}` |
| `px.py` | 한 시각 채움색: `clusters`(색 글자+검정 외곽, k-means) · `box`(흰 글자+색 외곽, 잉크 상자·고리·배경 hex) | mp4 t y0 y1 → 표준출력 줄 / dict |
| `segsheet.py` | capseg 덩어리마다 [장면 | 자막 띠 확대 | 시각·hex] 시트(사람 눈 판독용, 측정 아님) | mp4 seg.json 접두어 → jpg 10줄씩 |
| `measure.py` | 흰 저채도 글자(외곽 색 무관) 마스크 변화 cap_ch · 광류 줌 발산 div·이동 tx/ty(cutdet 에 없음) · 띠 가린 장면차 · 밝기 / `seg` 서브명령 = 컷·자막 덩어리·덩어리별 움직임 요약 | mp4 b0 b1 → `{fps,band,rows}` |
| `rangesheet.py` | 고른 구간을 1프레임 간격까지 격자 시트(전환·등장 확대 판독, 측정 아님) | mp4 t0 t1 step → jpg |
| `tone.py` | 말 위 지속 순음(띵): 2.5~6kHz 칸 돌출 ≥14dB 0.12초+ (sfx_events tonal 이 말과 겹쳐 놓친 것) | mp4… → `{id:[{t,dur,hz,prom_db}]}` |
| `red.py` | 빨간 손그림 표시(원·화살표) 프레임별 칸 수·상자 + 흰·연하늘 카드 비율 | mp4 t0 t1 → 표준출력 줄 |
| `build_lr.py` | 눈으로 적은 spec + 위 실측 + sfx_raw 신호 → 줄판독 json(`kal_analyze check --strict` 꼴) | spec.py → 줄판독 json |

## 명령 (트랙 폴더에서)
```
PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/capseg.py   <mp4> <띠y0> <띠y1> seg_<id>.json
PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/cutdet.py   <mp4> <창y0> <창y1> cut_<id>.json
PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/segsheet.py <mp4> seg_<id>.json ss_<id> [띠y0 띠y1]
PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/px.py       <mp4> <t> <띠y0> <띠y1> [K]          # 색 글자
PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/px.py box   <mp4> <띠y0> <띠y1> <t1> [t2 ...]    # 흰 글자
PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/build_lr.py <spec.py> <out.json> --work <seg·cut 폴더> --mp4 <원본> \
      [--sfx-raw <sfx_raw.json>] [--profile profiles/ititemlog.json]
```
한 번에: `kal_analyze frames <mp4> --out <dir> --y0 <띠> --y1 <띠> --cap-band y0,y1 --window y0,y1` → strips/ + `seg_`·`cut_`·`segsheet_` 가 같은 폴더에,
이어서 `kal_analyze skeleton <dir> --spec <spec.py> --mp4 <원본> [--sfx-raw] [--profile] --out 줄판독/<id>.json`.
`kal.py` frames 단계는 `build_lr.bands_for(slug, 뜯기 layout)` 가 띠·창을 정한다(주인 한 곳): `profiles/<slug>.json` 의 capseg_band·cutdet_window > 뜯기 caption_band±100 · layout.window. 고른 근거는 판독목록 `readline.bands_why`.
**띠 민감(10-25 실측)**: capseg 는 띠가 바뀌면 경계가 크게 달라진다 — 잇템로그 SbWT 를 뜯기 caption_band(1257~1342)±60/100/120 으로 돌리면 손 띠(1150~1460) 결과 39경계 중 20~24개가 어긋났다. 손으로 정한 띠는 반드시 프로필에 적는다(그래야 재현된다).

## 채널 값
- 홈디자인노트: measure 띠는 편마다 다르다(DCXQ 570~665 등) — 아직 프로필 없음. 이븐쇼핑: tone 문턱·red 창(y 590, 높이 1220) → `profiles/evenshopping.json`.
- 띠·창은 채널마다 다르다. 잇템로그: capseg 띠 1150~1460 · cutdet 창 486~1920 · 측정 띠(build_lr) 1180~1470 → `profiles/ititemlog.json`.
- `examples/ititemlog_*.py` = 잇템로그 4편 spec(06 워커가 눈으로 적은 것) — spec 꼴 견본. 새 채널은 프로필 json 을 복사해 글꼴·외곽·층 이름을 고친다.

## 재현 대조 (10-25, SbWTqCnleC8)
| 대상 | 옛(세션 임시 폴더 도구 결과) | 새(이 폴더) |
|---|---|---|
| capseg 1150~1460 | work/lr6/seg_SbWTqCnleC8.json 39덩어리 | 39덩어리, json 완전 같음 |
| cutdet 486~1920 | work/lr6/cut_SbWTqCnleC8.json 27컷 | 27컷, json 완전 같음 |
| segsheet | ss_SbW_00.jpg | md5 같음(d0dd3057…) |
| px clusters t=5.0 | 3묶음 #FFF57B/#F7E710/#CB9F87 | 출력 줄 같음 |
| px box (홈디자인노트 DCXQjaWcZ-g t=2.0/5.5/9.0) | 옛 출력 | diff 0 |
| build_lr | channel/ititemlog/줄판독/SbWTqCnleC8.json 33줄 | 줄 33개 전부 같음, 다른 칸 = `_tools`(도구 경로 글)뿐 |
| measure·seg (홈디자인노트 DCXQ 570~665) | 옛 m_DCXQjaWcZ-g.json 647행 · seg 출력 20줄 | json 같음 · 출력 diff 0(기본·0.3/300 둘 다) |
| rangesheet (DCXQ 2~4초 0.033 · 0~30초 1초 자르기) | 옛 sheet.py jpg | md5 같음 |
| tone (이븐쇼핑 6편) | work/tone_detect.json 20발 | json 같음 |
| red (이븐쇼핑 tca 28.0~29.6 · Y2Y 23~24) | 옛 red.py 48·30줄 | diff 0 |
| 나머지 3편(zOSp·AZ2q·J7Gx) | lr6 seg 45/65/175 · cut 32/25/30 · 줄판독 38/30/35줄 | capseg·cutdet json 완전 같음 · 줄판독 다른 칸 `_tools` 뿐 |

시험: `shopping_shorts/tests/test_readline_tools.py`(합성 영상 + 이 PC 에 원본이 있으면 위 재현).

버린 것: 홈디자인노트 `strip.py`(구간 0.1초 자막 띠 격자) — kal_analyze frames 의 strips(바뀌는 지점 ±0.3초 0.1초 띠)와 channel/starpickroom/_tools/strip.py(구간·간격·띠·라벨)가 같은 일을 한다.
