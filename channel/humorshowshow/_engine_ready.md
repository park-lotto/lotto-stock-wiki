# 썰템쇼 제작 엔진 준비됨 — 사용법 (2026-10-18, 관제 097)

> 주인: `tools/calcopy/engine/preset_make.py`(한 명령 제작기) + 프리셋 `channel/humorshowshow/preset/썰템쇼_화자썰/`(manifest `channel_rules.make`).
> 2줄 누적 자막 판단 = `tools/calcopy/narr_video.py:steps_of`(맛템썰템과 같은 함수를 부른다 — 두 벌 아님).
> 확인: 벤치 NBdm 재료로 끝까지 렌더해 0.5·1.5·2.6·3.5·10·20초 프레임을 직접 봄 — 훅 카드(제목 2줄 흰·연두, 라벨 띠) → 약 2초부터 본문 틀(로고 썰템쇼·게시글 제목·조회수 줄) + 2줄 누적 자막 정상.
> 다른 채널 무영향: 잇썸홈 작품5 재렌더 MD5 `9dcdd9fa…` 같음, 재미썸홈 작품3·5 계획 시트 MD5·검사 표 같음.

## 1. 명령
```
PYTHONUTF8=1 py tools/calcopy/engine/preset_make.py channel/humorshowshow/preset/썰템쇼_화자썰 channel/humorshowshow/<작품폴더> --plan        # 계획 시트(TTS 전)
PYTHONUTF8=1 py tools/calcopy/engine/preset_make.py channel/humorshowshow/preset/썰템쇼_화자썰 channel/humorshowshow/<작품폴더> --allow-tts   # 완성(TTS 1회, 캐시되면 재호출 0)
```
- 완성본 = `<cand_dir>/make/final.mp4` · 1초 시트 `make/sheet_1s.jpg` · 검사표 `make/run_log.json`. 검사 전부 ○일 때만 바탕화면 `칼카피_썰템쇼_<제목>.mp4` 복사·`channel/결과물.json` 등록.
- 바탕화면 하위 폴더(`칼카피영상/썰템쇼/`)로 보내려면 `--desktop-dir "C:/Users/CH/Desktop/칼카피영상/썰템쇼"`.

## 2. 작품 폴더 꼴
`channel/humorshowshow/작품N_<소재>/{대본.json, 근거.md, 재료.json, plan/}`

### 대본.json
```json
{
 "desktop_title": "코스트코무스",
 "frame_vars": {
  "frames[hook].layers[text:title].text": "한국 코스트코만\n대놓고 차별한 디저트",
  "frames[hook].layers[text:label].text": "한국 코스트코만 대놓고 차별한 디저트",
  "frames[body].layers[text:label].text": "한국 코스트코만 차별한 디저트",
  "frames[body].layers[text:label#4].text": "7544"
 },
 "lines": [
  {"text": "한국 코스트코만 대놓고 차별한 디저트", "tts": "한국 코스트코만 대놓고 차별한 디저트?"},
  {"text": "디저트 하나로 북미 코스트코를/씹어먹은 한 프랑스 회사", "tts": "디저트 하나로 북미 코스트코를 씹어먹은 한 프랑스 회사."},
  {"text": "다크 초콜릿/제대로 때려박은 맛좀 봐라!", "speaker": "제조사", "tts": "다크 초콜릿 제대로 때려박은 맛 좀 봐라!"},
  {"text": "아 이걸 어떻게/안쓰고 버리냐고 ㅋㅋ", "tts": "아 이걸 어떻게 안 쓰고 버리냐고."}
 ]
}
```
- `frame_vars` = 틀의 작품별 글(훅 제목 2줄은 `\n`, 훅 라벨 띠, 게시글 제목, 댓글 수). 조회수 줄(`label#3`)은 기본값이 있어 생략 가능.
- **첫 줄 = 훅 줄**: 훅 카드(제목만, 자막 없음) 동안 읽힌다. 본문 첫 박자 시작이 훅→본문 틀 경계(자동).
- `text` = 화면 자막. **`/` = 화면 줄바꿈 자리**: 1줄이 먼저 뜨고 그 뒤 2줄째가 덧붙는다(누적). `/`가 없으면 14자 안팎으로 자동으로 자른다. 3조각 이상이면 [1]→[1+2]→[3]→[3+4]…
- `tts` = 읽는 글(**필수**에 가깝다): `ㅋㅋ·ㄷㄷ·ㅇㅇ` 같은 낱자는 빼야 한다(A11 검사가 막는다). 자막의 일부러 틀린 글자(촤컬릿 등)는 tts에서 바로잡는다.
- **화자 대사 줄** = `"speaker": "제조사"`: 화면 1줄 앞에 `제조사 : `가 붙고, 나레는 대사만 읽는다(화자 이름은 글자 수·말속도에서 빠진다). 한 장에 2인 대화가 들어가면 text에 `프랑스 : 너네 …/한국인들 : 흠 …`처럼 직접 쓰고 tts에는 대사만 쓴다.

### 재료.json
```json
{"cand_dir": "C:/숏템_칼카피/humorshowshow/작품N_<소재>",
 "shots": [
  {"src": "abc123.mp4", "ss": 12.4, "kind": "제품영상", "seen": "유리병 무스 뜨기", "src_crop": [x, y, w, h]},
  {"cont": true},
  {"src": "meme:0V_NUgfAfRE", "ss": 3.0, "kind": "짤", "seen": "고개 젓는 남자"}
 ]}
```
- **행 수 = 자막 조각 수**(1줄 조각 1행, 2줄째 덧붙음 1행). 2줄째에도 같은 컷을 이어 쓰려면 `{"cont": true}`. 개수가 맞지 않으면 제작기가 조각 목록을 찍어 주며 멈춘다(그 목록대로 행을 맞춘다).
- 훅 줄(첫 줄)이 `/`로 2조각이면 둘째 행은 `cont`(훅 카드는 한 컷).
- `src`: `cand_dir` 안 mp4 파일 이름 · `meme:<id>` = 짤 팩 `C:/숏템_칼카피/packs/meme/meme_pack/<id>.mp4`(옆 `<id>.jpg`로 미리 보기). 짤은 해상도 검사에서 빠진다.
- `src_crop` 생략 = 가운데에서 1080:878 비율로 크롭(`crop_x`로 가로 위치만 지정 가능). 남의 글자는 `src_crop`으로 뺀다. 확대는 2.3배 이하, 원본 720p 이상(A4).
- 창: 본문 1080×878. 훅 카드 창(1080×1172)은 같은 재료를 렌더러가 채운다(위아래가 더 보임).

## 3. 검사 기준(manifest `checks`, 출처 = 뜯기 8편·줄판독 21편)
길이 24.1~32.7초 · LUFS −15.3~−12.3 · 최고점 ≤−0.5 · 말속도 8.17~9.03(목표 8.6, 필재 tts_tempo 1.6) · 컷 중앙 1.16~2.4초 · 끝 컷 ≥1.2 · 짤 비율 ≤0.3, 같은 짤 1컷 · 화면 자막 한 줄 ≤18자(공백 포함, `화자 : ` 뺌) · 효과음 ≤줄 수(density low) · B13 중복 0 · B16 되감김 0 · A11 tts 낱자 0.
BGM `machi_no_dorufin`(경쾌, 벤치 곡은 못 찾음) · 효과음 sfx_pack density low.

## 4. 알려진 점
- 효과(빨간 화살표·반짝)는 아직 없다(벤치 54줄에 있음). 엔진 요청 대상.
- 렌더 시간: 틀 합성 약 80초(누적 자막이라 장면 25개), 전체 약 2분(TTS 캐시 뒤).
