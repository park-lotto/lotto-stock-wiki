"""믹스 job 백그라운드 오케스트레이션(설계 §2·§5).

run_mix_job: 다운로드→대본추출(병렬)→EDL생성→TTS까지 진행하고 ready_for_review로.
run_render: 사용자가 확인 후 최종 ffmpeg 렌더 → done.
각 단계에서 mix_jobs.status를 갱신하고, 예외는 status='failed'+error로 잡는다.
"""
import hashlib
import subprocess
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from shopping_shorts.store import Store
from shopping_shorts.media_download import download_any
from shopping_shorts import script_extract
from shopping_shorts.script_extract import extract_script
from shopping_shorts.edit_plan import _SYLLABLES_PER_SEC, build_edit_plan, conform_narration
from shopping_shorts.scene_match import match_scene_assets, match_sfx
from shopping_shorts import tts
from shopping_shorts import audio_post
from shopping_shorts import config
from shopping_shorts.video_assemble import assemble, _beat_timeline, _probe_duration, _MAX_SLOWMO, preview_preset
from shopping_shorts.motion_assets import resolve_layers, DEFAULT_ASSETS_DIR
from shopping_shorts.motion_packs import build_plan, load_packs
from shopping_shorts.vmake_client import remove_subtitles
from shopping_shorts import sub_region
from shopping_shorts.narration_naturalize import naturalize, merge_profile
from shopping_shorts import asr_check
from shopping_shorts import caption_sync
from shopping_shorts import tts_timestamps
from shopping_shorts import pron_corrections
from shopping_shorts import backbone
from shopping_shorts import plan_gate

# 모션 자산 폴더(테스트가 monkeypatch로 교체 가능하도록 모듈 상수로 노출)
MOTION_ASSETS_DIR = DEFAULT_ASSETS_DIR

# ★TTS 고정 시드(2026-07-23 사장님 "왜 매일 달라지나"): 프리셋에 seed가 없으면(대부분) v3가
# 매 렌더 다른 목소리로 뽑혀 비트마다·날마다 성우가 달라졌다. 고정 시드를 박아 결정성 확보
# — 튜닝한 톤(stability·style)·모델은 그대로 두고 '매번 달라짐'만 없앤다. 명시 seed는 존중.
_PINNED_TTS_SEED = 7


def _beat_words(mp3_path, dur=None):
    """자막 싱크용 단어 타임스탬프. TTS가 준 것을 먼저 쓰고, 없으면 ASR로 폴백한다(2026-07-31).

    ①TTS 타임스탬프 — 우리가 보낸 원문 그대로의 시각이라 맞출 대상이 없다(정렬 실패 없음).
    ②ASR 폴백 — 옛 경로. ELEVENLABS_TIMESTAMPS를 끄거나, 그 엔드포인트가 죽었거나,
      키 없는 무음 mock일 때 여기로 온다. 폴백을 남겨두는 이유는 그 세 경우에도
      자막이 글자수 추정으로 떨어지지 않게 하기 위해서다.
    ★asr_check를 모듈 속성으로 부른다 — 테스트가 mix_pipeline.asr_check를 monkeypatch 한다.
    """
    words = tts_timestamps.words_from_mp3(mp3_path)
    if words:
        # 합성 뒤 audio_post가 배속·무음트림으로 파일을 고쳤을 수 있다 → 최종 길이로 되맞춤.
        return tts_timestamps.rescale(words, dur)
    return asr_check.transcribe_words(mp3_path)


def _source_video_id(i):
    return f"s{i}"


# 성우 미선택(2단계 미리보기 등) 기본 성우 = 미나·표현(kr-mina-expressive, 2026-07-25 사장님 확정).
# 예전 기본은 config.ELEVENLABS_VOICE_ID(Rachel=영어 성우)라 성우를 고르기 전 미리보기가
# 영어 성우로 한국어를 읽었다. 값은 assets/voice_presets.json의 kr-mina-expressive 스냅샷.
_DEFAULT_VOICE = {
    "preset_id": "kr-mina-expressive",
    "voice_id": "aiUUgjHa4mpHf6UenZuf",
    "model_id": "eleven_v3",
    "settings": {"stability": 0.35, "similarity_boost": 0.78, "style": 0.4},
    "speed": 1.6,
    "silence_trim": "mid",
    # 컷편집 빠른 느낌(2026-07-25 사장님): 4단계 UI 기본(⚡속도감 모드 체크)과 동일하게
    # 미리보기 기본도 무음 컷·타이트 이음을 켠다 — 안 켜면 미리보기만 늘어져 들린다.
    "pace_mode": True,
}


def _voice_params(voice):
    """job의 voice 스냅샷(dict|None) → (voice_id, voice_settings, speed, extra_tempo,
    silence_trim, naturalize_profile, model_id, pace_mode). voice 없으면 _DEFAULT_VOICE
    (미나·표현) 기본값. naturalize_profile None → naturalize()가 자체 기본값 사용,
    pace_mode False → 속도감 다듬기 없음 = 옛 동작.

    스냅샷은 /api/mix/voice가 프리셋에서 통째로 복사해 넣는다 — naturalize_profile·model_id가
    빠지면 튜닝 작업대에서 동결한 값이 렌더에 도달하지 못한다(2026-07-15 whole-branch 리뷰 S1/S8)."""
    v = voice or _DEFAULT_VOICE
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
                    ranker=asr_ranker, global_pron=None):
    """한 줄을 naturalize→TTS(N-best·연속성)→후처리까지 합성하고 변환텍스트를 반환.

    **튜닝 작업대와 실제 렌더가 공유하는 단일 경로**다. 양쪽이 각자 파이프라인을 조립하면
    인자가 갈려 "작업대에서 들은 소리 ≠ 영상 소리"가 된다(2026-07-15 리뷰 S3/S4/S5/S6).
    새 호출부를 만들지 말고 이 함수를 쓸 것.

    profile 미지정 시 voice 스냅샷의 naturalize_profile을 쓴다. seed/n_best는 merge_profile을
    거친 값으로 읽어 텍스트와 오디오가 같은 기준을 보게 한다(S10)."""
    voice_id, settings, speed, extra_tempo, trim, prof_v, model_id, pace_mode = _voice_params(voice)
    prof = merge_profile(profile if profile is not None else prof_v)
    # 전역 발음교정을 profile 위에 병합(설계 §2-A) — 렌더·작업대 공통 choke.
    prof = pron_corrections.overlay(prof, global_pron or {})
    natural = naturalize(narration, prof, beat_role=beat_role,
                         beat_index=beat_index, beat_total=beat_total)
    # 오독 자동회피(2026-07-22): Whisper 랭커(GROQ 키)가 실동작할 때만 n을 최소 2로
    # 끌어올려 오독 적은 take를 자동 선택한다(best-of-N). 키가 없으면 랭킹이 안 되므로
    # profile값 그대로 둔다 — 안 그러면 랭킹도 못 하면서 TTS만 N배 낭비한다.
    # floor라 명시 프리셋(n_best=3 등)은 안 깎는다(whole-branch S4 계약 유지).
    n_best = prof.get("n_best", 1)
    if config.GROQ_API_KEY and n_best < 2:
        n_best = 2
    tts.synthesize_best(natural, str(out_path), n=n_best,
                        base_seed=(prof.get("seed") if prof.get("seed") is not None else _PINNED_TTS_SEED),
                        ranker=ranker,
                        voice_id=voice_id, voice_settings=settings, speed=speed,
                        model_id=model_id, previous_text=previous_text, next_text=next_text)
    # 비트별 라우드니스 정규화는 실제 ElevenLabs 음성일 때만 — 키 없는 개발용 무음 mock에
    # loudnorm을 걸면 무음 바닥을 노이즈로 끌어올린다(reference_local_tts_silent_mock_trap).
    audio_post.post_process(str(out_path), str(out_path), tempo=extra_tempo,
                            silence_trim=trim, pace_mode=pace_mode,
                            loudnorm=bool(config.ELEVENLABS_API_KEY))
    return natural


def _beat_tts_path(tts_dir, beat):
    """비트 TTS 파일 경로 — 파일명을 나레이션 '내용 해시'로 키잉한다(2026-07-27 실사고:
    B로 만들고 A로 바꾸면 자막은 A인데 음성은 B였다). 예전엔 beat_{idx}.mp3로 후보끼리
    파일명을 공유해, B 렌더가 그 파일을 B 음성으로 덮어쓴 뒤 A는 skip_existing으로 재합성을
    건너뛰어 B 음성을 그대로 재생했다. 내용 해시를 넣으면 대본이 다른 후보는 파일도 달라 절대
    안 섞이고(A는 A파일, B는 B파일), 같은 대본은 그대로 재사용(0원)된다."""
    key = hashlib.md5((beat.get("narration") or "").encode("utf-8")).hexdigest()[:10]
    return str(Path(tts_dir) / f"beat_{beat['beat_idx']}_{key}.mp3")


def _synthesize_beats(beats, tts_dir, *, voice, skip_existing=False, global_pron=None):
    """비트별로 synthesize_line 호출. beat['tts_path']를 채운다.
    연속성(previous_text/next_text)은 인접 비트의 '원문'(naturalize 전) narration을 쓴다
    — naturalize된 텍스트(오디오 태그·추임새 포함)를 연속성으로 넘기면 ElevenLabs가
    태그를 발화 텍스트로 오인할 수 있어서다.

    skip_existing=True: 이미 tts_path가 있는 비트는 재합성하지 않는다. 렌더 경로
    (run_preview/run_render)가 조립 직전 TTS를 '보장'하는 방어심층용 — 추천 후보(합성 완료,
    tts_path 있음)는 0원, 갈아끼운 후보(tts_path 키 자체가 없음)만 그 자리에서 합성한다.
    ★파일 실재가 아니라 tts_path '존재'로 판단한다 — 하류 tts_paths도 truthiness로만 보므로
    존재하되 파일이 없는 경우의 처리(별개 관심사)를 이 버그 수정이 바꾸지 않게 한다.

    ★비트별 합성은 서로 독립이라(고유 파일 beat_{beat_idx}.mp3, 이웃텍스트는 인덱스로
    미리 정해짐 — 앞 비트 오디오에 의존하지 않음) config.TTS_MAX_WORKERS로 bounded
    ThreadPoolExecutor 병렬 실행한다(2026-07-24, 실처리시간 단축). 순서·값은 순차 실행과
    동일 — worker는 자기 고유 인덱스 i만 쓰고 공유 가변상태(커서 등)는 없다. 429 방지를
    위해 무제한 동시성은 금지(ElevenLabs·GROQ-Whisper 랭커 rate limit).
    """
    tts_dir = Path(tts_dir)
    tts_dir.mkdir(parents=True, exist_ok=True)
    total = len(beats)

    def _one(i):
        beat = beats[i]
        out = Path(_beat_tts_path(tts_dir, beat))
        # 이 비트의 '현재 대본'에 해당하는 파일이 이미 있으면(=같은 후보·같은 대본) 재합성 스킵.
        # tts_path가 다른 이름을 가리키거나(후보 스위치) 파일이 없으면 새로 합성한다.
        if skip_existing and beat.get("tts_path") == str(out) and out.exists():
            return
        synthesize_line(
            beat["narration"], out, voice=voice, beat_role=beat.get("role"),
            beat_index=i, beat_total=total,
            previous_text=beats[i - 1]["narration"] if i > 0 else None,
            next_text=beats[i + 1]["narration"] if i < total - 1 else None,
            global_pron=global_pron,
        )
        beat["tts_path"] = str(out)
        # ★비트 끝 무음 트림(2026-07-22) — 각 비트 TTS 뒤 자연 무음(호흡·여백)을 잘라 이어붙임을
        # 딱 맞춘다. 안 자르면 비트 경계마다 dead-air가 남아 뚝뚝 끊긴다(레퍼런스 릴스는 무음 0).
        # 뒤만 자르고 작은 여백을 남겨 급함·클릭 방지. 실패·mock은 원본 유지(무해).
        try:
            audio_post.trim_tail_silence(out, out)
        except Exception:
            traceback.print_exc(file=sys.stderr)
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
        words = _beat_words(str(out), _ad)
        if words:
            beat["cap_durs"] = caption_sync.phrase_durs_from_words(
                beat["narration"], words, _ad or 0.0,
                preset=beat.get("caption_lines"))   # None일 수 있음 → 폴백

    if total == 0:
        return
    _t0 = datetime.now(timezone.utc)
    workers = max(1, min(config.TTS_MAX_WORKERS, total))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_one, i) for i in range(total)]
        for f in futures:
            f.result()  # 예외를 여기서 소비 — 숨기지 않고 그대로 전파(run_mix_job이 failed 처리)
    print(f"[tts] {total}비트 합성 {(datetime.now(timezone.utc) - _t0).total_seconds():.1f}s "
          f"(workers={workers})", file=sys.stderr)


def _sources_is_recipe(sources):
    """소스 category 다수결이 '레시피'면 True(장면 결 맞춤 분기). 비면 False.
    입력이 dict거나 원소가 dict가 아니어도 크래시하지 않는다(fail-open=False) — 실호출은
    list[dict]지만 일부 경로/테스트가 dict나 비정형을 넘겨도 안전해야 한다."""
    if isinstance(sources, dict):
        sources = list(sources.values())
    cats = [s.get("category") for s in (sources or [])
            if isinstance(s, dict) and s.get("category")]
    if not cats:
        return False
    return cats.count("레시피") * 2 > len(cats)


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
    # ★전역 used seg(2026-07-23 사장님 "동일 장면 반복 그만"): 모든 비트가 이미 쓴 seg를 모아
    # fill에 넘겨 비트 사이 반복을 막는다. 비트를 채울 때마다 새로 붙은 seg를 여기 등록한다.
    used_all = set()
    for b in beats:
        p = b.get("primary") or {}
        if p.get("seg_id"):
            used_all.add(p["seg_id"])
        for a in (b.get("alternates") or []):
            if a.get("seg_id"):
                used_all.add(a["seg_id"])
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
        # 포인트 비트(비법 소스 얹기 등 결정적 행위)는 그 장면이 주인공 — 클립을 덜 붙여(상한 2)
        # 파편으로 묻지 않고 길게 홀드한다. 앰비언트 비트는 기본 상한(config)으로 비주얼을 채움.
        mc = 2 if backbone.is_point_beat(b) else None
        try:
            filled = backbone.fill_clips_to_cover(b, source_scripts, src_count=sc, need=td,
                                                  max_clips=mc, avoid_segs=used_all)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            continue
        new_alts = filled.get("alternates", b.get("alternates"))
        b["alternates"] = new_alts
        for a in (new_alts or []):        # 새로 붙은 seg를 전역에 등록 → 다음 비트가 안 겹치게
            if a.get("seg_id"):
                used_all.add(a["seg_id"])


# 콘폼 트리거 임계(초). 이하의 초과분은 켄번즈 홀드(≤0.8s)로 자연 흡수되는 수준이라
# 제미니 리라이트+재TTS 비용을 쓰지 않는다(설계 §1, 2026-07-20).
_CONFORM_MIN_GAP = 0.8


def _conform_beats(beats, tts_dir, *, voice, global_pron=None):
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
                global_pron=global_pron,
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
        words = _beat_words(str(out), new_dur)
        if words:
            beat["cap_durs"] = caption_sync.phrase_durs_from_words(new_n, words, new_dur)
        beat["sync_gap"] = round(max(0.0, new_dur - budget), 2)


# 추출이 영상의 이만큼도 구간화하지 못하면 '빈약'으로 본다(2026-07-31).
# 실측: 21초 영상이 2구간 7.4초(35%)로 나와 재료로 못 썼는데 화면엔 표시가 없었다.
_MIN_COVERAGE = 0.55


def _video_seconds(path):
    """소스 영상 실제 길이(초). 못 재면 None(판정 생략 = 무해)."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, timeout=20)
        return float((out.stdout or "").strip())
    except Exception:
        return None


def _extract_coverage(r, path):
    """추출 구간이 영상의 몇 %를 덮었나. 판정 불가면 None.

    ★왜 '구간 개수'가 아니라 커버리지인가: 컷이 긴 영상은 구간이 적어도 정상이다.
      실패는 '영상 대부분이 구간으로 안 잡힌' 경우다(2026-07-31 job 8226822c5b09).
    """
    dur = _video_seconds(path)
    if not dur or dur <= 0:
        return None
    covered = sum(max(0.0, float(s.get("end") or 0) - float(s.get("start") or 0))
                  for s in (r.get("segments") or []))
    return min(1.0, covered / dur)


def _prepare_sources(urls, work):
    """소스 URL들을 플랫폼 무관하게 다운로드 → ({video_id: mp4경로}, {video_id: caption}, skipped).
    caption은 인스타 소스만 채워짐(download_any가 (path, caption) 튜플 반환) — 유튜브/틱톡은
    빈 문자열이라 extract_script가 영상 재전사로 채운다.

    ★소스별 예외격리(2026-07-19 실사고): 한 URL이 다운로드 안 되면 그 소스만 건너뛰고
    나머지로 계속한다 — 불량 URL 하나(렌즈 즐겨찾기로 샌 instagram.com/popular/{슬러그} 등)가
    배치 전체를 죽이던 걸 막는다. 근본차단은 lens_discover._is_watchable(입구), 여기는 백스톱.
    video_id는 인덱스 기준(s{i})이라 중간이 빠져도 나머지 매칭에 영향 없다(갭 허용).
    전부 실패(0개 생존)하면 RuntimeError. skipped=[(url, err), ...].

    병렬 다운로드(2026-07-24 속도개선 T③) — 아래 '대본 추출(병렬)' 단계와 같은
    ThreadPoolExecutor 패턴. 예외는 워커 안에서 잡아 (vid, path, caption, err) 튜플로
    돌려주므로 ex.map이 첫 예외에서 멈추는 일이 없다(소스별 격리 유지)."""
    def _download_one(item):
        i, url = item
        vid = _source_video_id(i)
        d = Path(work) / vid
        d.mkdir(parents=True, exist_ok=True)
        try:
            path, caption = download_any(url, str(d))
            return vid, path, caption, None
        except Exception as e:  # noqa: BLE001 — 소스별 격리가 목적
            print(f"_prepare_sources: 소스 스킵 — {url}: {e}", file=sys.stderr)
            return vid, None, None, (url, str(e))

    video_paths = {}
    captions = {}
    skipped = []
    with ThreadPoolExecutor(max_workers=max(1, len(urls))) as ex:
        results = list(ex.map(_download_one, enumerate(urls)))
    for vid, path, caption, err in results:
        if err is not None:
            skipped.append(err)
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
    _gpron = pron_corrections.load(store)
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
        # 프레임 태깅 추출전환(B1, 2026-07-29): 켜면 영상 통째 업로드 대신 파이썬 컷+프레임+오디오
        # 전사로 추출한다(느림·PROCESSING실패 근본해소). 기본 off=회귀0. 실측 후 승격.
        # 설계: docs/superpowers/specs/2026-07-29-프레임태깅-추출전환-design.md
        _use_frames = store.get_setting("frame_extract_enabled", "") == "1"
        def _extract(item):
            vid, path = item
            # 캐시 재사용(2026-07-24): 이 소스 대본을 담기/AI PICK/뽑기 때 이미 뽑아
            # script_extracts에 저장했으면 그대로 쓴다 — Gemini/Whisper 재전사 스킵(속도↑).
            # ★품질 무해 가드: extract_script와 동일한 {segments(seg_id 포함), full_text} 형태를
            #   그대로 저장했으므로 동일 데이터다. 단 seg_id가 다 있어야 장면매칭이 성립하므로,
            #   segments가 비었거나 seg_id 없는 항목이 하나라도 있으면 캐시를 버리고 새로 추출한다.
            cached = None
            try:
                cached = store.get_extract(vid)
            except Exception:
                cached = None
            segs = (cached or {}).get("segments")
            # ★스키마 승격(2026-07-31): change('사물이 무엇이 됐나') 필드가 생기기 전 캐시는
            #   영상의 진짜 포인트(갈라지다→매끈해지다·튀다·모찌처럼 늘어난다)를 하나도 안 갖고
            #   있다. 그대로 쓰면 도서관에 쌓인 옛 영상만 영원히 옛 품질로 남아 "어떤 건 되고
            #   어떤 건 안 되네"가 반복된다 → 필드 자체가 없으면 옛 스키마로 보고 다시 뽑는다.
            #   영상당 딱 한 번(재추출 결과가 캐시를 덮어씀). 값이 빈 문자열인 건 모델이 '변화
            #   없음'이라 판단한 정상 결과이므로 재추출하지 않는다(키 유무로만 판별).
            if segs and not any("change" in s for s in segs):
                segs = None
            if segs and all(s.get("seg_id") for s in segs):
                r = {"segments": segs, "full_text": (cached.get("full_text") or "")}
                # 무자막 소스 특장점(2026-07-26): 캐시엔 최상위 필드가 없을 수 있으므로
                # 세그별 product_benefits로 집계 폴백. 이 필드 추가 전 캐시는 빈 리스트 —
                # full_text도 비었다면 그 소스는 예전처럼 화면 재료로만 쓰인다(무해).
                r["product_benefits"] = (script_extract._norm_benefits(
                    cached.get("product_benefits")) or script_extract._collect_benefits(segs))
            elif _use_frames:
                from shopping_shorts import frame_script
                r = frame_script.extract_script_frames(path, vid, caption=captions.get(vid, ""))
                # 프레임 경로가 세그먼트를 못 만들면(컷 감지 실패 등) 기존 영상추출로 폴백 — 빈 결과 금지.
                if not r.get("segments"):
                    r = extract_script(path, vid, caption=captions.get(vid, ""))
            else:
                r = extract_script(path, vid, caption=captions.get(vid, ""))
            # ★조용한 추출 실패 잡기(2026-07-31 사장님: "실제 영상은 20초가 넘는데 추출이
            #   실패한 거라 사용자는 알 수가 없다"). 실측 job 8226822c5b09: 21초짜리 B영상이
            #   2구간 7.4초로 뭉쳐 나와 재료가 사실상 없었고, 화면엔 아무 표시도 없어서
            #   "왜 A로만 만들어졌지?"로만 보였다. → 커버리지를 재서 낮으면 한 번 다시 뽑고,
            #   그래도 낮으면 결과에 표시를 남겨 상류가 사장님께 알릴 수 있게 한다.
            cov = _extract_coverage(r, path)
            if cov is not None and cov < _MIN_COVERAGE:
                r2 = extract_script(path, vid, caption=captions.get(vid, ""))
                cov2 = _extract_coverage(r2, path)
                if cov2 is None or cov2 > (cov or 0):
                    r, cov = r2, cov2
            r["coverage"] = cov
            r["weak_extract"] = bool(cov is not None and cov < _MIN_COVERAGE)
            if r["weak_extract"]:
                print(f"[extract] ⚠️ {vid} 추출 빈약 — 영상의 {cov:.0%}만 구간화됨"
                      f"(구간 {len(r.get('segments') or [])}개). 재료로 거의 못 쓴다.", flush=True)
            r["video_id"] = vid
            # category(ai_categorize가 script_extracts.category에 저장) 전달 → 장면 결 맞춤(is_recipe) 분기용.
            # cached는 위에서 이미 조회했다(segments가 못써도 category 컬럼은 실려온다).
            r["category"] = (cached or {}).get("category")
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
                      # 백본 선정: URL로 플랫폼 판별(인스타/유튜브만 백본, 샤오홍슈 서브)
                      # + 참여도(수집캐시 댓글수) + 사장님 지정.
                      backbone_meta=_backbone_meta_from_job(job, extracts, store=store),
                      backbone_forced=_resolve_backbone_forced(job, extracts),
                      global_pron=_gpron)
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        store.update_mix_job(job_id, status="failed", error=str(e))
        # 유료게이트: 렌더 실패 → 예약한 'render' 크레딧 환불(계정+전역). 실패했는데 크레딧만
        # 날아가면 시니어에겐 '고장'으로 읽힌다(하루 2회뿐). points 실패환불(_fx_render_job)과 대칭.
        # ★render_charge_day가 있는 job만(=/api/mix/start가 실제 과금한 것) 환불하고, 딱 그 날짜로
        #   되돌린다. produce 2단계·auto_run·retype는 과금 안 해 이 값이 없다 → 오환불로 전역
        #   카운터를 갉아 다른 유저 과금을 상쇄하는 일을 막는다(리뷰 B/F).
        _refund_render_charge(store, job.get("customer_id", 0), job.get("render_charge_day"))


def _refund_render_charge(store, customer_id, charge_day):
    """렌더 실패 환불. charge_day=None이면 과금 안 한 job(오환불 방지) → no-op.
    "trial"(🎁 무료체험 이벤트)이면 계정은 영구 trial 버킷을, 전역은 오늘 버킷을 되돌린다
    (전역은 항상 today로 집계됐다). 그 외(날짜)면 계정·전역 둘 다 그 날짜로."""
    if not charge_day:
        return
    try:
        if charge_day == "trial":
            store.usage_decr(customer_id, "render", "trial")
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            store.usage_decr(-1, "render", today)
        else:
            store.usage_decr(customer_id, "render", charge_day)
            store.usage_decr(-1, "render", charge_day)
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


def _engagement_map(store):
    """수집 캐시(last_run)의 shortcode→댓글수 맵. 백본 선정의 참여도 신호용(사장님: '댓글도
    봐야 한다'). 캐시 없으면 빈 맵 — 참여도 0으로 무해 폴백."""
    m = {}
    for platform in ("instagram", "youtube", "tiktok"):
        try:
            items, _ = store.load_last_run_platform(platform)
        except Exception:
            continue
        for it in items or []:
            sc, c = it.get("shortcode"), it.get("comments")
            if sc and len(str(sc)) >= 5 and c is not None:
                m[str(sc)] = c
    return m


def _backbone_meta_from_job(job, extracts, store=None):
    """job의 urls + extracts 키(s0/s1/s2 순서)로 백본 선정용 meta 구성.
    → {video_id: {'platform': ..., 'comments': ...}}. 백본=인스타/유튜브 규칙 + 참여도(댓글수,
    2026-07-22 페이블 — 그전엔 comments 미배선이라 score_backbones의 참여도 0.4가 죽어 있었다).
    ⚠️ get_mix_job은 'urls'(list) 키로 준다 — 예전 'urls_json' 접근은 항상 빈 값이라
    플랫폼 규칙이 통째로 죽어 있었다(2026-07-22 수정)."""
    from shopping_shorts import backbone as _bb
    urls = _job_urls(job)
    eng = _engagement_map(store) if store is not None else {}
    meta = {}
    for i, key in enumerate(extracts.keys()):
        url = urls[i] if i < len(urls) else ""
        m = {"platform": _bb.platform_of(url)}
        for sc, c in eng.items():
            if sc in url:                      # url에 shortcode 포함(인스타/유튜브 공통)
                m["comments"] = c
                break
        meta[key] = m
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


def _record_bank_usage(store, snapshot, bank_context, rec, candidates,
                       sample_n=10, cap=50, call=None):
    """생성 순응 검열 레코드 1건을 만들어 링버퍼에 쌓고 집계를 저장한다(부가 관측, 실패 무해).
    은행 주입 job 중 sample_n에 1편만 제미니 순응 채점(counter % N == 1)."""
    from shopping_shorts import bank_usage_audit, bank_compliance
    plan = (rec or {}).get("plan") or {}
    story = (rec or {}).get("story") or {}
    conf = bank_usage_audit.structural_conformance(plan, snapshot, story)
    jsnap = bank_usage_audit.judge_snapshot(candidates)
    compliance = None
    if not snapshot.get("empty"):
        counter = 0
        try:
            counter = int(store.get_setting("bank_compliance_counter", "0") or "0")
        except (TypeError, ValueError):
            counter = 0
        counter += 1
        store.set_setting("bank_compliance_counter", str(counter))
        if counter % sample_n == 1:
            if call is None:
                from shopping_shorts import pattern_bank
                call = pattern_bank._default_call
            compliance = bank_compliance.judge_compliance(bank_context, plan.get("beats"), call)
    record = {"snapshot": snapshot, "conformance": conf, "judge": jsnap, "compliance": compliance}
    recent = store.append_bank_usage(record, cap=cap)
    import json as _json
    agg = bank_usage_audit.compute_usage_audit(recent)
    store.set_setting("bank_usage_audit_last", _json.dumps(agg, ensure_ascii=False))


_MAX_REPICK = 3
# 재픽으로 고칠 수 있는 위반의 신호어(생성 영역=길이·비트수는 제외). plan_gate가 내는
# 사람이 읽는 위반 문자열에 이 조각이 들어있으면 재픽 대상으로 본다.
_REPICKABLE_HINTS = ("이어지는 구간", "같은 장면", "잘게 쪼개진", "1개만 사용", "믹스가 안")


def _has_repickable(gate):
    return any(any(h in v for h in _REPICKABLE_HINTS) for v in (gate.get("violations") or []))


def _run_gate_correction(plan, source_scripts, target_seconds):
    """게이트 검사→재픽 루프. 위반이 재픽 가능하면 통과할 때까지 재픽(상한 _MAX_REPICK).
    재픽이 무변화면 즉시 종료(수렴). 최종 gate를 plan["gate"]에 항상 저장 —
    프론트가 역할별로(관리자=경고/일반=숨김) 표시한다. 순수·무과금·나레이션 불변."""
    pool_ct = len({s.get("video_id") for s in (source_scripts or [])
                   if s.get("segments")} - {None})
    beats = plan.get("beats")
    gate = plan_gate.check_plan(beats, target_seconds, pool_video_count=pool_ct)
    rounds = 0
    while rounds < _MAX_REPICK and _has_repickable(gate):
        new_beats = backbone.repick_for_gate(beats, source_scripts, gate)
        if new_beats == beats:
            break   # 더 못 고침 → 종료(잔여 위반은 §4 마감이 처리)
        beats = new_beats
        rounds += 1
        gate = plan_gate.check_plan(beats, target_seconds, pool_video_count=pool_ct)
    plan["beats"] = beats
    plan["gate"] = gate
    plan["repick_rounds"] = rounds
    if not gate["ok"]:
        print("plan_gate 잔여 위반(재픽 %d회 후): " % rounds
              + " / ".join(gate["violations"]), file=sys.stderr)


def _plan_and_tts(store, job_id, source_scripts, target_seconds, structure, video_type, work,
                  given_script=None, voice=None, customer_id=0,
                  scene_first=False, reference_text="", ping_pong=False,
                  backbone_meta=None, backbone_forced=None, backbone_base=False,
                  global_pron=None):
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
    # 소스 다수결이 레시피면 화면을 요리 시간순으로 재배치(장면 결 맞춤) — build_edit_plan 경로에 전달.
    is_recipe = _sources_is_recipe(source_scripts)
    _rec_cands = None   # 후보목록(카드) — conform 뒤 재저장해 카드=TTS 일치시키려고 잡아둔다
    if scene_first:
        from shopping_shorts.edit_plan import build_scene_first_plan
        # 부품은행 주입(P0-2): 설정 bank_enabled=1일 때만 승인 훅·어미·부사·CTA·스파인을 조립해
        # 영상 대본 프롬프트에 실어준다. 기본 off → 회귀0. 매 job 상위 perf 풀에서 로테이션
        # 샘플되므로(P0-1) 영상마다 다른 훅으로 열린다. 조립 실패는 조용히 무주입(부가기능).
        bank_context = ""
        avoid_hooks = None
        bank_snapshot = None        # ← 생성 순응 검열용 주입 스냅샷
        if store.get_setting("bank_enabled", "") == "1":
            try:
                from shopping_shorts import bank_assemble
                # 2026-07-27: 은행 '창의적 우수 라인'만(parts_block=승인 훅·부사·어미·CTA 감각) 재주입.
                # 제외: spine(A 백본 흐름이 대신)·winners few-shot(타제품 소재 오염)·avoid novelty
                # (매번 제품에서 밀어내던 드리프트 주범). parts는 프롬프트에서 '양념(참고·변형)'으로 쓴다.
                bank_context = bank_assemble.parts_block(store)
                bank_snapshot = bank_assemble.bank_usage_snapshot(store, video_type or "")  # 생성 순응 검열용
                avoid_hooks = None    # novelty OFF — 회피 감점 제거(드리프트 차단)
            except Exception:
                traceback.print_exc(file=sys.stderr)
        sf = build_scene_first_plan(source_scripts, reference_text, target_seconds,
                                    video_type=video_type, ping_pong=ping_pong,
                                    backbone_meta=backbone_meta, backbone_forced=backbone_forced,
                                    bank_context=bank_context, avoid_hooks=avoid_hooks,
                                    backbone_base=backbone_base,
                                    # 심사위원(대본품질·장면싱크·스토리라인)으로 best-of-N 선택.
                                    # ★2026-07-23: 은행/핑퐁이 켜진 스마트 경로면 항상 심사한다
                                    # (예전엔 backbone_base일 때만이라, 서버에 backbone_base 미설정 →
                                    # 심사가 통째로 꺼져 제일 탄탄한 후보를 못 골랐다. 사장님 지적).
                                    judge=(backbone_base or ping_pong
                                           or store.get_setting("bank_enabled", "") == "1"),
                                    # 주경로 앵커 dedup+레시피 grain 발동(Task8) — is_recipe는
                                    # 위(603줄)서 소스 다수결로 이미 계산됨.
                                    is_recipe=is_recipe)
        if sf["candidates"]:
            store.set_mix_candidates(job_id, sf["candidates"])
            _rec_cands = sf["candidates"]   # conform 뒤 재저장용(카드=TTS 일치)
            rec = next((cand for cand in sf["candidates"] if cand["recommended"]),
                       sf["candidates"][0])
            plan = rec["plan"]
            plan["generator"] = "scene_first"   # ★P1: 어느 생성기가 만들었나(조용한 폴백 금지)
            # 주입 미리보기(2026-07-23): 이 대본에 실제로 들어간 은행 블록을 plan에 실어 리뷰
            # 화면이 '은행이 뭘 댔나'를 눈으로 검증하게 한다(빈 문자열이면 은행 미주입).
            if bank_context:
                plan["bank_injected"] = bank_context
            # novelty(P0-3) 기록: 채택된 대본의 훅·인물·CTA를 남겨 다음 영상이 회피하게 한다.
            # 스위치 무관하게 항상 기록(데이터가 쌓여야 켰을 때 즉시 효과) — 실패해도 job 안 죽인다.
            try:
                _st = rec.get("story") or {}
                store.record_script_usage(_st.get("hook", ""), _st.get("story_person", ""),
                                          _st.get("cta_keyword", ""))
            except Exception:
                traceback.print_exc(file=sys.stderr)
            # 생성 순응 검열(부가 관측, 실패해도 job 안 죽인다) — 은행이 켜졌던 job만
            if bank_snapshot is not None:
                try:
                    _record_bank_usage(store, bank_snapshot, bank_context, rec, sf["candidates"])
                except Exception:
                    traceback.print_exc(file=sys.stderr)
        else:
            # ★P1(2026-07-24): scene_first가 실패하면 예전엔 **조용히** 옛 생성기로 넘어가
            # 개선(30초·7~8컷·대화·은행훅)이 안 탄 대본이 나왔고, 사장님은 "고쳤는데 왜 그대로냐"로
            # 겪었다(실측: 503 과부하 → 후보 0 → 폴백). 이제 폴백을 표식으로 남겨 화면에 띄운다.
            print("scene_first 후보 0 → 옛 생성기로 폴백(개선 미적용)", file=sys.stderr)
            plan = build_edit_plan(source_scripts, target_seconds, structure=structure,
                                   video_type=video_type, given_script=given_script,
                                   is_recipe=is_recipe)
            plan["generator"] = "legacy_fallback"
            plan["generator_note"] = "장면우선 생성이 실패해 예전 방식으로 만들었습니다(개선 미적용) — 다시 매칭을 권장합니다."
    else:
        plan = build_edit_plan(source_scripts, target_seconds, structure=structure,
                               video_type=video_type, given_script=given_script,
                               is_recipe=is_recipe)
        plan["generator"] = "legacy"
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
    _synthesize_beats(plan["beats"], work / "tts", voice=voice, global_pron=global_pron)

    # 4.2) 프리즈 뿌리 fix(2026-07-21) — 화면을 **실 TTS 길이**만큼 재보정한다. fill은 plan
    # 시점에 나레이션 추정(글자÷5.7)으로 채웠는데, 빠른 보이스면 실제 TTS가 추정과 달라 생긴
    # 틈을 렌더가 프리즈/슬로우로 때워왔다(두더지잡기의 뿌리). 실 tts_dur보다 화면이 짧은
    # 비트만 같은 소스 우선 B롤로 더 채운다 → 렌더가 정지 대신 실영상으로 채운다.
    _refill_beats_to_tts(plan["beats"], source_scripts, work / "tts")

    # 4.5) 싱크 콘폼(2026-07-20) — 대사가 영상 예산을 넘는 비트만 압축 리라이트 + 그 비트 재TTS.
    # 저장(아래) 전에 돌므로 preview·final 렌더 모두 자동 적용. 실패해도 job을 죽이지 않는다.
    try:
        _conform_beats(plan["beats"], work / "tts", voice=voice, global_pron=global_pron)
    except Exception:
        traceback.print_exc(file=sys.stderr)

    # 4.9) ★게이트 교정 루프(2026-07-25) — 최종 plan(refill·conform 뒤)을 보고 위반이면
    # 통과할 때까지 재픽(상한 3). 경고만 하던 관문을 '통과시키는 관문'으로. 순수·무과금·
    # 나레이션 불변. 실패해도 job은 안 죽인다(순수 계산).
    try:
        _run_gate_correction(plan, source_scripts, target_seconds)
    except Exception:
        traceback.print_exc(file=sys.stderr)

    # ★카드=TTS 일치(2026-07-27 실사고 "대본이랑 TTS가 다르게 나온다"): 추천 후보는 위에서
    #   _conform_beats/_refill로 나레이션이 재작성됐는데, candidates_json(카드가 읽는 것)은
    #   conform 전 스냅샷이라 카드 대본과 실제 말하는 TTS가 어긋났다. plan은 추천후보 plan과 같은
    #   객체(in-place 변경 반영)이므로 후보목록을 다시 저장해 카드가 '실제 말할 문장'을 보이게 한다.
    if _rec_cands:
        store.set_mix_candidates(job_id, _rec_cands)
    store.update_mix_job(job_id, edit_plan=plan, status="ready_for_review")


def retype_mix_job(job_id, video_type, db_path, work_root):
    """사용자가 감지된 영상 유형을 바꾸면, 저장된 extract로 EDL+TTS만 재생성한다
    (재다운로드·재추출 없음 — 방식3의 '확인/변경' 경로, 설계 §3-6)."""
    store = Store(db_path)
    _gpron = pron_corrections.load(store)
    job = store.get_mix_job(job_id)
    if not job or not job.get("extract"):
        return  # 추출 캐시 없으면 재생성 불가
    work = Path(work_root) / job_id
    try:
        source_scripts = list(job["extract"].values())
        _plan_and_tts(store, job_id, source_scripts, job["target_seconds"],
                      job["structure"], video_type, work, given_script=job.get("given_script"),
                      voice=job.get("voice"), customer_id=job.get("customer_id", 0),
                      global_pron=_gpron)
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        store.update_mix_job(job_id, status="failed", error=str(e))
        # 🎁 무료체험: 재타이핑(유형 변경 후 EDL+TTS 재생성)이 실패해도 체험 1회를 돌려준다.
        #   run_render 실패 환불과 대칭 — 체험자가 재타이핑 실패로 유일한 1회를 잃고 잠기는 걸 막는다.
        #   유료(render_charge_day=날짜)는 미환불(기존 동작). usage_decr는 0 밑으로 안 가 이중환불 안전.
        if job.get("render_charge_day") == "trial":
            _refund_render_charge(store, job.get("customer_id", 0), "trial")


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
    """소스 하나를 VMake로 청소 → (video_id, 클린경로, 지워진자막박스|None). ThreadPool 워커용(DB 미접근).
    청소 직후 원본↔클린을 diff해 '어디가 지워졌나'를 그 자리에서 구한다 — VMake는 좌표를 안 주지만
    우리가 before/after를 둘 다 쥐고 있어 계산 가능하다(best-effort, 실패해도 None으로 청소는 성공)."""
    vid, src = item
    out = str(Path(work) / f"clean_src_{vid}.mp4")
    clean_path = remove_subtitles(src, key, out_path=out)
    region = sub_region.detect_erased_region(src, clean_path, work)
    return vid, clean_path, region


def _ensure_clean_sources(store, job, job_id, work, key):
    """clean_sources 맵을 채워 반환. 이미 있고 파일이 존재하면 스킵(재과금 0).
    각 스레드는 remove_subtitles만 하고 경로를 반환 → DB 저장은 취합 후 메인에서 1회(경합 없음)."""
    source_map = _resolve_sources(job, Path(work))
    cached = dict(job.get("clean_sources") or {})
    # 지워진 자막영역: 소스별 박스 맵 + 1등(primary). 이미 있으면 이어붙인다(재청소 안 한 소스는 유지).
    regions = dict((job.get("clean_regions") or {}).get("sources") or {})
    todo = [(vid, src) for vid, src in source_map.items()
            if not (cached.get(vid) and Path(cached[vid]).exists())]
    if todo:
        with ThreadPoolExecutor(max_workers=len(todo)) as ex:
            for vid, out, region in ex.map(lambda t: _clean_one(t, key, work), todo):
                cached[vid] = out
                if region:
                    regions[vid] = region
                else:
                    regions.pop(vid, None)   # 이 소스엔 지속 변화 없음(원본에 자막 없었음)
        # 넓고 자주 쓰인 위치를 1번으로 — 소스마다 자막 위치가 달라도 대표 한 자리를 고른다.
        primary = sub_region.pick_primary(list(regions.values()))
        store.update_mix_job(job_id, clean_sources=cached,
                             clean_regions={"sources": regions, "primary": primary})
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
        # burn_captions=False — 이 조립본은 '자막 없는 clean 배경'(썸네일용)이다. 우리 나레이션
        # 자막을 구우면 썸네일 배경에 글자가 박혀 그 위에 제목을 얹을 수 없다(2026-07-22 사장님
        # 제보: clean_preview.mp4에 나레이션 자막이 박혀 나왔다). 원본 자막은 clean_map(자막제거
        # 소스)이 이미 없앴고, 여기선 우리 자막만 생략한다. 캡션 패스가 빠져 더 빠르기도 하다.
        assemble(plan, tts_paths, clean_map, str(out_path), clean_fn=None, deco={},
                 cutaway_paths=_resolve_cutaway_paths(store, plan, job.get("customer_id", 0)),
                 sfx_paths=_resolve_sfx_paths(store, plan, job.get("customer_id", 0)),
                 burn_captions=False)
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
                                 clean_error="AI 자막 제거 설정이 완료되지 않았습니다 (관리자 문의)")
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
    _gpron = pron_corrections.load(store)
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
        _synthesize_beats(plan["beats"], work / "tts", voice=job.get("voice"), skip_existing=True,
                          global_pron=_gpron)
        store.update_mix_job(job_id, edit_plan=plan)
        tts_paths = {b["beat_idx"]: b["tts_path"] for b in plan["beats"] if b.get("tts_path")}
        source_video_paths = _resolve_sources(job, work)
        out_path = work / "preview.mp4"
        # headcopy·caption_style은 **넘기지 않는다**(스펙 §9: 꾸미기 제외 / caption_style 기본값만).
        # headcopy는 store.py 주석대로 "영상제작 5단계 꾸미기 헤드카피"라 deco={}로 꾸미기를
        # 뺐다면서 헤드카피를 넘기는 건 자기모순이었다. assemble의 기본값이면 우리 자막은 정상으로
        # 굽힌다(라이브 관측: caption_style=None인 job으로 렌더해 자막 정상 확인).
        # ★미리보기는 veryfast로 인코딩(6분→~1.5분) — 확인용이라 화질 조금 낮아도 무방.
        # 최종 렌더(run_render)는 이 컨텍스트 밖이라 medium 고화질 그대로.
        with preview_preset():
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
    _gpron = pron_corrections.load(store)
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
        _synthesize_beats(plan["beats"], work / "tts", voice=job.get("voice"), skip_existing=True,
                          global_pron=_gpron)
        store.update_mix_job(job_id, edit_plan=plan)
        tts_paths = {b["beat_idx"]: b["tts_path"] for b in plan["beats"] if b.get("tts_path")}
        source_video_paths = _resolve_sources(job, work)
        out_path = work / "final.mp4"

        # 자막제거: 소스 원본을 미리(2단계) 또는 여기서(버튼 미사용 시) 청소해 그 소스로 조립한다.
        # mix_raw 위 clean_fn(구방식)은 폐기 — 소스단위여야 TTS/컷과 무관하게 캐시가 성립한다.
        if job.get("subtitle_removal"):
            key = _vmake_key(store)
            if not key:
                raise RuntimeError("자막 제거가 켜져 있으나 설정이 완료되지 않았습니다 (관리자 문의)")
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
        # 🎁 무료체험 이벤트: 최종 렌더(자막제거·조립)가 실패하면 체험 1회를 돌려준다(재도전 가능).
        #   과금은 /api/mix/start(run_mix_job 단계)에서 한 번뿐이고 최종렌더는 같은 job의 뒷단계라,
        #   run_mix_job이 성공해 여기까지 온 체험 job은 실패해도 환불이 안 됐다 → 여기서 메운다.
        #   유료(render_charge_day=날짜)는 기존 동작 유지(미환불) — 체험 한정.
        if job.get("render_charge_day") == "trial":
            _refund_render_charge(store, job.get("customer_id", 0), "trial")


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
    # 이 mp3는 최종 렌더가 skip_existing으로 재사용하므로, 전역 발음교정을 여기서도
    # 적용해야 재합성한 비트만 교정이 빠지는 일이 없다(Task2 리뷰 Important).
    try:
        synthesize_line(
            beat["narration"], out, voice=voice_override, beat_role=beat.get("role"),
            beat_index=i, beat_total=total,
            previous_text=plan["beats"][i - 1]["narration"] if i > 0 else None,
            next_text=plan["beats"][i + 1]["narration"] if i < total - 1 else None,
            global_pron=pron_corrections.load(store),
        )
        beat["tts_path"] = str(out)
        beat["voice_override"] = voice_override
        beat["cap_durs"] = None
        # ★probe를 밖으로 뺐으니 예외를 흡수해야 한다 — 예전엔 words가 있을 때만 불렸다.
        #   길이를 몰라도(None) 되맞춤만 건너뛰고 나머지는 그대로 돈다.
        try:
            _rdur = _probe_duration(str(out))
        except Exception:      # noqa: BLE001 — 길이 측정 실패로 재합성을 죽이지 않는다
            _rdur = None
        words = _beat_words(str(out), _rdur)
        if words:
            beat["cap_durs"] = caption_sync.phrase_durs_from_words(
                beat["narration"], words, _rdur or 0.0,
                preset=beat.get("caption_lines"))
        # 완료 신호: 단조 증가 버전. 프론트가 이 값 변화를 폴링해 '재합성 끝'을 안다
        # (mp3는 같은 경로/URL이라 겉으론 구분이 안 되므로 — 고정 4초 추측을 이 신호로 대체).
        beat["tts_ver"] = (beat.get("tts_ver") or 0) + 1
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
        _synthesize_beats(plan["beats"], work / "tts", voice=job.get("voice"),
                          global_pron=pron_corrections.load(store))
        store.update_mix_job(job_id, edit_plan=plan, status="ready_for_review")
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        store.update_mix_job(job_id, status="failed", error=str(e))
