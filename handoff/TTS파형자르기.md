# TTS 파형 · 무음 자르기

> 트랙 폴더: `.tracks/TTS파형자르기` · 브랜치 `track/TTS파형자르기`
> 커밋 `65fa2b70f` (origin에 푸시 완료 — 원격·로컬 같은 해시 확인) · **main 미병합 = 라이브 영향 없음**
> ⚠️ 아래 줄 번호는 `65fa2b70f` 기준이다. 코드가 바뀌었을 수 있으니 **열어서 확인하고** 쓸 것(0순위 규칙).

---

## 1. 무엇을 요청받았나

사장님(2026-09-22, 스크린샷 첨부):
> "tts부분에 [스크린샷] 음성구간을 넣어서 무음구간을 자동으로 없애주거나 수동으로 해주는걸
> 넣을건데 되나? **필름처럼 볼수있게**"

스크린샷 = 문장마다 가로로 긴 파형 띠, 양끝에 분홍 손잡이, 우측에 `−0.13s` 표시.

내가 A(끝만)/B(중간까지)로 갈라 제안 → 실측 보고 → 사장님 **"b까지"** → 구현.

---

## 2. ★가장 중요 — 무음 감지가 **한 번도 동작한 적이 없었다**

작업 도중 발견. 이것이 이번 세션의 가장 큰 수확이다.

### 증상
`audio_post.detect_silences` / `detect_edge_silence`가 **한글 경로에서 항상 `[]` / `0.0`** 반환.

### 원인
ffmpeg는 stderr를 UTF-8로 내는데 `subprocess.run(..., text=True)`만 주면 파이썬이
로캘(윈도우 = cp949)로 디코드하다 **리더 스레드에서 `UnicodeDecodeError`로 죽는다.**
그런데 이 파일의 호출부는 전부 `except Exception: return []` / `return 0.0` 꼴이라
**예외가 조용히 삼켜지고 "무음이 없다"로 둔갑**했다.

이 저장소는 경로에 `로또의 주식`이 들어가 **항상** 밟는다.

### 실측 증거 (job 409f894230c6, 비트 5개)
```
detect_edge_silence → 0.0   / detect_silences → []      (5개 전부)
ffmpeg를 직접 실행하면    → beat_0에 0.31초 무음이 분명히 있다
```
→ **기존 「✂ 끝 조용한 부분 자르기」 버튼은 눌러도 아무 일이 없었다.**

### 왜 놓쳤나 (재발 방지 핵심)
- 기존 테스트 `test_edge_silence.py`는 **가짜 stderr 문자열**만 파싱해서 검사했다.
  문자열 파서만 재면 인코딩 사고는 영영 안 잡힌다.
- **같은 함정을 `video_assemble.py:546`(`_FF_TEXT`)이 2026-07-16에 이미 고쳤는데
  `audio_post.py`는 그 수정을 못 받았다** — 한 곳을 고쳐도 같은 꼴이 다른 파일에 남는
  0순위-B 전형.

### 고친 것
- `audio_post.py:35` `_FF_TEXT` 상수 추가(`encoding="utf-8", errors="replace"`), 3곳 적용
  (`detect_silences` · `_audio_dur` · `detect_edge_silence`).
  ※ `video_assemble`을 import하면 순환이 된다(그쪽이 audio_post를 쓴다) → 상수를 이 파일에 둠.
- **전수 검사 도구** `tools/audit_subprocess_encoding.py` (0=깨끗, 1=결함).
- **회귀 테스트** `tests/test_silence_korean_path.py` — 가짜 문자열이 아니라
  **한글 폴더에 진짜 mp3를 만들어** 돌린다.

### ★이 검사들이 진짜 잡는지 확인한 방법 (0순위-A1c)
```
tools/audit_subprocess_encoding.py
  고치기 전 코드 → 결함 3건 잡음, rc=1      ← 실패가 떠야 진짜 검사다
  고친 뒤        → 0건, rc=0
tests/test_silence_korean_path.py
  인코딩 수정만 되돌림 → 2 failed ("한글 경로에서 무음을 못 찾았다", head=0.0)
  원복             → 3 passed
```
**둘 다 "고치기 전에 실패하는지"를 먼저 시험했다.** 안 하면 거짓 통과를 믿게 된다(2026-09-21 사고).

> 메모리: `reference_ffmpeg_stderr_cp949_삼킴`

---

## 3. 실측이 설계를 바꿨다 — A안은 이 환경에서 쓸모가 없다

job 409f894230c6 비트 5개 전수 측정(인코딩 고친 뒤):

| 비트 | 길이 | 앞뒤 끝 무음 | 문장 중간 무음 |
|---|---|---|---|
| 0 | 6.10초 | 0.00 | 2구간 0.51초 |
| 1 | 5.77초 | 0.00 | 2구간 0.41초 |
| 2 | 4.78초 | 0.00 | 1구간 0.27초 |
| 3 | 7.28초 | 0.00 | 3구간 0.55초 |
| 4 | 4.84초 | 0.00 | 4구간 0.85초 |
| **합** | **28.77초** | **0.00초** | **12구간 2.59초** |

**앞뒤가 0인 이유**: 음성 생성 단계의 `pace_mode`가 `silenceremove start_periods=1`로
이미 앞뒤를 걷어낸다(`audio_post._pace_filters`). 자를 것은 전부 문장 중간에 있다.

→ 그래서 **끝만 자르는 A안은 눌러도 "자를 조용한 부분이 없어요"만 뜬다.** B까지 해야 의미가 있다.

---

## 4. 무엇을 만들었나 (파일·줄 번호)

### 백엔드

**`shopping_shorts/audio_post.py`**
| 줄 | 이름 | 하는 일 |
|---|---|---|
| 35 | `_FF_TEXT` | ffmpeg 출력 인코딩 고정(위 2번) |
| 286 | `_WAVE_BARS = 120` | 파형 막대 수 |
| 289 | `extract_peaks()` | mp3 → 막대별 피크 `[0~1]`. s16le 8kHz raw PCM으로 디코드해 구간 최대 절대값 |
| 332~334 | `_GAP_THRESHOLD`(-30dB) `_GAP_MIN_DUR`(0.10) **`_GAP_KEEP`(0.06)** | 중간 쉼 판정값. ★사장님 청취 후 조절할 곳 |
| 337 | `find_gaps()` | 문장 **중간** 쉼만 `[{start,end,drop}]`. 끝에 닿는 건 제외(엣지 트림 몫) |
| 361 | `cut_gaps()` | atrim+concat으로 잘라낸 mp3 생성. 경계에 페이드(클릭음 방지). 실패 시 `None`(원본 유지) |

★**왜 파형을 서버에서 뽑나**: ①브라우저 `decodeAudioData`면 장면 20개 mp3를 전부 받아야 해 느리다
②무엇보다 **자동 자르기 판정(ffmpeg)과 화면 파형이 다른 엔진**이 되면 어긋난다(0순위-B).

**`shopping_shorts/app.py`**
| 줄 | 이름 | 비고 |
|---|---|---|
| 20568 | `_TRIM_SAFETY_PAD = 0.08` | 끝 자동 자르기가 남길 여백(첫/끝 음절 보호) |
| 20571 | `_apply_beat_trim()` | **트림 판단 단일 출처**. `/trim`·`/trim_all`이 공유. 모드 `auto`/`set`/`nudge`/`reset` + 하한 가드 |
| 20602 | `POST /trim` | `mode=set`(드래그 절대값) **신규** |
| 20633 | `POST /trim_all` | 전 칸 끝 무음 한 번에 |
| 20666 | `GET /wave/{beat_idx}` | peaks·dur·head_sil·tail_sil·**gaps**·**gap_cuts**·floor·pad |
| 20698 | `_gaps_equal()` | 구간 동일 판정(±0.02초) |
| 20705 | `POST /gap` | `add`/`remove`/`all`/`none` — 중간 쉼 저장(비파괴) |
| 20750 | `POST /gap_all` | 전 칸 중간 쉼 한 번에 |

★**왜 `trim_all`/`gap_all`을 따로 뒀나**: 칸마다 부르면 호출이 20번 날아가고 그 사이
장면 실험실 자동저장이 끼어 방금 저장한 값을 덮을 수 있다(2026-09-09 실사고와 같은 모양).
**한 번 읽고 한 번 쓴다.**

**`shopping_shorts/video_assemble.py`**
| 줄 | 이름 | 비고 |
|---|---|---|
| 3217 | `_apply_gap_cuts()` | **핵심 배선.** `assemble()` 진입부에서 `tts_paths`를 잘린 mp3로 교체 |
| 1736 | `_shrink_caps_for_gaps()` | 자른 만큼 자막 구절을 당김 |
| 1775 | `_adjust_caps_for_trim()` | `head_trim`과 `gap_cuts`를 **둘 다** 반영 |
| 576 | `_beat_effective_dur()` | ★**gap을 여기서 빼지 않는다** — 렌더가 이미 잘린 파일을 받으므로 probe에 반영돼 있다. 또 빼면 두 번 빠진다 |

★**왜 `tts_paths` 교체 한 방으로 끝나나**: `_render_mix`·`_beat_timeline`·`_burn_captions`
셋이 전부 `tts_paths`를 받는다. **진입부에서 한 번만 바꾸면 셋이 자동으로 따라온다** —
세 곳에 같은 잘라내기 논리를 심지 않는다(0순위-B).
※ 렌더의 `-ss`는 **앞만** 건너뛸 수 있어 중간 구간은 표현이 안 된다. 그래서 파일을 미리 만든다.

★**`_adjust_caps_for_trim`에서 주의한 것**: 앞트림과 중간컷이 **둘 다** 걸릴 수 있다.
한쪽만 반영하고 `return`하면 다른 쪽이 통째로 죽는다(0순위-B의 "조건부 값 덮어쓰기"와 같은 꼴).
→ 테스트 `test_captions_apply_both_head_trim_and_gaps`가 이걸 지킨다.

**`shopping_shorts/capcut_draft.py:807`** — 내보낼 때도 `cut_gaps`로 **잘린 사본**을 복사.
타임라인 길이는 잘린 기준이라 원본을 주면 캡컷에서만 쉼이 남아 어긋난다.

### 화면 `shopping_shorts/static/produce.html`
| 줄 | 내용 |
|---|---|
| 1641~ | `.wf` 계열 CSS(필름 띠·손잡이·`.wf-gap` 노란 빗금·진행선·`−0.00s` 태그) |
| 14972~15243 | `WAVEFORM-START` ~ `WAVEFORM-END` 블록 전체 |
| 14979 | `_wfHTML()` 껍데기 |
| 14995 | `_wfLoad()` 파형 비동기 로드 |
| 15006 | `_wfPaint()` 막대·쉼·잘린부분·손잡이 위치 그리기(높이는 `sqrt`로 폄) |
| 15053 | `_wfGapClick()` 쉼 클릭 토글 |
| 15077 | `_wfDragStart()` 손잡이 드래그(놓을 때 1회 저장) |
| 15121 | `wfTrimOne()` 줄별 `✂ 빈 곳 자르기` |
| 15155 | `wfTrimAll()` 상단 일괄 — **끝(`trim_all`)과 중간(`gap_all`)을 함께** 부른다 |
| 15190 | `_wfInit()` 로드 + 드래그·클릭 위임 연결 |
| 15458 | `_vpPlayTrimmed()` ▶가 트림·중간컷을 반영해 재생 |

★**`_wfInit`에서 클릭을 부모에 위임한 이유**: 쉼 구간은 `_wfPaint`가 `innerHTML`로 갈아끼우므로
구간마다 리스너를 걸면 다시 그릴 때 날아간다.

★**`▶` 재생을 고친 이유**: 종전 `vpPlayBeat`는 `a.currentTime=0`으로 **늘 원본 전체**를 틀었다.
파형에서 잘라도 이 단계에선 안 잘린 소리가 나 "잘랐는데 그대로네"가 된다.

★**옛 장식 파형(`_waveHTML`)**: 지웠다가 겹쳐 보여서 **음성 없는 줄에만** 남겼다
(`b.tts_preview_url ? '' : _waveHTML(i,b)`). `test_tts_panel_tidy`가 이걸 검사하므로
테스트도 함께 갱신했다(진짜 파형은 재생 중 **색이 들고 진행선**이 지나간다 —
모양이 소리 그 자체라 흔들면 거짓이 되므로 `wavePulse`를 쓰지 않는다).

---

## 5. 검증 — 전부 실행 결과다 (0순위-A1)

```
① 브라우저 실기동 (playwright, 진짜 마우스, 로컬 :8872)   → 12항목 전부 OK, JS오류 0
     파형 120막대 / 높이 54가지(장식이면 일정하다 → 진짜 음량 확인)
     쉼 클릭 저장(화면1 서버1) · 되살리기(화면0 서버0)
     드래그 head_trim 0 → 0.861, 서버 저장값 0.861 (일치)
     일괄 "빈 곳 1.9초를 잘랐어요", 잘린 구간 12개
     전부 되돌리기 → 잘림 0 / head_trim 0
② 실제 렌더 2회(자르기 OFF/ON)  → 29.05초 → 27.13초 (1.93초↓, 예상 1.87초)
     ★완성된 mp4의 무음을 직접 쟀다: 10구간 2.48초 → 2구간 0.33초
③ 자막 타이밍  → 컷 앞 구절 0.00 이동 / 컷 뒤 정확히 0.26초 당김, 누적오차 없음
     총 자막시간 5.928 → 5.536초 = 잘라낸 0.392초와 정확히 일치
④ 캡컷 내보내기 → 5개 비트 전부 잘린 사본(6.10→5.71 등), 렌더와 같은 길이
⑤ pytest 신규 26건 통과 (gap_cuts 11 + 한글경로 3 + trim API 12)
     ★전부 "고치기 전 코드에서 실패하는지" 확인함 — gap 반영을 끄면 2건 실패
⑥ 전체 스위트 27 failed / 8055 passed (11분)
     겹칠 만한 3건(test_scene_style·test_scene_style_hook_caption·test_silent_except_budget)을
     git stash로 **내 변경 없이** 돌려보니 똑같이 3건 실패 → 기존 실패, 회귀 아님
```

**들어볼 산출물** (`out/`):
`무음자르기_전.mp3`(28.77초) · `무음자르기_후.mp3`(26.89초) ·
`무음자르기_렌더_전.mp4`(29.05초) · `무음자르기_렌더_후.mp4`(27.13초)

### 검증 중 내가 틀렸던 것 (기록해 둔다)
- 처음 playwright에서 드래그가 "실패"로 나왔다 → 기능이 아니라 **검사가 틀렸다**.
  손잡이가 y=1425로 화면(1100px) 밖에 있어 `elementFromPoint`가 `null`이었다.
  `scrollIntoView` 후 정상 동작. **"실패"를 바로 코드 탓하지 말 것.**
- `MIX_JOB`은 `let` 바인딩(`produce.html:9197`)이라 `window.MIX_JOB=`로는 안 바뀐다.
  페이지 문맥에서 `MIX_JOB="..."`로 대입해야 한다.
  ※ 이 줄 번호도 내가 처음에 9194로 잘못 적었다(CSS를 넣기 전 grep 결과였다) —
    **기록의 줄 번호는 쓰기 직전에 다시 뽑아라.**

---

## 6. 재현·시험 방법 (다음 세션이 바로 쓸 수 있게)

```bash
# 트랙 폴더엔 DB가 없다(gitignore) — main에서 복사해 온다
cp "C:/Users/CH/Desktop/로또의 주식/shopping_shorts/data/reference.db" shopping_shorts/data/

# 로컬 서버
PYTHONIOENCODING=utf-8 python -m uvicorn shopping_shorts.app:app --port 8872 --host 127.0.0.1

# 시험용 job (실제 음성 5개 있음)
409f894230c6

# API 확인
curl "http://127.0.0.1:8872/api/produce/mix/409f894230c6/wave/0"
curl -X POST ".../gap_all" -H "Content-Type: application/json" -d '{"mode":"auto"}'

# 브라우저 전수(스크립트는 scratchpad에 있었다 — 필요하면 다시 만들 것)
#   주의: ①MIX_JOB은 let이라 페이지 문맥에서 대입 ②요소를 scrollIntoView 후 진짜 마우스로
py tools/audit_subprocess_encoding.py            # 인코딩 결함 전수(0=깨끗)
python -m pytest shopping_shorts/tests/test_gap_cuts.py shopping_shorts/tests/test_silence_korean_path.py shopping_shorts/tests/test_mix_trim_api.py -q
```

⚠️ 콘솔이 cp949라 한글 출력이 깨져 보인다 — `PYTHONIOENCODING=utf-8`을 붙이면 읽힌다.

### ⚠️ 기록은 **main 폴더에도** 둬야 찾힌다 (2026-09-22 발견)
`find_work.py`는 `BASE/handoff` · `BASE/wiki/log.d`만 본다(`tools/find_work.py:40`).
**트랙 폴더에만 쓰면 병합 전까지 다음 세션에게 안 보인다** — 0순위-A2가 막으려던
"파일은 있는데 찾을 방법이 없다"가 그대로 재현된다.
→ 이 트랙도 처음엔 안 찾혔다. 트랙 폴더에 쓴 뒤 **main 폴더로 복사**했다:
```
cp .tracks/<트랙>/handoff/<트랙>.md handoff/
cp .tracks/<트랙>/wiki/log.d/<트랙>.md wiki/log.d/
```
기록은 문서라 흡수 위험이 없다(코드가 아니다). 확인: `py tools/find_work.py <주제어>`

---

## ⏭ 다음 할 일

1. **사장님 청취 판정 대기** — `out/무음자르기_후.mp3`를 듣고 숨 간격이 적당한지.
   - 너무 붙으면(기관총) `audio_post.py:334` `_GAP_KEEP`을 **올린다**(0.06 → 0.10 등)
   - 여전히 늘어지면 **내린다**. 판정값도 같은 자리: `_GAP_THRESHOLD`(-30dB) · `_GAP_MIN_DUR`(0.10)
   - **한 곳만 고치면 렌더·캡컷·화면이 전부 따라온다.**
2. **라이브 배포는 승인 후** (0순위-A1c — 고객 화면이 바뀐다).
   ```
   py tools/track.py finish TTS파형자르기      # 게이트 통과 시 main → 3분 뒤 라이브
   ```
   승인 전까지는 트랙 브랜치에만 둔다(지금 상태).
3. **배포 후 반드시** 라이브에서 내 손으로 눌러보고 보고(0순위-A1). 로컬 검증은 중간 단계다.
4. (선택) `tools/audit_subprocess_encoding.py`를 `track.py finish` 게이트에 넣는 안 —
   같은 인코딩 사고가 다른 파일에서 재발하는 걸 막는다. 아직 안 넣었다.
