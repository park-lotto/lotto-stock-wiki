# AI 장면 생성(Veo) — 없는 장면을 소스 프레임 베이스로 4~8초 (2026-09-23)

**트랙** `AI장면생성` · **스위치** `ai_scene_enabled`(값 없음=관리자만 · "1"=전체) · **상태** 코드·테스트·로컬 실호출 완료, **서버 인증 대기**
설계 `docs/superpowers/specs/2026-09-22-AI장면생성-Veo-design.md` · 플랜 `docs/superpowers/plans/2026-09-23-AI장면생성-Veo.md`

## 사장님 결정
우선 관리자만 · 모든 칸에 버튼(훅은 ⚡임팩트 추가) · 서비스 계정 키는 Claude가 만들어 서버에 · "장면을 새로 만들지 말고 소스 베이스로 형태 유지·동작만".

## 구조
- `shopping_shorts/ai_scene.py`: `pick_seconds`(4|6|8) · `pick_base_material`(제품만 컷 우선: scene_desc에 사람·아기·손 없음) ·
  `base_frame_path`(그 컷이 청소본에 있으면 청소본에서, 아니면 원본) · `motion_request`(**베이스 이미지를 보여주며** Gemini가 동작 3단계) ·
  `build_prompt`(첫 프레임 묘사+초 단위 사건+재질·조명+금지 목록) · `generate`(Veo 3.1 Lite, 9:16, 무음) · `run_ai_scene`(워커).
- 결과: 장면 자산(clip/cutaway/source_kind=veo) + `beat["cutaway"]={"asset_id","match_type":"ai"}` + `beat["ai_scene"]={state,...}`.
- API `POST /api/produce/mix/{job}/ai_scene {beat_idx, style}` · 화면: 3단계 카드 「✨ AI 장면 만들기」/「⚡ 임팩트로」, 2초 폴링, 배지 「AI 장면 · 자연/임팩트 4초」, 「이 짤 빼기」로 제거.
- 워커 태스크 `ai_scene` · config `GCP_PROJECT`/`GCP_LOCATION`.

## 실측(로컬, 이 PC ADC, 사장님 job 사본 bte60cb14b7d 훅·임팩트)
1차: 45초, 자산 151. **Gemini가 이미지를 안 보고** "뒤집으면 핑크" 지어냄 → Veo가 그대로 뒤집음. 워터마크를 본뜬 가짜 로고.
→ 고침: 동작 지시에 베이스 프레임 첨부(`_vault_call_image`), "보이는 것만·변형 금지", 제품만 컷은 청소본에서 뜨기.
2차: 58초, 자산 152. 속도선→손이 머리 누름→안정, 형태·색 유지. 남은 것: 원본 컷 베이스면 첫 0.5초 자막·가짜 글자(청소본 베이스면 감소).
스파이크 7편(09-22): `Desktop\AI장면_*.mp4` — 상황을 초 단위로 적어야 지시대로 나옴(E2·D2).

## ★막힌 것 — 서버 Vertex 인증
서비스 계정 `shorts-veo@project-74eaf695-8229-44a1-876.iam.gserviceaccount.com` 생성·`roles/aiplatform.user` 부여 완료.
**키 발급은 조직 정책(`iam.disableServiceAccountKeyCreation`, org 753122311363)으로 거부.** 정책 해제 권한(orgpolicy.policies.create) 없음.
선택지: ① 이 PC ADC 파일(`~/.config/gcloud/application_default_credentials.json`)을 서버로 복사(사장님 계정 토큰) ② 사장님이 콘솔에서 조직 정책 해제 후 키 발급.
서버엔 google-genai 2.7.0 있음. env: `GOOGLE_APPLICATION_CREDENTIALS`·`GCP_PROJECT`·`GCP_LOCATION`(`/etc/shopping-shorts.env`).

## ⏭ 다음
- [ ] 사장님 선택 → 서버 인증 배치 → `finish` → DEPLOY_NOW → 사장님 job에서 버튼 직접 → 생성 → 렌더 → 캡컷 확인(0순위-A1)
- [ ] 텍스트 잔존 대응(원본 베이스일 때): 4단계 뒤 사용 권장 안내 or 컷어웨이 자막제거
- [ ] 고객 전체는 사장님 판정 뒤 `ai_scene_enabled=1`
