"""믹스 job 백그라운드 오케스트레이션(설계 §2·§5).

run_mix_job: 다운로드→대본추출(병렬)→EDL생성→TTS까지 진행하고 ready_for_review로.
run_render: 사용자가 확인 후 최종 ffmpeg 렌더 → done.
각 단계에서 mix_jobs.status를 갱신하고, 예외는 status='failed'+error로 잡는다.
"""
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from shopping_shorts.store import Store
from shopping_shorts.media_download import download_any
from shopping_shorts.script_extract import extract_script
from shopping_shorts.edit_plan import build_edit_plan
from shopping_shorts import tts
from shopping_shorts import audio_post
from shopping_shorts.video_assemble import assemble
from shopping_shorts.motion_assets import resolve_layers, DEFAULT_ASSETS_DIR

# 모션 자산 폴더(테스트가 monkeypatch로 교체 가능하도록 모듈 상수로 노출)
MOTION_ASSETS_DIR = DEFAULT_ASSETS_DIR
from shopping_shorts.vmake_client import remove_subtitles
from shopping_shorts.narration_naturalize import naturalize


def _source_video_id(i):
    return f"s{i}"


def _voice_params(voice):
    """job의 voice 스냅샷(dict|None) → (voice_id, voice_settings, speed, extra_tempo,
    silence_trim, naturalize_profile). voice 없으면 전부 기본값(config 기본 성우,
    속도 1.0, 무음삭제 off, naturalize_profile None → naturalize()가 자체 기본값 사용)."""
    v = voice or {}
    speed = v.get("speed", 1.0)
    extra_tempo = speed / 1.2 if speed > 1.2 else 1.0  # 1.2 초과분만 atempo로
    return (v.get("voice_id"), v.get("settings"), speed, extra_tempo,
            v.get("silence_trim", "off"), v.get("naturalize_profile"))


def _synthesize_beats(beats, tts_dir, *, voice_id, voice_settings, speed,
                      extra_tempo, trim, profile):
    """비트별로 naturalize→TTS(N-best·연속성)→후처리. beat['tts_path']를 채운다.
    연속성(previous_text/next_text)은 인접 비트의 '원문'(naturalize 전) narration을 쓴다
    — naturalize된 텍스트(오디오 태그·추임새 포함)를 연속성으로 넘기면 ElevenLabs가
    태그를 발화 텍스트로 오인할 수 있어서다."""
    tts_dir = Path(tts_dir)
    tts_dir.mkdir(parents=True, exist_ok=True)
    prof = profile or {}
    n_best = prof.get("n_best", 1)
    seed = prof.get("seed")
    total = len(beats)
    for i, beat in enumerate(beats):
        natural = naturalize(beat["narration"], prof, beat_role=beat.get("role"),
                             beat_index=i, beat_total=total)
        prev_t = beats[i - 1]["narration"] if i > 0 else None
        next_t = beats[i + 1]["narration"] if i < total - 1 else None
        out = tts_dir / f"beat_{beat['beat_idx']}.mp3"
        tts.synthesize_best(natural, str(out), n=n_best, base_seed=seed,
                            voice_id=voice_id, voice_settings=voice_settings, speed=speed,
                            model_id="eleven_v3", previous_text=prev_t, next_text=next_t)
        audio_post.post_process(str(out), str(out), tempo=extra_tempo, silence_trim=trim)
        beat["tts_path"] = str(out)


def _prepare_sources(urls, work):
    """소스 URL들을 플랫폼 무관하게 다운로드 → ({video_id: mp4경로}, {video_id: caption}).
    caption은 인스타 소스만 채워짐(download_any가 (path, caption) 튜플 반환) — 유튜브/틱톡은
    빈 문자열이라 extract_script가 영상 재전사로 채운다."""
    video_paths = {}
    captions = {}
    for i, url in enumerate(urls):
        vid = _source_video_id(i)
        d = Path(work) / vid
        d.mkdir(parents=True, exist_ok=True)
        path, caption = download_any(url, str(d))
        video_paths[vid] = path
        captions[vid] = caption
    return video_paths, captions


def run_mix_job(job_id, db_path, work_root):
    """다운로드→추출→EDL→TTS. 완료 시 status='ready_for_review'."""
    store = Store(db_path)
    job = store.get_mix_job(job_id)
    if not job:
        return
    work = Path(work_root) / job_id
    work.mkdir(parents=True, exist_ok=True)
    try:
        # 1) 다운로드 — 사용자가 붙여넣은 URL은 플랫폼별 페이지/공유 주소라 그대로
        # download_video 하면 영상이 아니라 HTML을 받아 Gemini가 state=FAILED로
        # 거부하는 경우가 있다(2026-07-12 라이브 실측, 인스타그램). 이제
        # media_download.download_any가 플랫폼별로(인스타=Apify로 CDN videoUrl
        # 해석 후 다운로드, 유튜브/틱톡=yt-dlp) 알아서 처리한다.
        store.update_mix_job(job_id, status="downloading")
        # video_id -> mp4 path, video_id -> caption(인스타만 채워짐, 유튜브/틱톡은 "").
        # extract_script가 caption을 힌트로 쓰고 없어도 영상 재전사로 동작 — .get(vid, "")로 안전 기본값.
        video_paths, captions = _prepare_sources(job["urls"], work)

        # 2) 대본 추출(병렬)
        store.update_mix_job(job_id, status="extracting")
        def _extract(item):
            vid, path = item
            r = extract_script(path, vid, caption=captions.get(vid, ""))
            r["video_id"] = vid
            return vid, r
        with ThreadPoolExecutor(max_workers=max(1, len(video_paths))) as ex:
            extracts = dict(ex.map(_extract, video_paths.items()))
        store.update_mix_job(job_id, extract=extracts)

        # 3~4) 통합 EDL 생성 + 비트별 TTS (video_type=None → 자동 유형 감지)
        # given_script이 있으면(영상제작 2단계) 나레이션을 새로 쓰지 않고 그 대본으로 매칭.
        source_scripts = list(extracts.values())
        _plan_and_tts(store, job_id, source_scripts, job["target_seconds"],
                      job["structure"], None, work, given_script=job.get("given_script"),
                      voice=job.get("voice"))
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        store.update_mix_job(job_id, status="failed", error=str(e))


def _plan_and_tts(store, job_id, source_scripts, target_seconds, structure, video_type, work,
                  given_script=None, voice=None):
    """EDL 생성(3) + 비트별 TTS(4) → edit_plan 저장 + ready_for_review.
    run_mix_job(자동판별, video_type=None)과 retype_mix_job(사용자 선택 유형)이 공유.
    given_script: 있으면 확정 대본을 그대로 비트로 쪼개 영상만 매칭(영상제작 2단계).
    voice: job의 voice 스냅샷(선택된 보이스 프리셋) — 있으면 비트별 TTS에 적용."""
    # 3) 통합 EDL
    store.update_mix_job(job_id, status="planning")
    plan = build_edit_plan(source_scripts, target_seconds, structure=structure,
                           video_type=video_type, given_script=given_script)
    # 빈 EDL(추출 전량 실패 또는 파이프라인 중간 전용풀 소진)을 ready_for_review로
    # 오보고하지 않는다 — 성공처럼 보이는 빈 리뷰화면 대신 즉시 실패로 정상 종료
    # (2026-07-12 최종 전체리뷰 Important).
    if not plan["beats"]:
        raise RuntimeError("EDL 비어있음 — 대본 추출 실패 또는 Gemini 키 소진으로 편집안을 만들지 못함")

    # 4) 비트별 TTS (naturalize + N-best + 연속성 + 프리셋 후처리)
    store.update_mix_job(job_id, status="tts")
    voice_id, vs, speed, extra_tempo, trim, profile = _voice_params(voice)
    _synthesize_beats(plan["beats"], work / "tts", voice_id=voice_id, voice_settings=vs,
                      speed=speed, extra_tempo=extra_tempo, trim=trim, profile=profile)

    store.update_mix_job(job_id, edit_plan=plan, status="ready_for_review")


def retype_mix_job(job_id, video_type, db_path, work_root):
    """사용자가 감지된 영상 유형을 바꾸면, 저장된 extract로 EDL+TTS만 재생성한다
    (재다운로드·재추출 없음 — 방식3의 '확인/변경' 경로, 설계 §3-6)."""
    store = Store(db_path)
    job = store.get_mix_job(job_id)
    if not job or not job.get("extract"):
        return  # 추출 캐시 없으면 재생성 불가
    work = Path(work_root) / job_id
    try:
        source_scripts = list(job["extract"].values())
        _plan_and_tts(store, job_id, source_scripts, job["target_seconds"],
                      job["structure"], video_type, work, given_script=job.get("given_script"),
                      voice=job.get("voice"))
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        store.update_mix_job(job_id, status="failed", error=str(e))


def _resolve_sources(job, work):
    """다운로드된 소스 mp4 경로 맵 {video_id: path}. 없으면 예외."""
    source_video_paths = {}
    for i in range(len(job["urls"])):
        vid = _source_video_id(i)
        mp4 = next((work / vid).glob("*.mp4"), None)
        if mp4 is None:
            raise RuntimeError(f"소스 영상 없음: {vid} (다운로드 디렉터리에 mp4 없음)")
        source_video_paths[vid] = str(mp4)
    return source_video_paths


def _vmake_key(store):
    """등록된 VMake 개인키(DB settings). 없으면 빈 문자열."""
    return store.get_setting("vmake_api_key", "") or ""


def run_render(job_id, db_path, work_root):
    """확인된 EDL을 최종 mp4로 렌더. subtitle_removal이 켜져 있으면 믹스 후
    VMake로 원본 자막을 제거하고 그 위에 우리 자막을 굽는다. 완료 시 status='done'."""
    store = Store(db_path)
    job = store.get_mix_job(job_id)
    if not job or not job.get("edit_plan"):
        return
    work = Path(work_root) / job_id
    work.mkdir(parents=True, exist_ok=True)
    try:
        store.update_mix_job(job_id, status="rendering")
        plan = job["edit_plan"]
        tts_paths = {b["beat_idx"]: b["tts_path"] for b in plan["beats"] if b.get("tts_path")}
        source_video_paths = _resolve_sources(job, work)
        out_path = work / "final.mp4"

        clean_fn = None
        if job.get("subtitle_removal"):
            key = _vmake_key(store)
            if not key:
                raise RuntimeError("자막 제거가 켜져 있으나 VMake 개인키가 등록되지 않았습니다")
            def clean_fn(mix_raw):                        # noqa: E306
                store.update_mix_job(job_id, status="removing_subtitles")
                clean_path = str(work / "clean.mp4")
                out = remove_subtitles(mix_raw, key, out_path=clean_path)
                store.update_mix_job(job_id, clean_video_path=out)
                return out

        # deco의 BGM 파일(업로드 시 work/{file}에 저장)을 절대경로로 해석해 넘긴다.
        deco = job.get("deco") or {}
        bgm = deco.get("bgm") or {}
        if bgm.get("file"):
            bp = work / bgm["file"]
            if bp.exists():
                deco = {**deco, "bgm": {**bgm, "_abspath": str(bp)}}
        ov = deco.get("overlay") or {}
        if ov.get("file"):
            op = work / ov["file"]
            if op.exists():
                deco = {**deco, "overlay": {**ov, "_abspath": str(op)}}
        # 모션 레이어(전환·스티커): asset_id → 실경로·기본배치 해석
        motion = deco.get("motion") or {}
        if motion.get("layers"):
            resolved = resolve_layers(motion["layers"], MOTION_ASSETS_DIR)
            deco = {**deco, "motion": {**motion, "layers": resolved}}
        assemble(plan, tts_paths, source_video_paths, str(out_path), clean_fn=clean_fn,
                 headcopy=job.get("headcopy"), caption_style=job.get("caption_style"),
                 deco=deco)
        store.update_mix_job(job_id, status="done", video_path=str(out_path))
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        store.update_mix_job(job_id, status="failed", error=str(e))


def resynth_tts_job(job_id, db_path, work_root):
    """기존 edit_plan은 그대로 두고, job의 voice 설정으로 비트별 TTS만 다시 생성한다
    (영상제작 4단계 '이 대본으로 다시 듣기'·프리셋 변경). 재다운로드·재매칭 없음."""
    store = Store(db_path)
    job = store.get_mix_job(job_id)
    if not job or not job.get("edit_plan"):
        return
    plan = job["edit_plan"]
    work = Path(work_root) / job_id
    store.update_mix_job(job_id, status="tts")
    voice_id, vs, speed, extra_tempo, trim, profile = _voice_params(job.get("voice"))
    try:
        _synthesize_beats(plan["beats"], work / "tts", voice_id=voice_id, voice_settings=vs,
                          speed=speed, extra_tempo=extra_tempo, trim=trim, profile=profile)
        store.update_mix_job(job_id, edit_plan=plan, status="ready_for_review")
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        store.update_mix_job(job_id, status="failed", error=str(e))
