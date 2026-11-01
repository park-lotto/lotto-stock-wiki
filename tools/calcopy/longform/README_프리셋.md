# 지식한입형 롱폼 프리셋 (칼카피 v2 · 2026-11-01)

경제·시사 해설 롱폼(10~15분, 16:9)을 '지식한입' 채널의 형식(콜드 오픈 훅 → 로고 범퍼 → `대주제 : 원인 n` 챕터 → 마무리 → "오늘 영상 여기까지고요" → 아웃트로)으로 만든다.
형식·연출·편집 규칙만 복제했다. 레퍼런스 영상·음성·대본·로고는 들어 있지 않다.

## 폴더
| 파일 | 하는 일 |
|---|---|
| `config.json` | 채널 이름·괄호·아웃트로 문구·색·음량·BGM·성우·속도·범퍼 위치 |
| `shots.py` | 샷리스트(문장 번호 → 화면 종류·검색어·차트 숫자·출처). **소재마다 새로 쓴다** |
| `tts.py` | 대본 md → 문장 목록(`narr/lines.json`). `--parse-only` 면 목록만, 아니면 타입캐스트로 녹음(예전 방식) |
| `tts_elevenlabs.py` | **기본 녹음(v2)** — 일레븐랩스 Chris · 속도 1.2 · 숫자+단위 붙여쓰기 · 첫소리 보존 → `narr/trim/` |
| `숫자한글읽기_지침.md` | 녹음용 글(tts 칸)의 숫자·기호를 한글로 바꾸는 규칙 |
| `gen_images.py` | AI 장면·실사 대체 이미지(Codex GPT 이미지) → `assets/img/sNNN.png` |
| `stock.py` | Pexels 실사 영상 → `assets/stock/sNNN.mp4` (있으면 이미지보다 먼저 씀) |
| `render.py` | `timeline`(타임라인·자막·오디오 믹스) → `video`(프레임 렌더) → `mux`(합치기) |
| `fonts/` | Pretendard(OFL), Black Han Sans(OFL), Nanum Pen Script(OFL), 함초롬바탕 Bold(한컴 무료 배포) |
| `media/bgm/` | **zip 에는 곡 파일이 없다 → 처음에 `python -X utf8 get_bgm.py` 로 받는다.** Kevin MacLeod(incompetech) CC-BY 4.0 — Cool Vibes · Groove Grove · Crypto(본편, 범퍼 구간마다 차례로 교체), Funky Chunk(징글·아웃트로) |
| `assets/article/` | 기사 캡처(aNNN.png + json: url·phrase·boxes) → `article="aNNN", circle_at=[(문장, 단어)]` 로 실제 기사 화면 + 형광펜 + 빨간 동그라미 |
| `media/sfx/` | HyperFrames 번들 효과음 whoosh·pop·typing·thud·ding |
| `규격표.md` | 레퍼런스 3편 실측·분석 규격(이 프리셋의 근거) |

## r4 (11-01 사용자 피드백 반영)
- 화면은 실사 영상이 기본(`assets/stock/sNNN.mp4`, 출처는 `assets/stock/credits.md`). Mixkit·Coverr(표기 불필요), Wikimedia Commons(CC BY/BY-SA 설명란 표기 필수). 뉴스 방송사 영상은 쓰지 않는다
- 펀치 문장은 타이포 카드: `add(a, b, "typo", items=[(문장, 단어, "글자 [[강조]] ~~취소~~ / 줄바꿈", 바탕 ivory|black|lime|pink, 위치 L|C|R, 크기 S0|S1|S2, 등장 stamp|whip, 박스색)])` — 한 편에 10~12곳
- 기사 인용은 글자 나열 대신 기사 캡처 + 빨간 동그라미
- 라벨 키워드는 크게, 항목마다 색이 다르게(노랑·파랑·핑크). 큰 문구(big)도 `[[강조]]`·`~~취소~~` 지원
- 그림에 글자가 필요한 장면(피켓·서류)은 STYLE의 'No text'를 빼고 글자를 지정해 그린다(`regen_text.py`)
- 배경음악은 곡마다 RMS를 맞추고 150Hz 아래를 깎는다(`bgm_highpass`). 베이스가 큰 Lobby Time 대신 Backbay Lounge

## v2 (11-01 저녁 사용자 피드백 반영)
- **목소리: 일레븐랩스 Chris** (`PDoCXqBQFGsvfO0hNkEs`, eleven_multilingual_v2, stability 0.5 · similarity 0.8 · style 0.1 · speed 1.2). 상업 이용은 일레븐랩스 유료 요금제 조건을 확인한다
- **속도는 일레븐랩스 speed 로만 낸다.** 녹음 뒤 atempo 로 또 빠르게 하면 음색이 깨져 튄다
- **첫소리 보존:** 앞뒤 무음 자르기는 -55dB, 앞 0.06초 · 뒤 0.08초 남김. -40dB 처럼 빡빡하면 문장 첫 단어가 뭉개진다
- **숫자는 한글로:** tts 칸의 숫자·%·기호를 `숫자한글읽기_지침.md` 대로 한글로 바꾼다(화면 자막은 숫자 그대로). 남아 있으면 `tts_elevenlabs.py`가 멈춘다
- **숫자와 단위는 붙여서 보낸다**(지침의 '띄어 쓴다'의 예외): "오 퍼센트" → "오퍼센트". 띄우면 "오, 퍼센트"로 끊어 읽는다. `tts_elevenlabs.py`가 자동으로 붙인다
- **배경음:** 가벼운 재즈(Backbay Lounge) 대신 긴장감 있는 **Crypto** 를 세 번째 본편 곡으로
- 녹음 확인은 faster-whisper 받아쓰기(아르곤은 오디오 받아쓰기에서 명령 권한을 요구해 헤들리스로 막힌다)
- 결과: 13분 13초 · -16.4 LUFS · 분당 약 380음절
## 소재 찾기
`소재발굴가이드.md` — 채널이 다루는 4갈래(나라 현황·기업 흥망·한국 생활경제·정치/안보), 소재 얻는 방법(이번 주 뉴스 → 통념 → 반박 숫자 → 원인 분해), 매주 루틴, 점검표

## 아르곤 대조 때 주의
- 아르곤은 긴 영상을 30초 단위로 들어서 :00/:30마다 "피치다운"이 있다고 잘못 보고한다 → 무시
- 480p 화면 자막 글자를 잘못 읽는다(OCR) → 자막 데이터(`build/timeline.json`의 subs)로 확인한 뒤 고친다
- 영상 2편(완성본+레퍼런스)을 high로 동시에 보게 하면 응답이 끊긴다 → 규격표.md + 완성본 1편, 동시 4개 이하
- (11-01 3차 대조) 아르곤은 최신 뉴스 수치를 모른다 → "금리 4.98%는 틀림, 3%대", "국가데이터처는 없는 기관" 같은 사실 지적은 사실기록 출처로 먼저 확인하고 버린다. 사실 확인은 jev-search 로 한다
- (11-01 3차 대조) 아르곤은 화면에 없는 문제도 지어낸다(자막 상자 사라짐·출처 두 줄 겹침·막대 높이 뒤바뀜 모두 사실 아님) → '상' 지적은 `python -I render.py frame <초>` 로 그 장면을 뽑아 직접 확인한 뒤 고친다
- 대조는 두 번이면 충분하다. 세 번째부터는 지적 대부분이 오독·지어낸 것이라 비용 대비 얻는 게 적다

## 순서 (새 소재 한 편)
0. 처음 한 번: `python -X utf8 get_bgm.py` (배경음 5곡) · 예시 완성본은 `예시/완성본_미리보기_360p.mp4`
1. 소재 → Jev 판정(`jev-screen.ps1`) → 채널 헌법으로 대본(말투는 아래 규칙) → `대본.md`
   - `## [챕터명]` 줄 = 좌상단 캡슐 문구, `[범퍼]` 줄 = 훅 끝 로고 범퍼, 문장 끝 `{F#}` = 사실기록 번호(읽지 않음), `<!-- -->`로 시작하는 줄 = 뺀 문장
2. `python -X utf8 tts.py 대본.md narr --parse-only` → `narr/lines.json` 의 tts 칸 숫자를 `숫자한글읽기_지침.md` 대로 한글로 바꾼다 → `python -X utf8 tts_elevenlabs.py` (예전 타입캐스트: `python -X utf8 tts.py 대본.md narr --voice Taesub --tempo 1.15`)
3. `shots.py` 작성: 문장 1~2개(5~7초)마다 샷 1개. 비율은 실사 45% · 차트/표 25~30% · 인용 카드 15% · AI 5% 안팎. 숫자는 사실기록에 있는 것만 쓴다
4. 그림: `python -I gen_images.py ai 4` → `python -I stock.py`(Pexels 키 있을 때) → 남은 칸은 `python -I gen_images.py stock-fallback 4`
5. `python -X utf8 render.py timeline` → `python -X utf8 render.py video` → `python -X utf8 render.py mux` → `_inventory/` (경로에 한글이 있으면 `-I` 대신 `-X utf8`)
6. 검수: 완성본 480p + `규격표.md`를 agy(`gemini-4-argon-high`)에 주고 관점 8개(훅·구조, 말투·발음, 자막, UI·출처, 그래픽, 편집 호흡, 오디오, 사실·표현)로 차이를 타임코드 목록으로 받아 고친 뒤, 한 번 더 대조한다(두 번째가 마지막)

## 말투 규칙 (실측)
- 해요체 36% · 하십시오체 28% · ~더라고요/~대요 15% · ~거든요/~잖아요/~죠 15% · 반말 추임새(~란 말이야/~거냐) 4%
- 긴 설명 뒤 짧은 단정문("전혀 아니었습니다.") · 입으로는 어림수와 비유, 화면에는 정밀 수치와 출처
- 훅: 체감 현상 → 그럴듯한 통념 → "찾아보니까 전혀 아니었습니다" + 숫자 → 핵심 질문 → 범퍼
- 마무리: "좀 거칠게 정리를 하자면은" → 3문장 요약 → 전망 → "오늘 영상 여기까지고요." (구독·좋아요 멘트 없음)

## 비밀값
- 일레븐랩스: `~/.volcano/keys/elevenlabs` · 타입캐스트: `~/.volcano/keys/typecast` · Pexels: `PEXELS_API_KEY` 또는 `~/.volcano/keys/pexels` — 파일에 넣지 않는다

## 크레딧(설명란에 넣기)
Music: "Cool Vibes", "Groove Grove", "Crypto", "Funky Chunk" Kevin MacLeod (incompetech.com) Licensed under Creative Commons: By Attribution 4.0 License http://creativecommons.org/licenses/by/4.0/
