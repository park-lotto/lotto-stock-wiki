# 얜샷템 하이브리드 파이프라인 (`tools/calcopy/hybrid/`) — 2026-10-18, 관제 097

연예인 원음(얜샷템 틀) + 나레(잇썸홈 / 재미썸홈 틀) 숏폼을 **편마다 스크립트를 복사하지 않고** 대본.json·재료.json·틀만으로 만든다.
옛 방식(오푸스 1명이 편당 75~140분·툴콜 140~230회)에서 시간이 간 곳 = 렌더 스크립트 복사·손질 / 제품 영상 통째 받기 / 무료 제미나이 한도 / 이름 오독 재합성 21회 / 렌더-보기 반복.

## 파일
| 파일 | 역할(판단 주인) |
|---|---|
| `render_itssum.py` | 잇썸홈판 렌더러 한 벌 — `timeline()` 이 시각의 주인. 함익병·박세리·장윤정·최은경 손질 전부 포함(원음 조각/줄 여럿·mute·tts_override·느린 줄 당김·max 검사) |
| `render_jaemi.py` | 재미썸홈판 렌더러 한 벌 — `timeline()`·`narr_prep()`. tts_tempo·punct_at 없으면 자동(`auto_tempo`·`auto_punct_at`), 'ㅈ' 잘림·오프너 −0.25 수리 포함 |
| `legacy_import.py` | 옛 편(make_render.py / make.py 상수) → v2 대본·재료 |
| `gemini_server.py` | 재수출 — **주인은 `tools/calcopy/engine/gemini_server.py`**(10-18 엔진으로 옮김). 서버 제미나이(회원 풀·key_vault, 키는 PC 에 안 옴), 작업×모델 병렬(스레드 ≤12), 모델 2개 교차. 엔진 `gemini_free.ask` 가 로컬 한도 때 자동 대체 경로로 쓴다 |
| `server_ai.py` | 받아쓰기(gemini_server 로 위임)·**유튜브 Data API 검색**(서버 키 풀) |
| `screen.py` | 후보 검색(yt-dlp + 서버 API) → 받기 전 가려내기(메타·자동자막 키워드·360p 토막 시트) → 고른 것만 1080p(구간만도 됨) |
| `name_check.py` | 이름 구절만 합성·받아쓰기로 표기 고르기(본 TTS 전). 사전 **주인은 `tools/calcopy/engine/name_dict.json`+`name_dict.py`**(10-18 옮김 — preset_make 등 모든 TTS 가 읽는다) |
| `checks.py` | 렌더 뒤 자동 검사 → `B표_draft.md`(B1·2·3·4·9·13·16·16'·17·18·A9·T1 얼굴·받아쓰기 2모델) + 줄별 대조표 |
| `thumb.py` | 0초·H 구간 연예인 얼굴 검사(YuNet) + 업로드 썸네일 JPG(얼굴 크기·정면·선명도 1등 프레임, 틀 제목 포함) |
| `run.py` | 단계 실행기(이어 돌리기·`stage_log.json` 초 장부(주인 `engine/stage_log.py`)·두 판 동시 렌더) |
| `briefs/*.md` | 소넷 워커 브리프(research · screen_pick · script) · 오푸스 판정(review) |

## 한 편 돌리는 법 (부모 오푸스 세션)
```
py tools/calcopy/hybrid/run.py 이영자 init --source <원본URL> --product "고렌샤크 요가신발" --keywords 고렌샤크,gorenshark --queries "고렌샤크 요가 신발" "gorenshark shoes"
py tools/calcopy/hybrid/run.py 이영자 download            # 원본 1080p + 자막(chosen 없으면 원본만)
  → 소넷 워커(briefs/research.md) : 조사.md + asr/spans.json              [병렬 가능]
py tools/calcopy/hybrid/run.py 이영자 candidates && … screen   # 도구 3~6분
  → 소넷 워커(briefs/screen_pick.md) : screen.json chosen                 [research 와 동시]
py tools/calcopy/hybrid/run.py 이영자 download && … asr          # 고른 것만 받기 · 원본 구간 받아쓰기(서버 2모델)
  → 오푸스(또는 소넷 초안 → 오푸스 확정, briefs/script.md) : 대본.json·재료.json·근거.md (두 판)
py tools/calcopy/hybrid/run.py 이영자 plan          # 계획 시트 → 오푸스가 컷 눈 확인(A3·A5·A13)
py tools/calcopy/hybrid/run.py 이영자 name_check    # 이름 표기(사전에 있으면 0초)
py tools/calcopy/hybrid/run.py 이영자 render --parallel     # TTS 1회씩 + 두 판 동시 렌더(약 5~6분)
py tools/calcopy/hybrid/run.py 이영자 checks        # B표 초안 + 썸네일 + 얼굴 검사(판당 3~4분, 대부분 check_seams)
  → 오푸스(briefs/review.md) : 대조표 판정 칸만 채워 B표.md
py tools/calcopy/hybrid/run.py 이영자 deliver       # 바탕화면 mp4+jpg (자동 통과한 판만, 아니면 --force 는 사장님 판정 뒤)
py tools/calcopy/hybrid/run.py 이영자 status        # 어디까지·다음은 누가
```
`render_*.py <doc> <work> [--plan]`, `checks.py <doc> <work> --asr`, `thumb.py make <doc> <work>` 는 run.py 없이 따로도 돈다(증명 때 그렇게 썼다).

## 시간(편당, 실측·추정)
| 단계 | 옛 방식(에이전트 보고) | 새 파이프라인 | 누가 |
|---|---|---|---|
| 렌더 스크립트 복사·손질 | 15~30분(편마다) | 0 (JSON 만) | — |
| 제품 영상 받기 | 후보 통째 300~400MB × 3~5개, 10~20분 | 검색+가려내기 3~6분(후보당 수 MB) + 고른 것만 1~3분 | 도구 → 소넷 고르기 |
| 받아쓰기 | 로컬 무료 키 한도 → 1모델·재시도, 5~15분 | 서버 2모델 병렬 10~20초/요청 | 도구 |
| 이름 오독 | TTS 전체 재합성 21회(최은경) | 이름 구절 ≤6회 + 사전 재사용 0회 | 도구 |
| 렌더 | 5분/판(직렬) | 5분/판, 두 판 동시 → 6분 | 도구 |
| 검수 수치 재기 | 오푸스 손으로 20~30분 | checks 3~4분/판(자동) + 판정 5분 | 도구 → 오푸스 |
| **합계(두 판)** | **75~140분** | **도구 ≈25분 + 사람(조사·대본·판정) ≈30~40분, 소넷 2명 병렬이면 벽시계 ≈45분** | |

## 증명(장윤정 테클라, 기존 TTS 재사용)
`C:/숏템_칼카피/yanshottem/_hybrid_pipeline_test/장윤정/` — 잇썸홈판 final.mp4 **MD5 f20e40b5…(옛 완성본과 비트 단위 동일)**, 재미썸홈판 27.10초(옛 27.2 — 'ㅈ' 잘림 수리로 A|B 경계 0.03초 앞) −14.1 LUFS·cps 8.38·컷 중앙 1.80·효과음 8 전부 옛 B표와 같음. 받아쓰기 2모델 원음 덮음 1.0·화자 1·이름 2/2.

## 실측 메모(10-18)
- screen: 후보 1개 = 메타+자막+360p 토막 3개+시트 ≈ 48초·2MB(통째 300MB 대신). 유튜브가 자막을 429 로 자주 막아 자막은 따로·재시도 3회·동시 2개. 토막 상한 120초·멈춤 40초(yt_fetch).
- gemini_server: 클립 2개×모델 2개 9.9초 · 손태영 3클립×5모델 12.5초. 서버에 없는 모델(gemini-2.5-flash)은 404 로 표시되고 대체 모델로 간다. 글 1회 요청은 SSH·기동 고정비가 커서(실측 6.5~20초 벽시계, 모델 자체 2~4초) 로컬 풀(4~9초)이 빠르다 — 묶음일 때 서버.
- thumb: 잇썸 54초(a_seg 재사용) · 재미썸 2분 44초(틀 합성 한 번 포함). checks: 판당 2.5~3분(거의 check_seams).
- 얼굴 판정 기준 = `thumb.py` FACE_MIN_FRAC **0.20**(10-18 실측: 바탕화면 15판 첫 프레임 0.28~1.0 통과, 옛 장윤정 재미썸 전신 0.12 반려) · 가운데 60%. 기존 완성본(연예인 얼굴로 고친 판)은 T1 통과. 기준을 바꾸면 thumb.py 상수 한 곳만.

## 1차 실전 수리(10-18 손태영 162분 · 한혜진 169분 · 김가연 — 사장님 "퀄리티는 그대로, 시간부터 줄여라")
시간이 간 곳(stage_log 실측): screen 648초+1639초(후보 1개 yt-dlp 시간초과가 단계를 죽임, 두 번) · 원본 통째 받기 813초 · 제품 받기 332초(자막 429 우회)
· asr 215초(flash-latest 177~304초/요청) · 렌더 재시도 12회(문장 자르기·문장부호 쉼·컷 넘침) · checks 70~350초 · thumb 16~175초.
뿌리 수리(주인 한 곳, 시험 `tests/test_calcopy_hybrid_fixes.py` 34개):
- **받기** `engine/yt_fetch.py`: 구간은 HLS 먼저 + **진행 없음 감시**(STALL_SEC 동안 파일이 안 자라면 그 프로세스만 끊고 다음 형식) · 자막은 영상과 **다른 호출**(429 여도 영상은 성공) · 키워드 적중 NFC·띄어쓰기 무시(맥 업로드 제목 '진생 로얄' 거짓 ×). screen 은 후보 하나가 죽어도 행에 사유를 적고 **screen.json 을 항상 쓴다**(토막 상한 300→120초·멈춤 40초면 그 후보 나머지 토막 생략). material_auto.section 도 같은 감시.
  실측: 360p 토막 6초 6.1초 · 자막 없음도 멈춤 없음 4.0초 · HLS 1080 구간 10초(+패드 2) 20.2초 13MB.
- **서버 ASR** `engine/gemini_server.py`: 모델 = 측정으로 고른 `gemini-3-flash-preview`·`gemini-3.5-flash`(둘 다 2~5초), 요청 상한 45초(http_options), 실패(429 끝까지·시간초과·404)면 **대체 모델**(flash-latest → 3.5-flash-lite)로 작업마다 성공 모델 2개를 채운다. jobs[i].cross_ok 가 거짓이면 checks·run 이 '교차 확인 모자람'으로 적는다 — 1모델을 교차로 포장하지 않는다. 실측 손태영 3클립×5모델 15회 12.5초(옛 3클립 2모델 215초). shim `hybrid/gemini_server.py` 는 스크립트로도 돈다.
- **나레 시각** `engine/narr_align.py`: Typecast **타임스탬프 엔드포인트**(추가 과금 없음)로 글자 시각을 받아 사이드카(`narr_full.mp3.tts.json`, 열쇠 = md5(글|목소리|배속|모델) — 줄 tts 를 고치면 다시 합성, 옛 mp3 는 유료 재합성 없이 그대로). 잇썸 문장 경계·재미썸 문장부호 자리·끝 문장 시작을 글자 시각으로 정한다(소리 짐작 없음). align 없는 옛 합성본만 여러 문턱 틈(−40/−32/−26dB, 얕은 틈 가산) 짝짓기로 어림하고, 쉼 안 쉰 마침표는 그 자리에 쉼을 **새로 넣는다**(tts_pause.shape 길이 0 틈 허용).
  증명(손태영): 옛 합성본 어림 = 손 값 ±0.019초(8/8) · 끝 문장 시작 21.1→19.2초(rate_last 14.3→7.7) / 새 TTS align = 문장부호 8/8 틈 정중앙(0.000), 잇썸 H|B1 경계 align 3.84초 vs 틈 어림 4.73초 — 서버 받아쓰기로 3.84~4.75 가 '저도'(B1 첫 낱말) 확인. Typecast 동시 합성 상한 2(TTS_CONCURRENCY, 프로세스 사이도 슬롯 잠금).
- **컷 길이는 계획에서**: 잇썸 plan 이 어림 over 면 멈추고 ×1.15 안이면 `[빠듯]` 경고(손태영 새 TTS 로 B2 2.147>1.99 넘친 컷이 바로 그 경고 컷). 재미썸 재료 B/A/F1 에 `max` 를 적으면 timeline 이 계획·렌더 둘 다 잡는다.
- **checks**: B13 은 같은 원음 구간 밑 A 컷끼리 제외(orig_spans) · 받아쓰기 창 앞뒤 0.15초 여유 · 같은 완성본(MD5)·구간·모델이면 `work/asr_cache.json` 재사용 · B4 최단 컷 1프레임·B17 반올림 허용 오차 · 이름 받아쓰기는 사전 `heard_ok`(연음 '한예진') 허용.
- **썸네일** `thumb.py`: 눈 뜸 지표(눈 패치 어두운 픽셀 비율 ≥0.26, 랜드마크만으로) 가산·감은 눈 −3 → 손태영 자동 선택이 손 선택과 같아짐(잇썸 6.15초·재미썸 1.8초, 전엔 2.55초 눈 반감·7.05초 입 가림). 대본 `thumb{"at":초}` 로 고정, `thumb{"keep":true}` 또는 `final.jpg.manual` 이 있으면 덮어쓰지 않는다. 배경 포스터의 작은 얼굴(가장 큰 얼굴의 45% 미만)은 세지 않는다.
- **이름**: 시험 문장 조사 이/가(ND.josa) · 표기 이중 삽입 금지(ND.apply — '씨 씨가') · 사전 갱신·stage_log 는 파일 잠금(`engine/filelock.py`) 아래 읽기-수정-쓰기.
- 남은 위험: 손으로 입을 가린 프레임은 랜드마크 지표로 못 가른다(입 폭·입술 붉은기·피부 비율 전부 겹침 — 실측) → 눈 뜸 + 정면성으로만 밀어낸다. 서버 3.5-flash 는 풀 일부 키가 429(9키 중) — 대체 모델이 채운다. 재미썸 align 경로는 손태영 1편으로만 증명.

## 규칙(사장님)
- 썸네일은 무조건 연예인(10-18): T1(0초·H 구간 얼굴) × 면 반려 — 제품 컷으로 시작하는 옛 판은 걸린다(10-18 고친 뒤 바탕화면 15판 전부 ○).
- 제미나이는 서버 풀로 최대한(10-18): 받아쓰기 모델 2개 교차 기본, 키 값은 PC 로 안 온다.
- 소재·결과물은 C 작업 폴더, 완성본은 바탕화면 `칼카피영상/얜샷템/하이브리드/` — deliver 가 MD5 대조.
- 10-18 뿌리 수리로 서버 창구·이름 사전·단계 장부의 **주인은 `tools/calcopy/engine/`**(hybrid 는 부르기만). 요약 `tools/calcopy/최적화_가이드.md`, 설계 `docs/superpowers/specs/2026-10-18-칼카피_제작자동화-design.md`.
