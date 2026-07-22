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
from shopping_shorts.edit_plan import _SYLLABLES_PER_SEC, build_edit_plan, conform_narration
from shopping_shorts.scene_match import match_scene_assets, match_sfx
from shopping_shorts import tts
from shopping_shorts import audio_post
from shopping_shorts.video_assemble import assemble, _beat_timeline, _probe_duration, _MAX_SLOWMO
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
    silence_trim, naturalize_profile, model_id, pace_mode). voice 없으면 전부 기본값(config
    기본 성우, 속도 1.0, 무음삭제 off, naturalize_profile None → naturalize()가 자체 기본값 사용,
    pace_mode False → 속도감 다듬기 없음 = 옛 동작).

    스냅샷은 /api/mix/voice가 프리셋에서 통째로 복사해 넣는다 — naturalize_profile·model_id가
    빠지면 튜닝 작업대에서 동결한 값이 렌더에 도달하지 못한다(2026-07-15 whole-branch 리뷰 S1/S8)."""
    v = voice or {}
    speed = v.get("speed", 1.0)
    extra_tempo = speed / 1.2 if speed > 1.2 else 1.0  # 1.2 초과분만 atempo로
    return (v.get("voice_id"), v.get("settings"), speed, extra_tempo,
            v.get("silence_trim", "off"), v.get("naturalize_profile"),
            v.get("model_id") or "eleven_v3", v.get("pace_mode", False))


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
    voice_id, settings, speed, extra_tempo, trim, prof_v, model_id, pace_mode = _voice_params(voice)
    prof = merge_profile(profile if profile is not None else prof_v)
    natural = naturalize(narration, prof, beat_role=beat_role,
                         beat_index=beat_index, beat_total=beat_total)
    tts.synthesize_best(natural, str(out_path), n=prof.get("n_best", 1),
                        base_seed=prof.get("seed"), ranker=ranker,
                        voice_id=voice_id, voice_settings=settings, speed=speed,
                        model_id=model_id, previous_text=previous_text, next_text=next_text)
    audio_post.post_process(str(out_path), str(out_path), tempo=extra_tempo,
                            silence_trim=trim, pace_mode=pace_mode)
    return natural


def _synthesize_beats(beats, tts_dir, *, voice, skip_existing=False):
    """비트별로 synthesize_line 호출. beat['tts_path']를 채운다.
    연속성(previous_text/next_text)은 인접 비트의 '원문'(naturalize 전) narration을 쓴다
    — naturalize된 텍스트(오디오 태그·추임새 포함)를 연속성으로 넘기면 ElevenLabs가
    태그를 발화 텍스트로 오인할 수 있어서다.

    skip_existing=True: 이미 tts_path가 있는 비트는 재합성하지 않는다. 렌더 경로
    (run_preview/run_render)가 조립 직전 TTS를 '보장'하는 방어심층용 — 추천 후보(합성 완료,
    tts_path 있음)는 0원, 갈아끼운 후보(tts_path 키 자체가 없음)만 그 자리에서 합성한다.
    ★파일 실재가 아니라 tts_path '존재'로 판단한다 — 하류 tts_paths도 truthiness로만 보므로
    존재하되 파일이 없는 경우의 처리(별개 관심사)를 이 버그 수정이 바꾸지 않게 한다.
    """
    tts_dir = Path(tts_dir)
    tts_dir.mkdir(parents=True, exist_ok=True)
    total = len(beats)
    for i, beat in enumerate(beats):
        out = tts_dir / f"beat_{beat['beat_idx']}.mp3"
        if skip_existing and beat.get("tts_path"):
            continue
        synthesize_line(
            beat["narration"], out, voice=voice, beat_role=beat.get("role"),
            beat_index=i, beat_total=total,
            previous_text=beats[i - 1]["narration"] if i > 0 else None,
            next_text=beats[i + 1]["narration"] if i < total - 1 else None,
        )
        beat["tts_path"] = str(out)
        # UI '영상 길이'는 target_seconds 합인데, 추정(글자÷5.7)은 보이스 speed를 못 봐서
        # 빠른 보이스(speed>1)면 실제 음성보다 길게 잡혀 '음성이 짧아요' 오경고가 떴다.
        # 실제 발화초로 덮어 UI·조립(tts_dur)·최종영상을 한 값으로 맞춘다(2026-07-21).
        # probe 실패(손상·미존재 mp3)는 조용히 추정 유지 — target 덮어쓰기는 부가기능이라 죽이면 안 된다.
        try:
            _ad = _probe_duration(str(out))
        except Exception:
            _ad = None
        if _ad and _ad > 0:
            beat["target_seconds"] = round(_ad, 1)
        # 자막 타이밍용: 실제 말한 워드 시각으로 구절 표시시간 계산(실패/키없음 → 미설정=폴백).
        beat["cap_durs"] = None
        words = asr_check.transcribe_words(str(out))
        if words:
            beat["cap_durs"] = caption_sync.phrase_durs_from_words(
                beat["narration"], words, _ad or 0.0,
                preset=beat.get("caption_lines"))   # None일 수 있음 → 폴백


def _refill_beats_to_tts(beats, source_scripts, tts_dir):
    """TTS 후 재보정 — 각 비트 화면(primary+alternates)이 **실 TTS 길이**보다 짧으면 풀에서
    같은 소스 우선 B롤을 더 붙인다. 추정≠실제로 생긴 틈이 렌더에서 프리즈/슬로우로 새는 걸
    막는 뿌리 fix(2026-07-21). backbone.fill_clips_to_cover(need=실TTS)를 재사용. 원본 beat의
    alternates만 갱신(다른 필드 불변). probe/pool 문제는 조용히 통과(부가기능이 job 안 죽인다)."""
    from collections import Counter
    from shopping_shorts import backbone
    if not source_scripts:
        return
    sc = Counter((b.get("primary") or {}).get("video_id")
                 for b in beats if b.get("primary"))
    for b in beats:
        tp = b.get("tts_path")
        if not tp:
            continue
        try:
            td = _probe_duration(str(tp))
        except Exception:
            continue
        if not td or backbone.clip_seconds(b) >= td:
            continue
        try:
            filled = backbone.fill_clips_to_cover(b, source_scripts, src_count=sc, need=td)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            continue
        b["alternates"] = filled.get("alternates", b.get("alternates"))


# 콘폼 트리거 임계(초). 이하의 초과분은 켄번즈 홀드(≤0.8s)로 자연 흡수되는 수준이라
# 제미니 리라이트+재TTS 비용을 쓰지 않는다(설계 §1, 2026-07-20).
_CONFORM_MIN_GAP = 0.8


def _conform_beats(beats, tts_dir, *, voice):
    """싱크 콘폼 패스(2026-07-20 설계 T3) — 대사가 영상 예산을 넘는 비트만 표면 재단.

    예산 = Σ(primary+alternates 구간 길이) × _MAX_SLOWMO. _plan_beat_clips가 세그먼트를
    전부 소진한 뒤에만 얼리므로 이 예산이 "영상으로 채울 수 있는 최대"다(코드 검증) —
    즉 초과분은 영상으로 못 채우고, 남은 유일한 레버는 대본 길이다.

    비트당 리라이트 1회. 실패(키 소진·게이트 불통과·TTS 예외)는 조용히 통과 —
    원문+freeze 폴백이 렌더 실패보다 낫다. sync_gap은 성공/실패 무관하게 남겨
    편집안 화면이 근거를 보여준다(**b 스프레드로 자동 전달).

    ⚠️ narration 교체는 재TTS **성공 후에만** — 실패 시 문장/음성 불일치를 만들지 않는다."""
    total = len(beats)
    for i, beat in enumerate(beats):
        tp = beat.get("tts_path")
        if not tp:
            continue
        segs = [beat.get("primary")] + list(beat.get("alternates") or [])
        budget = sum(max(0.0, float(s["end"]) - float(s["start"])) for s in segs if s) * _MAX_SLOWMO
        if budget <= 0:
            continue
        try:
            tts_dur = _probe_duration(tp)
        except Exception:
            continue
        gap = tts_dur - budget
        beat["sync_gap"] = round(max(0.0, gap), 2)
        if gap <= _CONFORM_MIN_GAP:
            continue
        new_n = conform_narration(beat["narration"], budget)
        if not new_n:
            continue   # 리라이트 실패 → 원문 유지, freeze 폴백(sync_gap 플래그 잔존)
        out = Path(tts_dir) / f"beat_{beat['beat_idx']}.mp3"
        try:
            synthesize_line(
                new_n, out, voice=voice, beat_role=beat.get("role"),
                beat_index=i, beat_total=total,
                previous_text=beats[i - 1]["narration"] if i > 0 else None,
                next_text=beats[i + 1]["narration"] if i < total - 1 else None,
            )
        except Exception:
            traceback.print_exc(file=sys.stderr)
            continue   # 재TTS 실패 → narration 미교체(문장/음성 일치 유지)
        beat["narration"] = new_n
        beat["conformed"] = True
        beat["caption_lines"] = None   # 나레이션이 바뀌면 AI 자막줄은 무효 → 정규식 폴백
        beat["tts_path"] = str(out)
        beat["cap_durs"] = None
        new_dur = _probe_duration(str(out))
        # UI 표시 초 = 실제 발화초(빠른 보이스 speed까지 반영). 추정(글자÷5.7)은 speed를
        # 못 봐 오차가 커서 실측으로 둔다(2026-07-21). 실측 실패 시에만 추정 폴백.
        beat["target_seconds"] = round(new_dur, 1) if new_dur and new_dur > 0 \
            else round(max(1.5, len(new_n.strip()) / _SYLLABLES_PER_SEC), 1)
        words = asr_check.transcribe_words(str(out))
        if words:
            beat["cap_durs"] = caption_sync.phrase_durs_from_words(new_n, words, new_dur)
        beat["sync_gap"] = round(max(0.0, new_dur - budget), 2)


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
                      voice=job.get("voice"), customer_id=job.get("customer_id", 0),
                      scene_first=job.get("scene_first", False),
                      reference_text=job.get("given_script") or "",
                      # 핑퐁(대본↔장면 왕복 행위매칭): 전역 설정으로 on/off(기본 off·회귀0).
                      # 스키마 컬럼 없이 한 스위치로 켠다 — store.set_setting('ping_pong_enabled','1').
                      ping_pong=(store.get_setting("ping_pong_enabled", "") == "1"),
                      # 백본-베이스(2026-07-21 확정스펙): 켜면 레퍼런스 자유생성 대신 백본 흐름 위에
                      # 100% 우리 대본을 생성한다. 스마트 믹스 토글이 이 설정도 함께 켠다.
                      backbone_base=(store.get_setting("backbone_base_enabled", "") == "1"),
                      # 백본 선정: URL로 플랫폼 판별(인스타/유튜브만 백본, 샤오홍슈 서브) + 사장님 지정.
                      backbone_meta=_backbone_meta_from_job(job, extracts),
                      backbone_forced=_resolve_backbone_forced(job, extracts))
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        store.update_mix_job(job_id, status="failed", error=str(e))
        # 유료게이트: 렌더 실패 → 예약한 'render' 크레딧 환불(계정+전역). 실패했는데 크레딧만
        # 날아가면 시니어에겐 '고장'으로 읽힌다(하루 2회뿐). points 실패환불(_fx_render_job)과 대칭.
        # ★render_charge_day가 있는 job만(=/api/mix/start가 실제 과금한 것) 환불하고, 딱 그 날짜로
        #   되돌린다. produce 2단계·auto_run·retype는 과금 안 해 이 값이 없다 → 오환불로 전역
        #   카운터를 갉아 다른 유저 과금을 상쇄하는 일을 막는다(리뷰 B/F).
        day = job.get("render_charge_day")
        if day:
            try:
                store.usage_decr(job.get("customer_id", 0), "render", day)
                store.usage_decr(-1, "render", day)
            except Exception:
                traceback.print_exc(file=sys.stderr)


def _job_urls(job):
    """job에서 소스 URL 리스트를 뽑는다. get_mix_job은 'urls'(파싱된 list)로 주지만
    혹시 원시행(urls_json 문자열)이 와도 안전하게 파싱한다."""
    import json as _json
    u = job.get("urls")
    if isinstance(u, list):
        return u
    try:
        return _json.loads(job.get("urls_json") or "[]")
    except Exception:
        return []


def _backbone_meta_from_job(job, extracts):
    """job의 urls + extracts 키(s0/s1/s2 순서)로 백본 선정용 meta 구성.
    → {video_id: {'platform': ...}}. 백본=인스타/유튜브 규칙이 실제로 걸리게 한다.
    ⚠️ get_mix_job은 'urls'(list) 키로 준다 — 예전 'urls_json' 접근은 항상 빈 값이라
    플랫폼 규칙이 통째로 죽어 있었다(2026-07-22 수정)."""
    from shopping_shorts import backbone as _bb
    urls = _job_urls(job)
    meta = {}
    for i, key in enumerate(extracts.keys()):
        url = urls[i] if i < len(urls) else ""
        meta[key] = {"platform": _bb.platform_of(url)}
    return meta


def _resolve_backbone_forced(job, extracts):
    """job.backbone_main(사장님이 UI에서 고른 urls 인덱스, 0-based) → 추출 소스의 video_id.
    extracts 키 순서 = 소스 순서(=urls 순서)라 인덱스로 바로 집는다. None/범위밖이면 None
    (자동 선정으로 폴백)."""
    idx = job.get("backbone_main")
    if idx is None:
        return None
    try:
        idx = int(idx)
    except (TypeError, ValueError):
        return None
    keys = list(extracts.keys())
    return keys[idx] if 0 <= idx < len(keys) else None


def _plan_and_tts(store, job_id, source_scripts, target_seconds, structure, video_type, work,
                  given_script=None, voice=None, customer_id=0,
                  scene_first=False, reference_text="", ping_pong=False,
                  backbone_meta=None, backbone_forced=None, backbone_base=False):
    """EDL 생성(3) + 비트별 TTS(4) → edit_plan 저장 + ready_for_review.
    run_mix_job(자동판별, video_type=None)과 retype_mix_job(사용자 선택 유형)이 공유.
    given_script: 있으면 확정 대본을 그대로 비트로 쪼개 영상만 매칭(영상제작 2단계).
    voice: job의 voice 스냅샷(선택된 보이스 프리셋) — 있으면 비트별 TTS에 적용.
    scene_first: 장면 우선 대본 모드(2026-07-20, Task6) — build_scene_first_plan으로 후보 n개를
        생성해 store에 저장하고, 추천(recommended) 후보의 plan을 그대로 쓴다. 후보가 하나도 없으면
        (grounding 전멸 등) 기존 build_edit_plan으로 폴백한다.
    reference_text: scene_first일 때 스타일·구조를 계승할 레퍼런스 대본(보통 given_script 재활용)."""
    # 3) 통합 EDL
    store.update_mix_job(job_id, status="planning")
    if scene_first:
        from shopping_shorts.edit_plan import build_scene_first_plan
        # 부품은행 주입(P0-2): 설정 bank_enabled=1일 때만 승인 훅·어미·부사·CTA·스파인을 조립해
        # 영상 대본 프롬프트에 실어준다. 기본 off → 회귀0. 매 job 상위 perf 풀에서 로테이션
        # 샘플되므로(P0-1) 영상마다 다른 훅으로 열린다. 조립 실패는 조용히 무주입(부가기능).
        bank_context = ""
        avoid_hooks = None
        if store.get_setting("bank_enabled", "") == "1":
            try:
                from shopping_shorts import bank_assemble
                # 은행(로테이션 부품·스파인) + novelty 회피블록(최근 쓴 훅·인물·CTA)을 함께 주입.
                # 회피는 은행과 같은 스위치로 켠다 — 켜면 매 영상이 다른 훅으로 열리게 밀어준다.
                _blocks = [bank_assemble.assemble_bank_context(store, video_type or ""),
                           bank_assemble.avoid_block(store)]
                bank_context = "\n\n".join(x for x in _blocks if x)
                # 프롬프트 회피를 무시하고 같은 훅을 낸 후보를 추천단계에서도 감점(belt-and-suspenders).
                avoid_hooks = store.recent_script_usage()["hooks"] or None
            except Exception:
                traceback.print_exc(file=sys.stderr)
        sf = build_scene_first_plan(source_scripts, reference_text, target_seconds,
                                    video_type=video_type, ping_pong=ping_pong,
                                    backbone_meta=backbone_meta, backbone_forced=backbone_forced,
                                    bank_context=bank_context, avoid_hooks=avoid_hooks,
                                    backbone_base=backbone_base)
        if sf["candidates"]:
            store.set_mix_candidates(job_id, sf["candidates"])
            rec = next((cand for cand in sf["candidates"] if cand["recommended"]),
                       sf["candidates"][0])
            plan = rec["plan"]
            # novelty(P0-3) 기록: 채택된 대본의 훅·인물·CTA를 남겨 다음 영상이 회피하게 한다.
            # 스위치 무관하게 항상 기록(데이터가 쌓여야 켰을 때 즉시 효과) — 실패해도 job 안 죽인다.
            try:
                _st = rec.get("story") or {}
                store.record_script_usage(_st.get("hook", ""), _st.get("story_person", ""),
                                          _st.get("cta_keyword", ""))
            except Exception:
                traceback.print_exc(file=sys.stderr)
        else:
            plan = build_edit_plan(source_scripts, target_seconds, structure=structure,
                                   video_type=video_type, given_script=given_script)
    else:
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
    # 3.6) 효과음(sfx) 역할 매칭 — 별도 자산 목록(asset_type="sfx")으로 조회한다. 위 clip
    # 목록엔 sfx가 없으므로 재조회 필요. match_sfx가 beat["sfx"]={asset_id,position,..}를 심고,
    # run_render/run_preview가 asset_id→media_path로 해석한다(컷어웨이와 같은 seam). Gemini 0회.
    sfx_assets = store.list_scene_assets(customer_id=customer_id, asset_type="sfx")
    if sfx_assets:
        plan = match_sfx(plan, sfx_assets)

    # 4) 비트별 TTS (naturalize + N-best + 연속성 + 프리셋 후처리)
    store.update_mix_job(job_id, status="tts")
    _synthesize_beats(plan["beats"], work / "tts", voice=voice)

    # 4.2) 프리즈 뿌리 fix(2026-07-21) — 화면을 **실 TTS 길이**만큼 재보정한다. fill은 plan
    # 시점에 나레이션 추정(글자÷5.7)으로 채웠는데, 빠른 보이스면 실제 TTS가 추정과 달라 생긴
    # 틈을 렌더가 프리즈/슬로우로 때워왔다(두더지잡기의 뿌리). 실 tts_dur보다 화면이 짧은
    # 비트만 같은 소스 우선 B롤로 더 채운다 → 렌더가 정지 대신 실영상으로 채운다.
    _refill_beats_to_tts(plan["beats"], source_scripts, work / "tts")

    # 4.5) 싱크 콘폼(2026-07-20) — 대사가 영상 예산을 넘는 비트만 압축 리라이트 + 그 비트 재TTS.
    # 저장(아래) 전에 돌므로 preview·final 렌더 모두 자동 적용. 실패해도 job을 죽이지 않는다.
    try:
        _conform_beats(plan["beats"], work / "tts", voice=voice)
    except Exception:
        traceback.print_exc(file=sys.stderr)

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
    """다운로드된 소스 mp4 경로 맵 {video_id: path}.

    ★스킵 일관성(2026-07-20 실사고): _prepare_sources가 불량 URL 소스를 건너뛰므로(다운로드
    안 됨), 여기서도 mp4 없는 video_id는 건너뛴다 — 미리보기/렌더 경로가 스킵된 소스를 찾다
    '소스 영상 없음: s1'으로 죽던 문제. edit_plan은 다운로드된 소스만 참조하고, video_assemble도
    source_video_paths에 없는 video_id는 걸러낸다(관용적). 단 하나도 없으면(전부 실패) 예외."""
    source_video_paths = {}
    for i in range(len(job["urls"])):
        vid = _source_video_id(i)
        mp4 = next((work / vid).glob("*.mp4"), None)
        if mp4 is not None:
            source_video_paths[vid] = str(mp4)
    if not source_video_paths:
        raise RuntimeError("소스 영상을 하나도 찾지 못했습니다 (다운로드 디렉터리에 mp4 없음)")
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


def _resolve_sfx_paths(store, plan, customer_id):
    """비트에 붙은 sfx asset_id → media_path. 컷어웨이와 같은 패턴(저장위치=읽기위치).
    run_render·run_preview 둘 다 이걸 써서 미리보기와 최종본이 같은 효과음을 낸다."""
    out = {}
    for beat in plan["beats"]:
        sfx = beat.get("sfx")
        if sfx:
            asset = store.get_scene_asset(sfx["asset_id"], customer_id=customer_id)
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


def assemble_clean_video(job_id, db_path, work_root):
    """자막제거(2단계) 후 '자막 없는 조립본'(clean_video_path)을 만들어 DB에 저장하고 경로 반환.
    VMake는 이미 탔으므로 clean_fn=None으로 청소된 소스를 재조립만 한다(추가과금 0). edit_plan·
    clean_sources가 없거나 조립 실패면 None. run_clean_sources(2단계)와 썸네일(5단계) 자가치유가
    공유한다 — 이전 조립이 재렌더/재매칭 레이스로 유실돼도 썸네일에서 다시 만들 수 있게(2026-07-21).
    """
    store = Store(db_path)
    job = store.get_mix_job(job_id)
    if not job:
        return None
    plan = job.get("edit_plan")
    clean_map = job.get("clean_sources") or {}
    if not plan or not clean_map:
        return None
    try:
        tts_paths = {b["beat_idx"]: b["tts_path"] for b in plan["beats"] if b.get("tts_path")}
        out_path = Path(work_root) / job_id / "clean_preview.mp4"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        assemble(plan, tts_paths, clean_map, str(out_path), clean_fn=None, deco={},
                 cutaway_paths=_resolve_cutaway_paths(store, plan, job.get("customer_id", 0)),
                 sfx_paths=_resolve_sfx_paths(store, plan, job.get("customer_id", 0)))
        store.update_mix_job(job_id, clean_video_path=str(out_path))
        return str(out_path)
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return None


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
        clean_map = _ensure_clean_sources(store, job, job_id, work, key)
        store.update_mix_job(job_id, clean_status="ready", clean_error=None)
    except Exception as e:  # noqa: BLE001 — BackgroundTasks라 밖에서 아무도 안 받는다
        traceback.print_exc(file=sys.stderr)
        store.update_mix_job(job_id, clean_status="failed", clean_error=str(e))
        return
    # ★썸네일(5단계) 배경은 자막 없는 조립본이 있어야 한다(app.py thumb/frames 우선순위 1번=
    # clean_video_path). 여기까진 소스 각각만 청소됐지 조립본이 없어, clean_video_path가 영원히
    # None이라 폴백이 preview_path(1단계 미리보기 — clean_fn=None으로 항상 원본 자막 그대로)로
    # 떨어졌다(2026-07-20 사장님 제보: 자막제거 후 썸네일에 지우기 전 문구가 그대로 나옴).
    # VMake는 위에서 이미 탔으니 clean_fn 없이 청소된 소스로 재조립만 한다(추가과금 0). 실패해도
    # clean_status는 안 되돌린다 — 소스청소(유료)는 이미 성공, 조립만 실패했다고 "실패"로 보이면
    # 재시도 혼란만 커진다. 조립 실패/유실 시엔 썸네일(5단계)이 자가치유로 다시 만든다(공유 헬퍼).
    assemble_clean_video(job_id, db_path, work_root)


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
        # ★TTS 보장(2026-07-21 실사고): 후보 선택(/api/mix/candidate)이 TTS 없는 후보 plan을
        #   edit_plan에 꽂으면 tts_paths가 비어 video_assemble이 "렌더할 비트가 없습니다"로 죽었다.
        #   조립 직전 스스로 낫는다 — 이미 있는 비트는 skip(재과금 0), 빠진 비트만 합성.
        #   합성 결과(tts_path)를 edit_plan에 되박아 최종 렌더가 재합성 없이 재사용하게 한다.
        _synthesize_beats(plan["beats"], work / "tts", voice=job.get("voice"), skip_existing=True)
        store.update_mix_job(job_id, edit_plan=plan)
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
                 cutaway_paths=_resolve_cutaway_paths(store, plan, job.get("customer_id", 0)),
                 sfx_paths=_resolve_sfx_paths(store, plan, job.get("customer_id", 0)))
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
        # ★TTS 보장(2026-07-21) — run_preview와 같은 방어심층. 미리보기를 건너뛰고 바로 렌더에
        #   와도(또는 TTS 없는 후보가 edit_plan에 있어도) 조립 직전 스스로 낫는다. 이미 있으면 skip.
        _synthesize_beats(plan["beats"], work / "tts", voice=job.get("voice"), skip_existing=True)
        store.update_mix_job(job_id, edit_plan=plan)
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
        sfx_paths = _resolve_sfx_paths(store, plan, job.get("customer_id", 0))
        assemble(plan, tts_paths, source_video_paths, str(out_path), clean_fn=None,
                 headcopy=job.get("headcopy"), caption_style=caption_style,
                 deco=deco, cutaway_paths=cutaway_paths, sfx_paths=sfx_paths)
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
                beat["narration"], words, _probe_duration(str(out)),
                preset=beat.get("caption_lines"))
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
