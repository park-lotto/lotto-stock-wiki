# readline_tools — 줄판독 픽셀 실측 도구 (관제 263 지시서 13 · 표준 §11 ⑫)

06 워커들(잇템로그·홈디자인노트·이븐쇼핑·썰풀다·유머쇼쇼·샤크탱크·핫템리포트, 10-24~25)이 세션 임시 폴더나 저장소 밖에 짜서 쓰던 도구를 옮겼다.
옮길 때 **알고리즘은 바꾸지 않았다** — 옛 산출물과 같은 값이 나오는지 실물로 대조했다(아래 표).
줄판독 도구는 **이 폴더만** 쓴다. 세션 임시 폴더·slug 폴더에 측정 도구를 새로 짜지 않는다. 다음 세션·다른 PC·회원 PC 가 다시 돌릴 수 없기 때문이다. 없는 기능은 보고하고 이 폴더에 넣는다.

## 도구
| 도구 | 무엇을 재나 | 입력 → 출력 |
|---|---|---|
| `capseg.py` | 자막 띠를 30fps 로 보고, 글자 잉크 마스크가 바뀌는 곳을 자막 덩어리 경계로 자른다. 모드: `color`(검정 외곽 옆 밝은 채움, 기본) · `bright`/`dark`/`both`(흰 글+검정 외곽 / 검정 글 / 둘 다 — 썰풀다 seg2) · `box`(흰 상자 위 검정 글, `--grid` 줄 칸 거르기 — 유머쇼쇼 seg2·seg3) · `shadow`(외곽선 없이 그림자·번짐만 있는 자막 — 샤크탱크 fsseg) | mp4 y0 y1 [--mode] → `[{t0,t1,n,ink,hex,yr}]` (box·shadow 는 꼴이 다르다) |
| `cutdet.py` | 창 안 프레임차·히스토그램차로 컷을 찾고 종류(cut/black/flash/zoomblur)·샷 chg 를 낸다. `--v2`: 자막 띠를 뺀 선명도로 블러를 다시 판정한다(같은 샷 바탕 대비 ≤0.45, 다시 선명해짐 ≥1.25). 검정(창의 60%↑가 검정 + 페이드인)·밝기 번쩍(컷에서 바로 +40 뒤 서서히 어두워짐)·영상 시작 블러·샷 motion(shotmotion)도 낸다. `color_flash` = 색 번쩍(프로필 `color_flash`) | mp4 y0 y1 [--v2 --cap-band] → `{n,cuts,shots}` |
| `shotmotion.py` | 같은 그림 컷을 버리고, 샷 처음↔끝 ORB 닮음변환으로 still/cam/zoom_in/zoom_out/pan 을 가른다(유머쇼쇼 motion.py). cutdet --v2 의 motion 주인 | mp4 cut.json y0 y1 → `{cuts,shots}` |
| `px.py` | 한 시각의 채움색. `clusters`(색 글자+검정 외곽, k-means) · `box`(흰 글자+색 외곽) | mp4 t y0 y1 → 표준출력 |
| `measure.py` | 흰 저채도 글자 마스크 변화·광류 줌/이동·장면차·밝기, `seg` = 요약(홈디자인노트) | mp4 b0 b1 → `{fps,band,rows}` |
| `segsheet.py` · `rangesheet.py` · `entersheet.py` | 사람 눈 판독용 시트: capseg 덩어리별 / 고른 구간 1프레임 간격 / 줄 시작마다 0.34초 등장 | → jpg |
| `tone.py` · `red.py` · `marktrack.py` | 말 위 순음 '띵' · 빨간 손그림 표시 프레임별 · 꾸밈 색(초록·분홍·빨강) 덩어리 트랙(샤크탱크 fxdet) | |
| `thumbmatch.py` | 유튜브 썸네일이 영상 몇 초 프레임인지(회색 90×160 상관, info.json 이면 썸네일을 무료로 받는다) | mp4 썸네일|info.json → `{best_t,best_corr,t0_corr,top}` |
| `asrwords.py` | 로컬 위스퍼 낱말 시각(효과음 후보를 걸러 낼 때) | out_dir mp4… → `<id>.json` |
| `autoband.py` | **자막 띠 자동 찾기**: 행마다 잉크가 '있고 바뀌는' 정도로 자막 핵을 찾고, 230px 목표 띠로 넓힌다. `--slug --src-dir --write` 면 `profiles/<slug>.json` 에 편별 `bands` 를 적는다 | mp4 [--mode] → `{band,core,mask}` |
| `build_lr.py` | 눈으로 적은 spec + 실측 + sfx_raw → 줄판독 json. `bands_for` = 띠·창·capseg 모드의 주인(kal.py 가 부른다). v2 motion 을 읽는다. 프로필 `fill: dominant` 면 강조색이 섞인 줄에서 바탕 글자색을 최빈 색으로 잡는다 | spec.py → 줄판독 json |
| `rules_only.py` | 줄판독만 다시 했을 때 규칙빈도만 다시 낸다(kal_state.json 을 안 건드림) | slug 주소 id들 |
| `eval_transition.py` · `eval_autoband.py` | 점검 도구: 전환 종류를 눈 정답과 대조 / 자동 띠를 손 띠와 대조 | |

## 명령 (트랙 폴더에서, 앞에 `PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/`)
```
capseg.py <mp4> <y0> <y1> seg_<id>.json [--mode color|bright|dark|both|box|shadow] [--grid y,y..]
cutdet.py <mp4> <창y0> <창y1> cut_<id>.json [--v2 --cap-band y0,y1]
build_lr.py <spec.py> <out.json> --work <seg·cut 폴더> --mp4 <원본> [--sfx-raw sfx_raw.json] [--profile profiles/<slug>.json]
autoband.py --slug <slug> --src-dir C:/숏템_칼카피/<slug>/src [--mode color] --write
eval_transition.py <slug> --src-dir <원본 폴더>
```
한 번에: `kal_analyze frames <mp4> --out <dir> --cap-band y0,y1 --window y0,y1` → strips/ + `seg_`·`cut_`·`segsheet_`. 이어서 `kal_analyze skeleton <dir> --spec <spec.py> --mp4 <원본> --out 줄판독/<id>.json`.
`kal.py` frames 단계는 `build_lr.bands_for(slug, 뜯기 layout, vid, mp4)` 가 띠·창·모드를 정한다. 우선순위는 프로필 `bands{<편>}` > 프로필 `capseg_band`(손 값) > autoband(편마다 자동) > 뜯기 caption_band±100 이다. 고른 근거는 판독목록 `readline.bands_why` 에 남는다.

**줄판독만 다시 할 때는 kal.py 를 다시 돌리지 말고 step_rules 를 직접 부른다** — `rules_only.py <slug> <주소> <id,…>`. 대부분 채널은 kal_state 의 rules 가 done 이라 `kal.py --from rules` 를 쓰면 copy·make 단계까지 넘어간다.

모든 영상 도구는 원본이 30fps 가 아니면 30 으로 맞춘다(`capseg.fps_filter`). 60fps 를 그대로 넣으면 시각이 2배가 되고, 중복 프레임을 컷으로 센다(꿀템노트 m0Ex: 72컷 → 18컷). crop 은 `exact=1` 이다. 이것이 없으면 홀수 높이 띠에서 프레임이 밀려 경계가 반쯤 어긋났다. 앞서 '띠 민감'이라고 적었던 현상의 진짜 원인이 이것이다.

## 채널 값 = `profiles/<slug>.json`
ititemlog · evenshopping · sseolpulda · mantem · starpickroom · foreignshowshow(capseg_mode shadow·color_flash) · itemhome · annapick · hotpeople(앞의 다섯은 06 이 `_kal/readline_profile.json` 에 적었던 값을 옮긴 것, 원래 파일은 그대로 둠). `examples/` 는 잇템로그 spec 4편(spec 꼴 견본)이다.

## 재현 대조 (옛 도구·옛 산출물 == 새 도구)
| 대상 | 결과 |
|---|---|
| capseg/cutdet 잇템로그 4편(lr6) | json 완전 같음. 줄판독 4편은 `_tools` 칸만 다름 |
| capseg bright/dark/both 썰풀다 6편 | 짝수 띠 5편은 옛 seg2 와 같음(iZ 는 홀수 띠라 exact 수리로 달라짐). 썰풀다 줄판독 6편 완전 같음(mk.py 덧붙임을 build_lr 에 합침) |
| capseg box(유머쇼쇼 6편)·box --grid(pY2z) | 옛 seg2·seg3 와 같음 |
| capseg shadow·color_flash·marktrack(샤크탱크 QMJ·2jJ) | 옛 fs_*_seg·fs_*_flash·fx_* 와 같음 |
| shotmotion(유머쇼쇼 4/5편) | 옛 mo_* 와 같음(pY2z 는 창을 몰라 못 맞춤) |
| measure·seg·rangesheet·px box(홈디자인노트 DCXQ) · tone 6편·red 2구간(이븐쇼핑) · segsheet md5 · px clusters | 같음 |
| thumbmatch(핫템리포트 6편) | 손 측정 시각과 ±1칸(0.17초) 안: OE 12.0·IRFN 15.67·a06 11.67(손 11.5)·Zq 18.83·Rpfk 13.17·RWS 15.33 |

## 전환 종류 점검 — 14채널 98편 눈 정답(특수 79곳·cut 1287줄)
도구: `eval_transition_loco.py dump …` → `loco` (채널 하나 빼고 문턱 고르기) · `loco --fixed` (cutdet.V2 그대로). 판정 주인은 `cutdet.classify_arrays`(특징)·`cutdet.decide`(문턱).
| 재는 법 | 빠진(또는 전) 채널 평균 일치 | 전체 일치 | 오탐(cut 줄) |
|---|---|---|---|
| LOCO(채널마다 나머지로 문턱 고름) | **0.726** | 63/79 = 0.797 | 47/1287 = 3.7% |
| 고정 문턱 cutdet.V2(LOCO 에서 가장 자주 뽑힌 값) | 0.731 | 63/79 = 0.797 | **37/1287 = 2.9%** |
| (앞판 규칙, 5채널에 맞춘 것) | 검증 7채널 0.68 | — | 26/660 |
**목표(평균 ≥90%)에는 못 미친다.** 오탐 목표(≤3%)는 고정 문턱에서 채운다. 꼴별로 정리하면 이렇다.
| 꼴 | 수 | 왜 안 되나 | 해 본 것 |
|---|---|---|---|
| uljimatrot zoomblur | 4 | 2곳은 컷 자체가 안 잡힌다. 선명도가 내려가지 않고(700~900 고른 수준) 밝기만 서서히 바뀐다. 나머지 2곳은 약한 블러(비율 0.52~0.56·회복 1.5) | 비율 0.6 까지 열면 2곳을 잡지만 오탐 +2.4%p(4.9%). 컷 없이 오는 블러 찾기는 선명도가 안 내려가 소용없음 |
| 샤크탱크 flash | 7 | 사건 없음 2·색 점프 13~43(문턱 45 밑)·밝기 점프가 음수인 번쩍 | 색 문턱 30 은 다른 채널 오탐을 늘린다 |
| zoomblur ↔ '블러 낀 cut' | cut 줄 오탐 31 중 다수 | 정답이 cut 인 줄에도 블러 특징(비율 ≤0.3·회복 ≥1.5)이 그대로 있다(이븐쇼핑 13·아이템홈 7·키치잇 7). 방사 블러(가장자리 ÷ 가운데 선명도)·칸별 흐림 고르기로도 정답 zoomblur 와 갈리지 않는다(분포가 겹침) | 3×3 칸 선명도 덤프로 확인 — 갈리지 않아 규칙에 넣지 않음. 채널마다 사람이 붙인 이름(블러 컷을 cut 으로 적느냐)이 다른 것으로 보인다 |
| 만템 flash → black | 1 | 검정 98% 프레임 뒤 밝아지는 꼴을 사람은 flash 로 적었다 | — |
| 썰풀다 zoomblur(6iW 10.17) | 1 | 선명도가 내려가지 않는다(비율 1.16) | — |
그러니 이 도구가 내는 전환 종류는 '신호'로만 쓴다. 채널마다 eval_transition 으로 그 채널 정답과 다시 맞춰 보고, 블러 컷을 그 채널이 cut 으로 적는지 먼저 확인한다.

## 자동 띠 점검(eval_autoband)
34편, 10-25. **합격 31/34** — 손 띠 채널(잇템로그·썰풀다·홈디자인노트, 06 워커가 그 띠로 실제 분할을 돌림)은 F1≥0.95, layout 띠 채널(방구석·얌얌노·이븐쇼핑)은 줄판독 줄 경계 재현이 손 띠의 95% 이상이면 합격.
- 잇템로그 4/4 · 썰풀다 6/6(fnZN 은 채널 무리 prior 로 해결) · 이븐쇼핑 6/6 · 얌얌노 6/6 · 방구석 5/6 · 홈디자인노트 4/6.
- 남은 3편:
  - 홈디자인노트 WTgQ: 자막이 편 안에서 여러 자리로 옮겨 다닌다. 핵을 워터마크로 잡았다.
  - 홈디자인노트 iiBU: 기준 경계가 8개뿐이고 F1 0.933이다.
  - 방구석 8iE: 줄판독 경계 재현이 0.722로, 손 띠의 0.833 보다 낮다.
- 띠가 맞으려면 세 가지가 필요했다.
  - 모드별 띠 모양: color 는 230px 로 넓히고, 검정 글·흰 획은 핵에 바짝 붙인다.
  - 채널 무리 prior: 과반 편의 핵 자리와 가까운 후보를 고른다.
  - 고정 글자 행 빼기: 제목·조회수 줄을 띠에 넣지 않는다.
- 이븐쇼핑은 모드 문제가 아니었다. 앞판의 손 띠(줄 y 최소~최대)가 창까지 넣어 기준 쪽이 틀렸다. 420~580 이면 color·dark 모두 줄 경계 1.0 이다.

## ⑭ 줄마다 자리가 바뀌는 자막·가는 손글씨(안나픽 iS0la) — 시험했지만 넣지 않음
창 전체(419~1501)에서 글자 줄 모양 덩어리를 찾아 자르는 방식(capseg free)을 시험했다. 결과는 줄판독 경계 재현 0.46~0.64(정밀 0.19~0.30)였다. 줄 띠별로 따로 비교해도 재현 1.0·정밀 0.15 였다. 고정 띠 color(1140~1270)는 재현 1.0·정밀 0.29 라 오히려 낫다. 장면 속 글자 같은 덩어리가 경계를 마구 만들기 때문이다.
그래서 도구에는 넣지 않았다. 이 편은 경계를 띠 capseg 로 잡고, 자리가 바뀌는 줄(830~875 노랑 손글씨 등)의 y 는 눈 판독으로 채운다.

## 버린 것
홈디자인노트 `strip.py` — kal_analyze strips·starpickroom strip.py 와 같은 일을 한다. 샤크탱크 `mkfs.py`(채널 전용 조립 318줄)·`chunks.py`·`stats.py` — 측정 도구가 아니라 그 채널의 조립·집계 스크립트라 옮기지 않았다.

시험: `shopping_shorts/tests/test_readline_tools.py`(합성 영상 시험 + 이 PC 에 원본이 있으면 실물 재현·정답 대조).
