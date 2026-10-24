# readline_tools — 줄판독 픽셀 실측 도구 (관제 263 지시서 13 · 표준 §11 ⑫)

06 워커(잇템로그·홈디자인노트, 10-24~25)가 세션 임시 폴더에 짜서 쓰던 도구를 저장소로 옮겼다. **알고리즘은 바꾸지 않았다**(잇템로그 SbWTqCnleC8 재실행 값 = 옛 산출물, 아래 재현 표).
줄판독 도구는 **이 폴더만** 쓴다. 세션 임시 폴더에 새 도구를 짜지 않는다 — 다음 세션·다른 PC·회원 PC 가 재현 못 한다.

| 도구 | 무엇을 재나 | 입력 → 출력 |
|---|---|---|
| `capseg.py` | 자막 띠 30fps 매 프레임 '검정 외곽 옆 밝은 채움' 잉크 마스크가 바뀌는 곳 = 자막 덩어리 경계 · 채움 hex · y 범위 | mp4 y0 y1 → `[{t0,t1,n,ink,hex,yr}]` |
| `cutdet.py` | 창 안 프레임차·히스토그램차 = 컷 · 종류(cut/black/flash/zoomblur) · 샷별 움직임 chg | mp4 y0 y1 → `{n,cuts,shots}` |
| `px.py` | 한 시각 채움색: `clusters`(색 글자+검정 외곽, k-means) · `box`(흰 글자+색 외곽, 잉크 상자·고리·배경 hex) | mp4 t y0 y1 → 표준출력 줄 / dict |
| `segsheet.py` | capseg 덩어리마다 [장면 | 자막 띠 확대 | 시각·hex] 시트(사람 눈 판독용, 측정 아님) | mp4 seg.json 접두어 → jpg 10줄씩 |
| `build_lr.py` | 눈으로 적은 spec + 위 실측 + sfx_raw 신호 → 줄판독 json(`kal_analyze check --strict` 꼴) | spec.py → 줄판독 json |

## 명령 (트랙 폴더에서)
```
PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/capseg.py   <mp4> <띠y0> <띠y1> seg_<id>.json
PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/cutdet.py   <mp4> <창y0> <창y1> cut_<id>.json
PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/segsheet.py <mp4> seg_<id>.json ss_<id> [띠y0 띠y1]
PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/px.py       <mp4> <t> <띠y0> <띠y1> [K]          # 색 글자
PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/px.py box   <mp4> <띠y0> <띠y1> <t1> [t2 ...]    # 흰 글자
PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/build_lr.py <spec.py> <out.json> --work <seg·cut 폴더> --mp4 <원본> \
      [--sfx-raw <sfx_raw.json>] [--profile examples/ititemlog_profile.json]
```
한 번에: `kal_analyze frames <mp4> --out <dir> --y0 <띠> --y1 <띠> --cap-band y0,y1 --window y0,y1` → strips/ + `seg_`·`cut_`·`segsheet_` 가 같은 폴더에,
이어서 `kal_analyze skeleton <dir> --spec <spec.py> --mp4 <원본> [--sfx-raw] [--profile] --out 줄판독/<id>.json`.
`kal.py` frames 단계는 영상 창만 넘기므로 cutdet 만 돌고 capseg 는 "건너뜀(자막 띠 모름)" 으로 남는다 — 자막 띠는 `--cap-band` 로 따로.

## 채널 값
- 띠·창은 채널마다 다르다. 잇템로그: capseg 띠 1150~1460 · cutdet 창 486~1920 · 측정 띠(build_lr) 1180~1470 → `examples/ititemlog_profile.json`.
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
| 나머지 3편(zOSp·AZ2q·J7Gx) | lr6 seg 45/65/175 · cut 32/25/30 · 줄판독 38/30/35줄 | capseg·cutdet json 완전 같음 · 줄판독 다른 칸 `_tools` 뿐 |

시험: `shopping_shorts/tests/test_readline_tools.py`(합성 영상 + 이 PC 에 원본이 있으면 위 재현).
