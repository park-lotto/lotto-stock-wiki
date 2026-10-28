# AI 장면 생성(Veo) — 없는 장면을 소스 프레임 베이스로 4초 만들기 (설계)

**날짜** 2026-09-22 · **트랙** `AI장면생성` · **상태** 사장님 검토 대기
**사장님 결정(2026-09-22)**: 우선 관리자만(고객은 나중) · 모든 칸에 버튼 · 훅은 임팩트 있게 가능 · 서비스 계정 키는 Claude가 만들어 서버에 넣는다.
**전제(사장님)**: 장면을 처음부터 새로 만들지 않는다 — **영상 소스에서 베이스(프레임)를 가져와 형태는 유지하고 동작만 자연스럽게**.

## 1. 실측 근거
- 건축 제작소(`Desktop\AI Shorts\engine\server.py:620~`)가 Vertex `veo-3.1-lite-generate-001`로 시작 이미지 보간을 이미 돌린다. 720p $0.05/초 → 4초 ≈ 300원. 무료 크레딧 ₩378,113(85일).
- 스파이크(2026-09-22 20:11, job `bte60cb14b7d` s0@1.0s 프레임): 피사체·색·구도 유지, 아기 팔·문어 다리만 미세 동작. 41초, 720x1280, 4.0초. **시작 프레임의 원본 자막이 첫 1초에 그대로 나온다** → 베이스 프레임은 자막 없는 것을 써야 한다.
- 3단계는 비트마다 `fit≤2`("이 문장에 맞는 영상이 부족")를 이미 매긴다(라이브 1,500 job에 1,782칸). 이게 "없는 장면"의 신호.
- 비트에 b-roll을 얹는 경로(장면 자산 `scene_assets` + `beat["cutaway"]` → `_render_mix` overlay → 청소 → 캡컷)가 라이브에 있다. 수동 지정 API `POST /api/produce/mix/{job}/cutaway` 존재.
- 서버에는 Vertex 인증이 없다(ADC·서비스계정 없음). `google-genai 2.7.0`은 설치돼 있다.

## 2. 목표 / 비목표
**목표**
- 3단계 편집안의 **모든 칸**에 「✨ AI 장면(4초)」 버튼. 훅 칸에는 「⚡ 임팩트」 선택 추가.
- 누르면 그 비트의 **현재 재료 프레임을 베이스**로 Veo가 4초(비트가 길면 6·8초) 클립을 만들고, 장면 자산으로 저장해 그 비트의 컷어웨이로 붙인다. 렌더·청소·캡컷은 기존 경로 그대로.
- 관리자 스위치 `ai_scene_enabled`(""/admin/목록/1, 기본 `admin`). 고객 과금 없음(1차).
**비목표**
- 텍스트→영상(프롬프트만) 생성. 베이스 프레임 없이는 안 만든다.
- 고객 크레딧 과금·단가 — 사장님 품질 판정 뒤.
- 자동 생성(fit≤2 자동) — 버튼만.

## 3. 흐름
```
[3단계 카드] ✨ AI 장면 ─POST /api/produce/mix/{job}/ai_scene {beat_idx, style}─▶ job_queue "ai_scene"
워커 run_ai_scene(job_id, beat_idx, style):
  1) 베이스 프레임: clean_base 있으면 청소본의 그 비트 첫 컷(time_in_clean) 프레임,
     없으면 primary 재료 start+0.2s 원본 프레임. 720x1280 크롭(9:16).
  2) 프롬프트 = 템플릿(형태·색·구도 유지, 새 물체·사람·글자 금지) + 동작 지시(narration을 Gemini flash로
     영어 한 줄 요약: "what natural motion fits this line") + style(natural: 미세 동작·느린 푸시인 /
     impact: 빠른 푸시인·손동작 강조·화면 흔들림 약간).
  3) Veo: image=베이스, 9:16, duration = 4 | 6 | 8 (비트 실길이 ≤4→4, ≤6→6, 그 외 8), audio 없음.
  4) 저장: _SCENE_ASSETS_DIR/veo_{job}_{beat}_{ts}.mp4 + 포스터 → store.add_scene_asset(
        asset_type="clip", render_mode="cutaway", source_kind="veo", source_ref=f"{job}:{beat}:{style}",
        title=f"AI 장면 · {narration[:20]}", scene_desc=narration, duration)
  5) beat["cutaway"]={"asset_id", "match_type":"ai"} + beat["ai_scene"]={"state":"done","asset_id","style","sec"}
     → _save_render_inputs(edit_plan). 실패 시 beat["ai_scene"]={"state":"failed","error"}.
[카드] 진행 중엔 ⏳(2초 폴링: GET /api/mix/status 의 beats[i].ai_scene), 끝나면 renderSceneCutaway가 포스터+「AI 장면 · 자연/임팩트」 배지, 「이 짤 빼기」로 제거(기존).
```
- 청소본 정본(clean_base)과의 관계: 컷어웨이는 `_render_mix`에서 재료 위에 얹히므로 4단계 전에 만들면 합성본이 통째로 청소된다(원본 프레임의 글자도 지워짐). 4단계 뒤에 만들면 베이스가 청소본 프레임이라 글자가 없고, 정본 재배치 렌더에서도 컷어웨이는 그대로 얹힌다(재청소 0). `coverage`는 재료만 보므로 컷어웨이 변경은 재청소를 일으키지 않는다 — **의도된 것**(AI 클립은 글자 없는 프레임에서 나온다).
- 임팩트(훅)는 프롬프트만 다르다. 모델·길이·비용 같음.

## 4. 구성요소
| 단위 | 하는 일 | 파일 |
|---|---|---|
| `ai_scene.py`(신규) | `base_frame(job, work, beat) -> png` · `build_prompt(beat, style, translate) -> str` · `pick_seconds(dur) -> 4|6|8` · `generate(png, prompt, sec) -> mp4`(Vertex 호출, 폴링, 실패 예외) · `run_ai_scene(job_id, beat_idx, style, db_path, work_root)` | 신규 |
| `config.py` | `GCP_PROJECT`, `GCP_LOCATION`(us-central1), `GOOGLE_APPLICATION_CREDENTIALS`는 SDK가 env로 읽음 | 수정 |
| `worker.py` | `"ai_scene"` 태스크 등록 | 수정 |
| `app.py` | `POST /api/produce/mix/{job}/ai_scene`(스위치·소유·beat 검증·중복 방지 `task_is_alive`) · 설정 키 `ai_scene_enabled` 등록 · `/api/mix/status`가 `beats[].ai_scene`·`cutaway` 포함(이미 edit_plan을 주므로 확인만) | 수정 |
| `produce.html` | 카드에 버튼(스위치 켜진 계정만 표시: status 응답의 `ai_scene_enabled`), 폴링, 배지 | 수정 |
| 서버 인증 | 서비스 계정 `shorts-veo@project-74eaf695-8229-44a1-876` (roles/aiplatform.user) 키 → `/home/ubuntu/keys/veo-sa.json`, `/etc/shopping-shorts.env`에 `GOOGLE_APPLICATION_CREDENTIALS`·`GCP_PROJECT`·`GCP_LOCATION` | 운영 |

**두 번 정하지 않는다**: 베이스 프레임 자리는 `ai_scene.base_frame` 하나(청소본 우선). 컷어웨이 붙이기는 기존 `/cutaway` 로직과 같은 필드(`beat["cutaway"]`)만 쓴다.

## 5. 오류·한계
- Vertex 실패/429 → beat.ai_scene.state=failed + 원문 앞 120자, 카드에 표시, 다시 누르면 재시도. 과금 없음(1차).
- 생성 시간 40~120초 — 폴링으로 보여준다. 워커 슬롯을 그 시간 점유(고객 렌더와 같은 큐). 1차는 감수, 몰리면 별도 큐.
- Veo가 글자를 만들 수 있다(건축 실측) → 프롬프트에 금지 + 베이스에 글자 없게. 그래도 나오면 사장님이 「이 짤 빼기」.
- 4초보다 긴 비트: 6·8초까지 생성, 그 이상은 컷어웨이가 앞부분만 덮고 나머지는 원래 재료(기존 overlay enable 구간 동작).

## 6. 검증
1. 단위: `pick_seconds`·`build_prompt`(금지문 포함·style 분기)·`base_frame`(청소본 우선) — Vertex는 monkeypatch.
2. 로컬 실렌더: 사본 job에서 버튼 흐름을 API로 호출(Vertex 실호출 1회, 300원) → 자산 생성·cutaway 지정·렌더(오버레이 구간 확인, 프레임 눈)·캡컷 조각 포함.
3. 서버: SA 키 배치 후 관리자 job에서 직접 버튼 → 생성 → 렌더 → 눈 확인(0순위-A1). 고객 노출은 사장님 판정 뒤 `1`.
