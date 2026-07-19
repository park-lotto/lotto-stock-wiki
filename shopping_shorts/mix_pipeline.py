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
from shopping_shorts.scene_match import match_scene_assets
from shopping_shorts import tts
from shopping_shorts import audio_post
from shopping_shorts.video_assemble import assemble, _beat_timeline, _probe_duration
from shopping_shorts.motion_assets import resolve_layers, DEFAULT_ASSETS_DIR
from shopping_shorts.motion_packs import build_plan, load_packs
from shopping_shorts.vmake_client import remove_subtitles
from shopping_shorts.narration_naturalize import naturalize, merge_profile
from shopping_shorts import asr_check
from shopping_shorts import caption_sync

# 모션 자산 폴더(테스트가 monkeypatch로 교체 가능하도록 모듈 상수로 노출)
MOTION_ASSETS_DIR = DEFAULT_ASSETS_DIR


def _source_video_id(i):
    return f"s{i}"


def _voice_params(voice):
    """job의 voice 스냅샷(dict|None) → (voice_id, voice_settings, speed, extra_tempo,
    silence_trim, naturalize_profile, model_id). voice 없으면 전부 기본값(config 기본 성우,
    속도 1.0, 무음삭제 off, naturalize_profile None → naturalize()가 자체 기본값 사용).

    스냅샷은 /api/mix/voice가 프리셋에서 통째로 복사해 넣는다 — naturalize_profile·model_id가
    빠지면 튜닝 작업대에서 동결한 값이 렌더에 도달하지 못한다(2026-07-15 whole-branch 리뷰 S1/S8)."""
    v = voice or {}
    speed = v.get("speed", 1.0)
    extra_tempo = speed / 1.2 if speed > 1.2 else 1.0  # 1.2 초과분만 atempo로
    return (v.get("voice_id"), v.get("settings"), speed, extra_tempo,
            v.get("silence_trim", "off"), v.get("naturalize_profile"),
            v.get("model_id") or "eleven_v3")


def asr_ranker(path, text):
    """N-best take 랭커: Whisper 재전사 diff의 오독 점수(낮을수록 좋음).
    GROQ_API_KEY 미설정이면 transcribe가 None → 0(전부 동점 → 첫 take)으로 무해 폴백."""
    hyp = asr_check.transcribe(path)
    return asr_check.mismatch_score(asr_check.diff_words(text, hyp)) if hyp else 0


def synthesize_line(narration, out_path, *, voice=None, profile=None, beat_role=None,
                    beat_index=None, beat_total=None, previous_text=None, next_text=None,
                    ranker=asr_ranker):
    """한 줄을 naturalize→TTS(N-best·연속성)→후처리까지 합성하고 변환텍스트를 반환.

    **튜닝 작업대와 실제 렌더가 공유하는 단일 경로**다. 양쪽이 각자 파이프라인을 조립하면
    인자가 갈려 "작업대에서 들은 소리 ≠ 영상 소리"가 된다(2026-07-15 리뷰 S3/S4/S5/S6).
    새 호출부를 만들지 말고 이 함수를 쓸 것.

    profile 미지정 시 voice 스냅샷의 naturalize_profile을 쓴다. seed/n_best는 merge_profile을
    거친 값으로 읽어 텍스트와 오디오가 같은 기준을 보게 한다(S10)."""
    voice_id, settings, speed, extra_tempo, trim, prof_v, model_id = _voice_params(voice)
    prof = merge_profile(profile if profile is not None else prof_v)
    natural = naturalize(narration, prof, beat_role=beat_role,
                         beat_index=beat_index, beat_total=beat_total)
    tts.synthesize_best(natural, str(out_path), n=prof.get("n_best", 1),
                        base_seed=prof.get("seed"), ranker=ranker,
                        voice_id=voice_id, voice_settings=settings, speed=speed,
                        model_id=model_id, previous_text=previous_text, next_text=next_text)
    audio_post.post_process(str(out_path), str(out_path), tempo=extra_tempo, silence_trim=trim)
    return natural


def _synthesize_beats(beats, tts_dir, *, voice):
    """비트별로 synthesize_line 호출. beat['tts_path']를 채운다.
    연속성(previous_text/next_text)은 인접 비트의 '원문'(naturalize 전) narration을 쓴다
    — naturalize된 텍스트(오디오 태그·추임새 포함)를 연속성으로 넘기면 ElevenLabs가
    태그를 발화 텍스트로 오인할 수 있어서다."""
    tts_dir = Path(tts_dir)
    tts_dir.mkdir(parents=True, exist_ok=True)
    total = len(beats)
    for i, beat in enumerate(beats):
        out = tts_dir / f"beat_{beat['beat_idx']}.mp3"
        synthesize_line(
            beat["narration"], out, voice=voice, beat_role=beat.get("role"),
            beat_index=i, beat_total=total,
            previous_text=beats[i - 1]["narration"] if i > 0 else None,
            next_text=beats[i + 1]["narration"] if i < total - 1 else None,
        )
        beat["tts_path"] = str(out)
        # 자막 타이밍용: 실제 말한 워드 시각으로 구절 표시시간 계산(실패/키없음 → 미설정=폴백).
        beat["cap_durs"] = None
        words = asr_check.transcribe_words(str(out))
        if words:
            dur = _probe_duration(str(out))
            beat["cap_durs"] = caption_sync.phrase_durs_from_words(
                beat["narration"], words, dur)   # None일 수 있음 → 폴백


def _prepare_sources(urls, work):
    """소스 URL들을 플랫폼 무관하게 다운로드 → ({video_id: mp4경로}, {video_id: caption}, skipped).
    caption은 인스타 소스만 채워짐(download_any가 (path, caption) 튜플 반환) — 유튜브/틱톡은
    빈 문자열이라 extract_script가 영상 재전사로 채운다.

    ★소스별 예외격리(2026-07-19 실사고): 한 URL이 다운로드 안 되면 그 소스만 건너뛰고
    나머지로 계속한다 — 불량 URL 하나(렌즈 즐겨찾기로 샌 instagram.com/popular/{슬러그} 등)가
    배치 전체를 죽이던 걸 막는다. 근본차단은 lens_discover._is_watchable(입구), 여기는 백스톱.
    video_id는 인덱스 기준(s{i})이라 중간이 빠져도 나머지 매칭에 영향 없다(갭 허용).
    전부 실패(0개 생존)하면 RuntimeError. skipped=[(url, err), ...]."""
    video_paths = {}
    captions = {}
    skipped = []
    for i, url in enumerate(urls):
        vid = _source_video_id(i)
        d = Path(work) / vid
        d.mkdir(parents=True, exist_ok=True)
        try:
            path, caption = download_any(url, str(d))
        except Exception as e:  # noqa: BLE001 — 소스별 격리가 목적
            skipped.append((url, str(e)))
            print(f"_prepare_sources: 소스 스킵 — {url}: {e}", file=sys.stderr)
            continue
        video_paths[vid] = path
        captions[vid] = caption
    if not video_paths:
        raise RuntimeError(
            "소스 영상을 하나도 못 받았습니다 — 모든 URL 다운로드 실패:\n"
            + "\n".join(f"· {u}: {e}" for u, e in skipped))
    return video_paths, captions, skipped


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
        # 소스별 예외격리: 불량 URL은 스킵되고 최소 1개만 살면 계속(2026-07-19).
        video_paths, captions, skipped = _prepare_sources(job["urls"], work)
        if skipped:
            print(f"run_mix_job[{job_id}]: {len(skipped)}개 소스 스킵 "
                  f"(불량 URL) — {[u for u, _ in skipped]}", file=sys.stderr)

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
                      voice=job.get("voice"), customer_id=job.get("customer_id", 0))
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        store.update_mix_job(job_id, status="failed", error=str(e))


def _plan_and_tts(store, job_id, source_scripts, target_seconds, structure, video_type, work,
                  given_script=None, voice=None, customer_id=0):
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

    # 3.5) 장면 라이브러리 매칭 — 자산이 있을 때만(없으면 plan 무변경). match_scene_assets가
    # beat["cutaway"]={"asset_id":..,"score":..}를 심고, run_render이 같은 키를 읽어
    # asset_id→media_path로 해석한다(저장위치=읽기위치, seam은 mix_pipeline 배선 참고).
    assets = store.list_scene_assets(customer_id=customer_id, asset_type="clip")
    if assets:
        plan = match_scene_assets(plan, assets)

    # 4) 비트별 TTS (naturalize + N-best + 연속성 + 프리셋 후처리)
    store.update_mix_job(job_id, status="tts")
    _synthesize_beats(plan["beats"], work / "tts", voice=voice)

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
                      voice=job.get("voice"), customer_id=job.get("customer_id", 0))
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


def _apply_motion_pack(deco, caption_style, timeline, packs):
    """deco.motion.pack_id → 팩 정책으로 레이어·색감·자막효과·헤드카피 노출을 채운다.

    핵심: 레이어는 **저장하지 않고 렌더 시점에 만든다**(비트 경계는 TTS 실길이로 정해지므로).
    저장되는 건 pack_id뿐. 사용자가 직접 지정한 값(color_filter·caption effect)이 팩보다 우선한다.
    반환: (deco, caption_style) — 원본을 변형하지 않은 얕은 복사본.
    """
    motion = (deco or {}).get("motion") or {}
    pack_id = motion.get("pack_id")
    if not pack_id:
        return deco, caption_style
    pack = packs.get(pack_id)
    if not pack:
        print(f"[motion] 모르는 pack_id={pack_id!r} — 모션 없이 진행", file=sys.stderr)
        return deco, caption_style

    p = build_plan(pack, timeline)
    new_motion = {**motion, "layers": p["layers"] + list(motion.get("layers") or [])}
    if not motion.get("color_filter"):
        new_motion["color_filter"] = p["color_filter"]
    if p["headcopy_enable"]:
        new_motion["_headcopy_enable"] = p["headcopy_enable"]   # DB 저장 안 함(렌더 파생값)
    deco = {**deco, "motion": new_motion}

    if p["caption_effect"] and not (caption_style or {}).get("effect"):
        caption_style = {**(caption_style or {}), "effect": p["caption_effect"]}
    return deco, caption_style


def _resolve_cutaway_paths(store, plan, customer_id):
    """비트에 붙은 cutaway asset_id → media_path. 저장위치(match가 쓴 beat['cutaway'])
    = 읽기위치(여기). run_render와 run_preview 둘 다 이걸 써서 미리보기와 최종본이
    같은 컷어웨이를 보여준다(안 그러면 사장님이 유료 렌더 전에 확인 못 함)."""
    out = {}
    for beat in plan["beats"]:
        cut = beat.get("cutaway")
        if cut:
            asset = store.get_scene_asset(cut["asset_id"], customer_id=customer_id)
            if asset and asset.get("media_path"):
                out[beat["beat_idx"]] = asset["media_path"]
    return out


def _clean_one(item, key, work):
    """소스 하나를 VMake로 청소 → (video_id, 클린경로). ThreadPool 워커용(DB 미접근)."""
    vid, src = item
    out = str(Path(work) / f"clean_src_{vid}.mp4")
    return vid, remove_subtitles(src, key, out_path=out)


def _ensure_clean_sources(store, job, job_id, work, key):
    """clean_sources 맵을 채워 반환. 이미 있고 파일이 존재하면 스킵(재과금 0).
    각 스레드는 remove_subtitles만 하고 경로를 반환 → DB 저장은 취합 후 메인에서 1회(경합 없음)."""
    source_map = _resolve_sources(job, Path(work))
    cached = dict(job.get("clean_sources") or {})
    todo = [(vid, src) for vid, src in source_map.items()
            if not (cached.get(vid) and Path(cached[vid]).exists())]
    if todo:
        with ThreadPoolExecutor(max_workers=len(todo)) as ex:
            for vid, out in ex.map(lambda t: _clean_one(t, key, work), todo):
                cached[vid] = out
        store.update_mix_job(job_id, clean_sources=cached)
    return cached


def run_clean_sources(job_id, db_path, work_root):
    """2단계: 각 소스 원본을 VMake로 자막제거해 clean_sources에 캐시.
    BackgroundTasks로 불리므로 예외를 밖으로 안 던진다(clean_status로만 알린다)."""
    store = Store(db_path)
    job = store.get_mix_job(job_id)
    if not job:
        return
    try:
        work = Path(work_root) / job_id
        work.mkdir(parents=True, exist_ok=True)
        key = _vmake_key(store)
        if not key:
            store.update_mix_job(job_id, clean_status="failed",
                                 clean_error="VMake 개인키가 등록되지 않았습니다")
            return
        _ensure_clean_sources(store, job, job_id, work, key)
        store.update_mix_job(job_id, clean_status="ready", clean_error=None)
    except Exception as e:  # noqa: BLE001 — BackgroundTasks라 밖에서 아무도 안 받는다
        traceback.print_exc(file=sys.stderr)
        store.update_mix_job(job_id, clean_status="failed", clean_error=str(e))


def run_preview(job_id, db_path, work_root):
    """1단계 미리보기: 유료 자막제거(VMake)·꾸미기 없이 믹스+음성+기본자막만 렌더.

    ★clean_fn을 안 넘기는 것이 이 함수의 전부다 — assemble이 이미 3토막
    (_render_mix → clean_fn(선택) → _burn_captions)이라 clean_fn=None이면 유료 단계만
    빠진다(스펙 §3). deco={}로 꾸미기도 뺀다(4단계 소관).

    왜 필요한가: 다음 단계(자막제거)가 VMake 유료 API라, 컷·대본이 틀린 채 넘어가면 그 돈이
    날아간다. 편집안(텍스트)만 보고는 판단이 안 되므로 여기서 공짜로 보여준다.
    원본 자막이 남는 건 의도된 트레이드오프 — 두 겹은 지저분할 뿐 공짜고, 2단계가 깨끗하게 다시 굽는다.

    기존 status(downloading→…→done)는 **건드리지 않는다** — preview_status만 쓴다.
    섞으면 최종렌더 폴링과 서로를 오인한다(스펙 §6.1).

    BackgroundTasks로 불리므로 예외를 밖으로 던지지 않는다(아무도 안 받는다).
    """
    store = Store(db_path)
    job = store.get_mix_job(job_id)
    if not job or not job.get("edit_plan"):
        return
    try:
        # ★mkdir을 try 안에 둔다 — 밖에서 터지면 preview_status가 갱신되지 않아 화면이 무한 ⏳가 된다
        # (라우트가 이미 'rendering'을 써둔 상태라 failed로 내려주는 건 여기밖에 없다).
        work = Path(work_root) / job_id
        work.mkdir(parents=True, exist_ok=True)
        store.update_mix_job(job_id, preview_status="rendering", preview_error=None)
        plan = job["edit_plan"]
        tts_paths = {b["beat_idx"]: b["tts_path"] for b in plan["beats"] if b.get("tts_path")}
        source_video_paths = _resolve_sources(job, work)
        out_path = work / "preview.mp4"
        # headcopy·caption_style은 **넘기지 않는다**(스펙 §9: 꾸미기 제외 / caption_style 기본값만).
        # headcopy는 store.py 주석대로 "영상제작 5단계 꾸미기 헤드카피"라 deco={}로 꾸미기를
        # 뺐다면서 헤드카피를 넘기는 건 자기모순이었다. assemble의 기본값이면 우리 자막은 정상으로
        # 굽힌다(라이브 관측: caption_style=None인 job으로 렌더해 자막 정상 확인).
        assemble(plan, tts_paths, source_video_paths, str(out_path),
                 clean_fn=None,                      # ← 유료 VMake 건너뜀. 이게 핵심이다.
                 deco={},                             # ← 꾸미기 없음(4단계 소관)
                 cutaway_paths=_resolve_cutaway_paths(store, plan, job.get("customer_id", 0)))
        store.update_mix_job(job_id, preview_status="ready", preview_path=str(out_path))
    except Exception as e:  # noqa: BLE001 — BackgroundTasks라 밖에서 아무도 안 받는다
        traceback.print_exc(file=sys.stderr)
        store.update_mix_job(job_id, preview_status="failed", preview_error=str(e))


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

        # 자막제거: 소스 원본을 미리(2단계) 또는 여기서(버튼 미사용 시) 청소해 그 소스로 조립한다.
        # mix_raw 위 clean_fn(구방식)은 폐기 — 소스단위여야 TTS/컷과 무관하게 캐시가 성립한다.
        if job.get("subtitle_removal"):
            key = _vmake_key(store)
            if not key:
                raise RuntimeError("자막 제거가 켜져 있으나 VMake 개인키가 등록되지 않았습니다")
            clean_map = _ensure_clean_sources(store, job, job_id, work, key)
            store.update_mix_job(job_id, clean_status="ready", clean_error=None)
            source_video_paths = {vid: clean_map.get(vid, p)
                                  for vid, p in source_video_paths.items()}

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
        # 모션 팩: pack_id → 비트 타임라인으로 레이어 생성(렌더 시점에만 알 수 있음)
        # pack_id 없으면 _apply_motion_pack이 무변경으로 통과하므로, 그 경우 불필요한
        # ffprobe 호출(_beat_timeline)을 피한다 — 수동 layers만 쓰는 기존 deco를 위해 필수.
        caption_style = job.get("caption_style")
        if (deco.get("motion") or {}).get("pack_id"):
            timeline = _beat_timeline(plan, tts_paths)
            deco, caption_style = _apply_motion_pack(deco, caption_style, timeline, load_packs(MOTION_ASSETS_DIR))
        # 모션 레이어(전환·스티커): asset_id → 실경로·기본배치 해석
        motion = deco.get("motion") or {}
        if motion.get("layers"):
            resolved = resolve_layers(motion["layers"], MOTION_ASSETS_DIR)
            deco = {**deco, "motion": {**motion, "layers": resolved}}
        # 컷어웨이: 비트에 붙은 asset_id를 media_path로 해석해 assemble에 넘긴다.
        # 저장위치(match_scene_assets가 쓴 beat["cutaway"]) = 읽기위치(여기) — seam 일치.
        cutaway_paths = _resolve_cutaway_paths(store, plan, job.get("customer_id", 0))
        assemble(plan, tts_paths, source_video_paths, str(out_path), clean_fn=None,
                 headcopy=job.get("headcopy"), caption_style=caption_style,
                 deco=deco, cutaway_paths=cutaway_paths)
        store.update_mix_job(job_id, status="done", video_path=str(out_path))
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        store.update_mix_job(job_id, status="failed", error=str(e))


def resynth_one_beat(job_id, beat_idx, voice_override, db_path, work_root):
    """비트 하나만 voice_override로 재합성해 같은 mp3에 덮어쓰고 자막을 재동기한다.
    최종 렌더는 재합성 없이 이 mp3(beat['tts_path'])를 재사용하므로 교정이 그대로 남는다."""
    store = Store(db_path)
    job = store.get_mix_job(job_id)
    if not job or not job.get("edit_plan"):
        return
    plan = job["edit_plan"]
    beat = next((b for b in plan["beats"] if b["beat_idx"] == beat_idx), None)
    if beat is None:
        return
    total = len(plan["beats"])
    i = next(k for k, b in enumerate(plan["beats"]) if b["beat_idx"] == beat_idx)
    work = Path(work_root) / job_id
    tts_dir = work / "tts"
    tts_dir.mkdir(parents=True, exist_ok=True)
    out = tts_dir / f"beat_{beat_idx}.mp3"
    try:
        synthesize_line(
            beat["narration"], out, voice=voice_override, beat_role=beat.get("role"),
            beat_index=i, beat_total=total,
            previous_text=plan["beats"][i - 1]["narration"] if i > 0 else None,
            next_text=plan["beats"][i + 1]["narration"] if i < total - 1 else None,
        )
        beat["tts_path"] = str(out)
        beat["voice_override"] = voice_override
        beat["cap_durs"] = None
        words = asr_check.transcribe_words(str(out))
        if words:
            beat["cap_durs"] = caption_sync.phrase_durs_from_words(
                beat["narration"], words, _probe_duration(str(out)))
        store.update_mix_job(job_id, edit_plan=plan)
    except Exception as e:
        traceback.print_exc(file=sys.stderr)


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
    try:
        _synthesize_beats(plan["beats"], work / "tts", voice=job.get("voice"))
        store.update_mix_job(job_id, edit_plan=plan, status="ready_for_review")
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        store.update_mix_job(job_id, status="failed", error=str(e))
