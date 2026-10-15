# channelkit/bench — 채널 실측 도구 한 벌 (설계, 2026-09-28)

사장님 계획: 칼카피 → 장르별·채널별 쇼츠 프리셋 전부. 그 첫 부품 = **채널을 던지면 기준표 숫자(bench.json)가 나오는 자 한 벌**.
지금은 세 벌(옆 세션 `카피/bench/_tools` 3,132줄 · 숏템엔진 `tools/hotpeople/measure` 18개 · 볼케이노 자 40개 목록)이라 같은 값을 다르게 잰다(함수 지도 `function_map.md` 겹침 24건).

## 0순위-C 두 줄

- **주인 함수**: 기준 하나 = `channelkit/bench/<영역>.py`의 함수 하나. 채널 좌표는 `layout.py`가 **자동으로** 찾아 `layout.json`에 적고, 나머지 자는 전부 그것을 읽는다(하드코딩 0).
- **결과물 검사**: `bench.run("hotpeople")`이 `baselines/hotpeople_2026-09-28.json`(이번 주 실측값)을 허용 오차 안에서 **재현**해야 통과. 문턱 하나를 바꾸면 빨강이 떠야 한다(사보타주). 검사 도구는 모듈과 같은 커밋.

## 1. 겹침 24건의 결정 — 자가 둘이면 갈린다

| 자 | 세 벌의 차이 | 결정 (근거) |
|---|---|---|
| 통합 LUFS | 정규식 4종 | ebur128 stderr **마지막** `^\s*I:` (re.M) — 볼케이노 measure_lufs와 동일 |
| 단기 폭 | sorted-index vs percentile / 앞 30개 버림 | 정렬 인덱스 `[int(n·.9)]−[int(n·.1)]`, −70 제외, **20개 미만 None**, 버리기 없음 (볼케이노 lufs_spread) |
| 모노 | (L+R)/2 vs `-ac 1` | **(L+R)/2 f32** (`-ac 1`은 +3.01dB — 볼케이노 규율) |
| 8~16k 고역 | FIR 1001/정규화 vs 1025 vs PSD | film 방식(kaiser 1001, β8.6, 중심 이득 정규화), dBFS |
| 장면 컷 | scene .15 / .30 / 자체 프레임차 | ffmpeg `select=gt(scene,T)` **T=0.3** on 영상창 crop + 0.2s 병합 + **cut_verify 상관<0.6 확인**. 0.3인 이유: 뜨거운사람들 기준선(컷 22)이 0.3이고 볼케이노 scene_cuts는 T를 서버가 주므로 고정값이 없다. T는 상수 하나(`SCENE_T`)로 두고 baseline에 기록 |
| 길이 | nb_frames/fps vs packets vs 컨테이너 | **프레임 수 ÷ fps** (볼케이노 frame_seconds) |
| 자막 잉크 문턱 | 90/100/110/120 | 극성별 하나: 밝은 배경 → lum<**110**, 어두운 배경 → lum>**200**+외곽선 검사(hardsub_probe 방식). 상수 `INK_DARK`/`INK_BRIGHT` |
| 오프닝 음량 | 20ms RMS p90−p10 (A7) vs ebur128 M | **둘 다 남기되 이름을 가른다**: `A.openvoice`(볼케이노 A7, 나레 채널) / `A.open3s_M`(BGM 채널). 같은 이름 아래 두 계산 금지 |
| 자막 교체 | 띠 차분 10fps 문턱 .01 / 노빠꾸 30fps | 10fps 띠 차분, 문턱 0.01, 0.4s 병합 — 뜨거운사람들 232자막 기준선 |
| 컷↔비트 | ±80ms | 유지, 우연 일치율(창÷비트 간격)을 함께 출력해 "동기 아님" 판정을 자동화 |

나머지(제목 사라짐·형광펜·빨강·글꼴 IoU·줄 폭 90%·회귀식)는 한 벌에만 있어 그대로 옮긴다.

## 2. 구조

```
shopping_shorts/channelkit/bench/
  __init__.py     run(channel, sample_dir, out_dir) → bench.json      ← 유일한 입구
  probe.py        ffprobe · 프레임 추출(rgb24/gray) · 길이=프레임÷fps        (공용, 다른 모듈은 ffmpeg 직접 호출 금지)
  layout.py       L.*  영상창(시간변화 행) · 자막띠 위치(위/아래/안)·극성 · 로고띠 · 배경색 · 세이프존  → layout.json
  captions.py     S.* T.sub_*  자막 교체 시각 · 줄 수/폭/행간/시작 y · 형광펜·강조색 · 획폭·외곽선·그림자·등장효과 · 시트 png
  cuts.py         T.cut_* K.rehook_gap  장면 컷(+상관 검증) · 첫 컷 · std · 최장 무변화 · 컷=자막 일치 · 줌 추적
  audio.py        A.*  I/TP/LRA/S폭/M · 8~16k · openvoice · BGM bpm·온셋·비트동기 · 덕킹(나레 있을 때) · Shazam 곡
  speech.py       N.*  스피치매틱스 단어시각 → 말한 시간·글자/초·첫 발화·쉼 · F0 피치 · 나레↔원음 교대(turns)
  text.py         W.* K.*  자막/전사 텍스트 → 어미·숫자·따옴표·문장부호·훅 유형·이름 공개·전환·마무리·단어 빈도·노출 회귀
  vision.py       제미니 판독(자막 시트·훅 시트) — LLM 의존은 여기만. 개수 검사·재시도·모양 확인 필수
  channel.py      C.* V.*  yt-dlp 메타 · 업로드 주기 · 조회 분포 · 상·하위 대조(min_age) · 댓글·고정댓글·업로더 댓글
  report.py       bench.json → 기준표 md/html · 재현일치도(원본 vs 우리) 표
  baselines/      hotpeople_2026-09-28.json …   ← 검사 기준선
  cache/          (gitignore) 표본 mp4·프레임
```

- `layout.py`가 먼저 돌고, 나머지는 `layout.json`만 읽는다. 자막띠가 영상창 **위**(쇼핑)·**아래**(뜨거운·노빠꾸)·**안**(영화)인 세 경우와 잉크 극성(밝은 글자/어두운 글자)을 여기서 정한다 — 함수 지도 §4.
- 채널마다 다른 것은 **layout.json과 프로필 플래그**(나레 있음/없음, BGM 있음/없음)뿐. 코드에 채널 이름이 나오면 설계 위반.
- 옆 세션 것에서 가져오는 자(뜨거운사람들에 없던 것): 덕킹(duck) · 피치(narr_pitch) · 나레↔원음 교대(turns/match_text) · 줌 추적(zoom_track) · 오프닝 카드(opening) · 정적 텍스트(static_texts) · 8~16k · 상관 컷 검증(cut_verify).

## 3. bench.json 모양

```json
{"channel":"hotpeople","measured_at":"2026-09-28","sample":["z1fgI__kSPw",…],"profile":{"narration":false,"bgm":true},
 "layout":{"canvas":[1080,1920],"window":[0,483,1080,790],"caption":{"pos":"below","band":[1272,1460],"ink":"dark"},"logo":[91,195],"bg_rgb":[248,248,248]},
 "criteria":{"S.chars":{"value":16,"stat":"median","range":[11,22],"n":232,"unit":"자","method":"captions.chars"}, …},
 "per_video":{"z1fgI__kSPw":{…}}}
```
기준표 id(L/S/H/T/A/N/W/K/M/C/V)가 곧 키. `method`는 잰 함수 이름 — "이 값 어디서 났나"를 파일이 스스로 말한다(0순위-C 표식).

## 4. 검사

- `tests/channelkit/test_bench_hotpeople.py`: 표본 10편(캐시, 없으면 yt-dlp) → `run` → baseline 대비 허용 오차(좌표 ±5px, 개수 ±1, 초 ±0.1, LUFS ±0.2, 비율 ±2%p) 안이면 통과.
- 사보타주: `SCENE_T`를 0.15로 바꾸면 컷 수가 기준선을 벗어나 **빨강**이 떠야 한다. 안 뜨면 검사가 아무것도 안 재는 것(0순위-A1c).
- 두 번째 채널(노빠꾸패밀리)로 **좌표 자동 검출**을 시험: 옆 세션 문서의 실측값(창·자막띠)과 ±5px.

## 5. spec과의 연결 (2단계 — 이 설계의 다음)

`channel_presets/<name>/spec.py`는 뼈대 상수를 손으로 적지 않고 `bench.baseline("<name>")`에서 읽는다. 결(`POLICY_`·폰트·색·BGM)은 spec에 남는다. 그래야 "칼카피본 = bench.json" 자산이 되고 응용 프리셋은 결만 바꾼다.

## 6. 순서

1. `probe`·`layout`·`captions`·`cuts`·`audio` (뜨거운사람들 기준선 재현이 검사) — 1일
2. `text`·`vision`·`channel`·`report` 이관 — 0.5일
3. `speech`·덕킹·피치·교대·줌 (옆 세션 자 이관, 나레 채널용) — 0.5일, 검사 = 김시선 문서값
4. 노빠꾸패밀리 표본 10편으로 자동 좌표 시험 → 통과하면 2호 채널 spec 착수
