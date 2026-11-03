"""Canonical public runner membership and exact installed file identity.

The builder and runner use this same list. Keep private reference helpers out.
"""
import hashlib
from pathlib import Path

STUDENT_FILES = frozenset({
    "original_import.py", "local_resolver.py", "integration_contract.py", "http_contract.py",
    "README.md",
    "focus_kernel.py",     # generated canonical local validation, no server catalogue
    "render_kernel.py",    # generated local frame geometry
    "local_photo_plan.py", # generated source-bound OCR viewport review
    "local_compute_identity.py", # immutable implementation byte digests
    "info3d_engine_pin.py", "file_witness.py",
    "repair_transition.py", "repair_candidates.py",
    "repair_state_stage.py",
    "redub_kernel.py",
    "person_kernel.py",
    "local_person_plan.py",
    "local_redub_plan.py", "local_redub_delivery.py", "redub_export_kernel.py",
    "local_shop_plan.py", "shop_kernel.py", "shop_export_kernel.py",
    "source_kernel.py", "source_state_kernel.py", "source_export_kernel.py",
    "local_source_context.py", "local_source_plan.py",
    "local_render_plan.py", # local frame-plan coordinator
    "local_focus.py",      # local evidence/receipt coordinator
    "runner_files.py",      # 배급 파일 목록과 전체 파일 일치 검증
    "local_paths.py",       # 실제 파일의 유니코드 표기와 입력 경로 일치
    "volcano_run.py",       # 실행기 본체
    "video_encoder.py",     # 영상 인코더 자리(@VENC@) 판정 — PC 마다 1초 시험 굽기 · GPU 실패 시 CPU 1회
    "onnx_providers.py",    # 렌더 안 AI(ACNet) 장치 판정 — 윈도우 DirectML 되면 GPU · PC 마다 1회 시험 · 실패 시 CPU 1회
    "volcano_drive.py",     # 구동기 (서버 지시를 따라가는 루프)
    "photo_fix.py",         # 사진 실사 검수 정지 한 줄 도우미(tools/build_photo_fix.py 가 서버 본문으로 만든다 · 2026-10-06)
    "agy_review_bridge.py",
    "agy_transport_client.py",
    "agy_transport_pc_env.py",
    "agy_transport_proc.py",
    "agy_transport_refusal.py",
    "agy_transport_codes.py",
    "agy_google.py",        # 구글 사진 후보 — 수강생 자기 agy(구독) 로 찾는다(2026-09-28 serper 자리)
    "jev_photo.py",         # 사진 앞단 거르기(TypeSafe Jev · 열쇠 있을 때만 · 실패면 안 거름) — 판정 한 벌(2026-10-23 · 팟캐스트 팩이 읽는다)
    "politics_legacy_upgrade.py", # 10-04 기준 갱신 지시 — 고친 엔진 파일은 그대로 두고 맞춘다(2026-10-05)
    "politics_baseline_core.py", # 정치 엔진 맞춤 판정 — 서버 맞춤 스크립트(runner_script.BASELINE)와 바이트까지 같다
    "politics_baseline_known.py", # 정치 엔진 맞춤 자료 — 서버 sync_spec 생성본(공식 지문 앞 64비트 · 공개 팩의 지문뿐)
    "ta_upgrade_local.py", # explicit code-only pinned job migration
    "response_receipts.py", # durable completed RPC delivery, no paid replay
    "runner_caller.py",     # 자동 설치가 공용 runner/ 도 함께 바꿔도 되는지(Z ②)
    "response_refs.py",    # 같은 검수 응답의 무손실 참조 복원
    "response_zip.py",     # negotiated gzip RPC integrity and size validation
    "response_inline_blobs.py",  # verified fresh evidence units before cache restoration
    "runtime_metrics.py",   # 작업 폴더별 누적 시간과 명시적으로 관측한 호출
    "film_caption.py",      # 단어 시각과 표시 문구를 분리한 한 줄 자막
    "film_continuity.py",   # 원본 시간표와 공유 카메라 경로
    "shorts_framing.py",    # 숏폼 AGY 피사체 영수증 → 확대 창·가로세로 가운데(사장님 결정 2026-10-07)
    "film_editor_legacy.py",  # 이야기 카드가 아닌 편집 작업(인물형 등)의 못박힌 엔진 — 바이트 고정(film_editor.run)
    "film_word_audio.py",   # 선택 원음 측정과 기존 접수 재개
    "film_tracks.py",       # 독립 화면·반응·효과음과 기존 음성 보존
    "longform_state.py",
    "longform_contract.py",
    "longform_editorial.py",  # 컷별 반복 자료·유사 구도 검수 증거
    "longform_photo.py",
    "longform_render.py",
    "longform_caption_motion.py",
    "longform_iris.py",
    "longform_graphic.py",
    "longform_groups.py",
    "longform_hyperframes.py",  # verified HyperFrames picture renderer
    "longform_texture.py",  # independent stepped texture motion
    "longform_native.py",  # Chrome/CDP PNG streaming capture
    "longform_object_glitch.py",
    "longform_fonts.py",
    "longform_engine.py",
    "longform_audio.py",
    "longform_source_audio.py",
    "longform_floor.py",  # 최소 구성(오드리 편 바닥) — 서버 src/longform/floor.py 와 바이트 같음
    "longform_external_voice.py",  # 작성자 외부 음성(제미나이 등) · 받아쓰기로 글자 시각
    "longform_gemini_voice.py",  # 제미나이 TTS(볼케이노킷) — 블록 음성을 만들어 외부 음성 길로
    "longform_timing.py",  # 문장 호흡 조정 뒤 화면·효과음·음악 시간 연결
    "longform_video.py",
    "longform_reframe.py",
    "longform_video_tools.py",
    "longform_video_treatment.py",
    "longform_source_revision.py",
    "longform_cut_review.py",
    "longform_media.py",
    "longform_montage.py",  # 실제 자료 다중 컷·전환
    "longform_shatter.py",  # 실제 앞 영상 파편과 연속 재생 뒤 영상
    "longform_ink.py",      # 잉크 전환 마스크
    "longform_tear.py",     # 종이 찢김 전환
    "longform_paper_reveal.py",  # 찢긴 종이 안쪽의 영상·사진 노출과 접힌 종이 모션
    "longform_transitions.py",  # 붓칠·빛 번짐 전환
    "longform_endcard.py",  # 움직이는 추천·출처 엔딩
    "longform_upload.py",   # 실제 사용 자산 크레딧·업로드 문구
    "film_editor.py",       # 확정 편집표와 프레임 구도로 실행하는 공용 영화 편집기
    "volcano_longform_review.py",  # 롱폼 자식의 현재 호스트 검수·대기 재개
    "focus_receipt.py", # exact focus evidence receipt reconstruction
    "subject_stage_pool.py", # CPU phases remain bounded while AGY waits
    "subject_focus.py",     # 실측 후보 선택과 프레임별 추적
    "subject_agy.py",       # 인물형 롱폼 피사체: AGY 판독 질문·답 검증·좌표 산수(로컬 추론 0)
    "subject_agy_run.py",   # 인물형 롱폼 피사체: 사본·AGY 전송·재개·관문
    "subject_sampled_recovery.py",  # Saved samples only; current local tracking with cache-only review
    "subject_decoder_recovery.py",  # Exact full-output local recovery; no new review dispatch
    "subject_decoder_identity.py",  # Content identity and verified legacy migration
    "subject_frame_clock.py",  # Explicit source PTS grid shared with final treatment
    "subject_frame_stream.py",  # 검수 표본 보존과 원본 프레임 순차 추적
    "subject_tracking_evidence.py",
    "source_motion.py",     # 선택/검수와 분리된 원본 움직임 계측
    "survey.py",            # 긴 영상 훑기 — 수강생 단계가 쓴다(volcano_tools 14곳)
    "vision.py",            # 제미나이 호출 — 수강생 단계가 쓴다(volcano_tools 12곳)
    "video_proxy_fit.py",   # 서버가 선언한 검수 용량 조정, 기존 영상·음성 보존
    "cardnews_design.py",   # 카드뉴스 — volcano_cardnews_steps 가 쓴다
    "cardnews_images.py",
    "cardnews_layout.py",
    "cardnews_publish.py",
    "cardnews_render.py",
    "cardnews_refspec.py",  # 레퍼런스 재기 — agy 판독 + 화소 재기(10-08)
    "cardnews_source.py",   # 원문 모으기·카드 쓰기 — 수강생 자기 agy(10-08)
    "cardnews_agyimage.py", # 카드 그림 — agy 그림 도구가 레퍼런스 참조로(10-08)
    "longform_agyimage.py", # 인물형 롱폼 그림 — 제작표 media.generate 를 학생 agy 그림 도구로(10-09 · cardnews_agyimage 를 쓴다)
    "longform_cutout.py",   # 인물형 롱폼 누끼 일감 prepare_cutouts(10-17 · 신고 #121) — nukki.py 를 쓴다
    "nukki.py",             # 사람 사진 누끼 한 자리(본인 Cloudflare 0순위 · 아니면 Replicate) — 인물형 롱폼·너이봤 공용(10-17)
})


def identity(directory):
    digest = hashlib.sha256(b'volcano-runner-files-v1\0')
    for name in sorted(STUDENT_FILES):
        body = (Path(directory) / name).read_bytes()
        digest.update(name.encode('utf-8') + b'\0')
        digest.update(hashlib.sha256(body).digest())
    return digest.hexdigest()[:12]
