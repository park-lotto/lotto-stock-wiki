---
name: project
description: TTS 연음/발음 어색함 근본해결 — 전역 발음사전+관리자 작업대. 라이브 배포됨
metadata: 
  node_type: memory
  type: project
  originSessionId: 3a4e4fe8-65b3-4ceb-9dd8-a578fbdee899
  modified: 2026-07-22T04:40:08.904Z
---

쇼핑쇼츠 TTS "대본 따라 들쭉날쭉" 3갈래 수정, 트랙 보이스에서 SDD 7태스크로 라이브 배포(2026-07-22, 서버 bc42ba542 active 확인).

- **① 볼륨 오르락내리락 = loudnorm 부재**(근본): `audio_post.post_process(loudnorm=True)` → EBU `loudnorm=I=-16:TP=-1.5:LRA=11` 마지막 필터. `synthesize_line`에서 `loudnorm=bool(ELEVENLABS_API_KEY)` — 무음 mock엔 안 검(트랩 회피 [[reference_local_tts_silent_mock_trap]]).
- **② 발음 오독 = best-of-2**(근본 아님, 확률저감): `synthesize_line`에서 GROQ 키 있을 때만 n을 최소 2로 floor-raise(랭커 실동작 조건). 명시 n_best=3 프리셋 보존. 키 없으면 낭비 차단. **연음엔 무의미**(ASR이 못 봄).
- **③ 연음/발음 어색 = 전역 발음사전**(진짜 근본): `{어색구절: 재표기}` 하나 등록하면 모든 보이스·모든 렌더에 영구 적용. **best-of-2 두더지잡기와 정반대 = 한번 잡으면 안 돌아옴**(끝없는 루프→유한). 단 새 문장은 여전히 어색할 수 있음(0이 아님).

**핵심 설계 결정**:
- **전역 사전은 서버 DB(settings kv, 키 `"global_pron_dict"`)에 저장 — git 파일 금지.** 서버가 git-tracked 파일에 쓰면 `git status` 더러워져 auto_deploy pull이 조용히 스킵됨(사고 #9 [[reference_deploy_truth_branch_ssh]]). DB는 배포 pull에 안 지워짐.
- **엔진 lever는 이미 있었음**: `narration_naturalize._pronunciation`(dict 긴키먼저 replace, 구절키 지원). `pron_corrections.overlay(profile, global_dict)`가 전역을 `profile["pronunciation"]["dict"]`에 병합(per-preset 우선). `synthesize_line`(렌더·작업대 공유 choke)에 배선.
- **미묘한 seam(whole-branch 리뷰가 잡음)**: synthesize_line이 overlay 후 naturalize가 `merge_profile`을 재실행하는데, 얕은 `.update`라 overlay된 dict 생존. 재귀병합이었으면 기능 통째로 죽었을 것.
- **작업대**(`voice_tune.html`, `/voice_tune` 관리자게이트): 어색문장 붙여넣기→AI(Gemini `edit_plan._vault_call`) 교정제안(환각필터: phrase in text)→손질→원본vs교정 A/B(`plApplyFix`=split/join=render의 replace와 동일)→전역저장. produce 보이스패널은 `<details>` 접기.

**SDD 교훈**: 리뷰 루프가 잡은 것 — ①resynth_tts_job/resynth_one_beat도 tts_path를 최종렌더가 skip_existing 재사용 → 발음교정 배선 필요(Task2 Important). ②캡처UI id 하이픈(`pl-text`) vs JS bare-global 언더스코어(`pl_text`) 불일치로 전 함수 ReferenceError(내 브리프발 버그) → 인덱스핸들러+esc()로 수정. **UI는 라이브 브라우저 그라운딩이 관리자 로그인 필요라 배포후 사장님 확인 필요**(정적검증만 됨).

파일: `shopping_shorts/pron_corrections.py`(신규)·`mix_pipeline.py`·`app.py`(/api/pron/*)·`static/voice_tune.html`·`static/produce.html`. 설계: `docs/superpowers/specs/2026-07-22-발음교정-전역사전-작업대-design.md`.
