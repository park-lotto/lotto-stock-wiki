"""믹스 job 백그라운드 오케스트레이션(설계 §2·§5).

run_mix_job: 다운로드→대본추출(병렬)→EDL생성→TTS까지 진행하고 ready_for_review로.
run_render: 사용자가 확인 후 최종 ffmpeg 렌더 → done.
각 단계에서 mix_jobs.status를 갱신하고, 예외는 status='failed'+error로 잡는다.
"""
import hashlib
import os
import json
import logging
import re
import shutil
import subprocess
import sys
import time
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
from shopping_shorts import typecast_tts
from shopping_shorts import audio_post
from shopping_shorts import config
from shopping_shorts import usage_meter
from shopping_shorts import single_source
from shopping_shorts import script_lang
from shopping_shorts.video_assemble import assemble, _beat_timeline, _beat_material, _probe_duration, _MAX_SLOWMO, preview_preset
from shopping_shorts.video_assemble import prepend_still
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


def _beat_words(mp3_path, dur=None, removed=None):
    """자막 싱크용 단어 타임스탬프. TTS가 준 것을 먼저 쓰고, 없으면 ASR로 폴백한다(2026-07-31).

    ①TTS 타임스탬프 — 우리가 보낸 원문 그대로의 시각이라 맞출 대상이 없다(정렬 실패 없음).
    ②ASR 폴백 — 옛 경로. ELEVENLABS_TIMESTAMPS를 끄거나, 그 엔드포인트가 죽었거나,
      키 없는 무음 mock일 때 여기로 온다. 폴백을 남겨두는 이유는 그 세 경우에도
      자막이 글자수 추정으로 떨어지지 않게 하기 위해서다.
    ★asr_check를 모듈 속성으로 부른다 — 테스트가 mix_pipeline.asr_check를 monkeypatch 한다.

    removed: 후처리가 잘라낸 무음 구간(원본 타임라인). 주면 rescale이 조각별로 갚는다
    — 속도감 모드 내부 무음 제거는 선형사상으로 못 맞춘다(2026-08-06).
    """
    return _beat_words_src(mp3_path, dur, removed)[0]


def _beat_words_src(mp3_path, dur=None, removed=None):
    """_beat_words + **어느 단에서 나온 시각인지**(2026-08-29 설계 ⑦a).

    "precise"  TTS가 준 정밀 타임스탬프(사이드카) — 정렬 실패 없음
    "asr"      받아쓰기 폴백 — 오인식만큼 오차
    "estimate" 둘 다 실패(None) — 하류가 글자수 비례로 떨어진다

    폴백 사다리는 지금까지 **조용히** 내려가서, 어긋난 작업물을 보고도 어느 단이
    범인인지 알 길이 없었다. 산출 단계를 beat["cap_src"]로 남겨 화면에 띄운다."""
    words = tts_timestamps.words_from_mp3(mp3_path)
    if words:
        # 합성 뒤 audio_post가 배속·무음트림으로 파일을 고쳤을 수 있다 → 최종 길이로 되맞춤.
        return tts_timestamps.rescale(words, dur, removed=removed), "precise"
    w = asr_check.transcribe_words(mp3_path)
    return w, ("asr" if w else "estimate")


def _source_video_id(i):
    return f"s{i}"


# URL → 캐시 키(shortcode). script_extracts는 **shortcode**로 저장된다(담기·AI PICK·
# prewarm 전부 그렇다). 반면 믹스 파이프라인 안에서 소스를 부르는 이름은 "s0"·"s1"이라,
# 그걸로 캐시를 찾으면 **영원히 빗나간다**.
#   ★2026-08-06 실사고: 캐시 재사용 코드(2026-07-24)가 `store.get_extract(vid)`로 vid="s0"을
#   넘겨 **한 번도 적중한 적이 없었다**. 라이브 확인 — 저장된 추출 408건, 그 중 그 영상의
#   캐시도 조건까지 충족(segments 12개·seg_id 전부·change 필드 있음)인데 매번 Gemini로
#   재전사했다(실측 job ff3921a9ae4c: 작업 118초 중 85초가 다운로드+재추출).
_SHORTCODE_RES = (
    re.compile(r"instagram\.com/(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)"),
    re.compile(r"(?:youtube\.com/shorts/|youtu\.be/|youtube\.com/watch\?v=)([A-Za-z0-9_-]+)"),
    re.compile(r"tiktok\.com/(?:@[^/]+/video/|v/)(\d+)"),
)
# 위 정규식과 짝을 이루는 플랫폼 이름 — 렌즈 경로가 저장한 키의 접두사를 만들 때 쓴다.
# ★반드시 _SHORTCODE_RES와 같은 순서·같은 길이여야 한다(짝으로 움직이는 값, 0순위-B).
_SHORTCODE_PLATFORMS = ("instagram", "youtube", "tiktok")


def _cache_key_for_url(url):
    """이 URL의 script_extracts 캐시 키(shortcode). 못 알아내면 None."""
    for rx in _SHORTCODE_RES:
        m = rx.search(url or "")
        if m:
            return m.group(1)
    return None


def _cache_keys_for_url(url):
    """이 URL로 저장돼 있을 수 있는 캐시 키 **후보 전부**(앞에 올수록 우선).

    ★왜 하나가 아닌가(2026-08-17 실측): 같은 영상이 경로에 따라 다른 키로 저장된다.
      담기 경로  → `7458060642738605355`      (URL에서 뽑은 ID 그대로)
      렌즈 경로  → `lens_tiktok_7458060642738605355`  (플랫폼 접두사가 붙는다)
    조회는 앞의 형태만 찾아서, **틱톡 소스는 캐시에 있는데도 한 번도 안 맞았다**
    (실측 job 8873eeb48a08: 인스타 1건 적중 / 틱톡 2건 불발. 두 틱톡 모두 DB에
    label 10·use_point 10·source_brief까지 갖춘 채 `lens_tiktok_…` 키로 있었다).
    그 결과 재태깅을 해도 대본 쪽은 옛 재료를 보고, 매번 Gemini로 다시 뽑았다.

    ⚠️ 렌즈 경로엔 짧은 해시 키(`lens_tiktok_1jw6i6i`)도 있는데 그건 URL에서
    만들어낼 수 없다 — 그래서 **DB에 적힌 것을 먼저 읽는다**(아래 store 조회).

    ★★2026-08-17 실측 — 정규식만으로는 플랫폼이 통째로 빠진다.
      `_SHORTCODE_RES`에 인스타·유튜브·틱톡 셋뿐이라 **도우인·샤오홍슈는 키가 0개**였다.
      담긴 394건 중 55건(도우인 8·샤오홍슈 47 = 14%)이 여기 해당한다. 그 결과
      고독스 C100(`grab_douyin_b26e5b24ee36`)은 상세4·리뷰8까지 긁어 저장해뒀는데도
      `product_facts_…`를 **한 번도 못 찾아** 대본에 재료가 안 실렸다.
      저장은 DB의 shortcode 그대로(`grab_douyin_…`), 조회는 URL 추론 — 같은 판단을
      두 군데서 다르게 내린 것이다(0순위-B). 그래서 **추론 전에 적힌 것을 읽는다**.
      플랫폼이 늘어도 여기를 다시 안 고쳐도 된다 = 썩지 않는다.
    """
    keys, seen = [], set()

    def _add(k):
        if k and k not in seen:
            seen.add(k)
            keys.append(k)

    # ① DB에 저장된 shortcode 우선 — 담기·위키가 URL과 짝으로 적어둔 값이다.
    #    추론으로는 절대 못 만드는 키(grab_douyin_…·lens_tiktok_1jw6i6i)가 여기서 나온다.
    try:
        # ⚠️ DB 경로는 config에서 — app에서 가져오면 app→mix_pipeline 순환 import가 된다.
        from shopping_shorts.config import DB_PATH
        from shopping_shorts.store import Store
        for sc in Store(DB_PATH).shortcodes_for_url(url):
            _add(sc)
    except Exception:      # noqa: BLE001 — 캐시 조회 실패가 파이프라인을 막으면 안 된다
        pass               #    (못 찾으면 아래 추론 + 종전대로 재추출로 간다)

    # ② URL 추론 폴백 — DB에 기록이 없는 경로(위키 직행 등)도 종전대로 맞힌다.
    for rx, plat in zip(_SHORTCODE_RES, _SHORTCODE_PLATFORMS):
        m = rx.search(url or "")
        if m:
            code = m.group(1)
            _add(code)
            _add(f"lens_{plat}_{code}")
            break
    return keys


# 성우 미선택(2단계 미리보기 등) 기본 성우 = 미나·표현(kr-mina-expressive, 2026-07-25 사장님 확정).
# 예전 기본은 config.ELEVENLABS_VOICE_ID(Rachel=영어 성우)라 성우를 고르기 전 미리보기가
# 영어 성우로 한국어를 읽었다. 값은 assets/voice_presets.json의 kr-mina-expressive 스냅샷.
_DEFAULT_VOICE = {
    "preset_id": "kr-mina-expressive",
    "voice_id": "aiUUgjHa4mpHf6UenZuf",
    "model_id": "eleven_v3",
    "settings": {"stability": 0.35, "similarity_boost": 0.78, "style": 0.4},
    # ★1.4 (2026-08-22 사장님 지시 — 2.2는 실제로 들어보니 말도 안 되게 빨랐다).
    #   ⚠️아래 "메종 8.45자/초"는 **자막 글자수 ÷ 영상 길이**로 낸 값이라
    #     사람이 말하는 속도가 아니다(무음·화면전환·자막만 있는 구간이 섞였다).
    #     그 값을 TTS 배속 목표로 삼은 것이 잘못이었다. 재측정 전까지 참고만 할 것.
    #   [옛 근거 — 검증 실패]
    #   메종 23.8초·193자·**8.45자/초** ← 사장님이 "밀도·시간 다 맞다"고 지목한 채널.
    #   우리는 1.6에서 6.46자/초라 히트작 하위10%(6.72)보다도 느렸다 — 같은 25초에
    #   메종보다 49자 적게 말한다 = "말이 빈다". 배속 샘플 실측(렌더와 같은 경로):
    #   1.6→6.51 · 1.8→7.26 · 2.0→7.66 · **2.2→8.75자/초**(메종과 일치).
    #   ⚠️길이는 글자를 줄여서 맞추면 안 된다 — 그러면 말이 비는 쪽으로 되돌아간다.
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

    ⚠️ pace_mode의 '기본'은 두 층이다(2026-08-10 정정 — 이 설명이 틀려 있었다):
      · voice 스냅샷에 키가 있으면 그 값
      · 스냅샷이 없거나 비었으면 **_DEFAULT_VOICE로 폴백** → 거기 pace_mode=True(2026-07-25~)
    즉 `_voice_params({})[7]`은 False가 아니라 True다. 기본값을 알고 싶으면
    _DEFAULT_VOICE를 보라 — 여기 적힌 `v.get(..., False)`만 보고 판단하면 틀린다.

    스냅샷은 /api/mix/voice가 프리셋에서 통째로 복사해 넣는다 — naturalize_profile·model_id가
    빠지면 튜닝 작업대에서 동결한 값이 렌더에 도달하지 못한다(2026-07-15 whole-branch 리뷰 S1/S8)."""
    v = voice or _DEFAULT_VOICE
    speed = v.get("speed", 1.0)
    model_id = v.get("model_id") or "eleven_v3"
    # ★타입캐스트는 API가 tempo 0.5~2.0을 직접 받는다(2026-08-19). 일레븐랩스처럼
    #   1.2 초과분을 후처리 atempo로 또 당기면 **이중 가속**이 된다(1.6배가 2.1배로
    #   들린다). 엔진 판정은 typecast_tts.is_typecast 한 곳만 쓴다(0순위-B).
    if typecast_tts.is_typecast(model_id):
        extra_tempo = 1.0
    else:
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
                    ranker=asr_ranker, global_pron=None, customer_id=0):
    """한 줄을 naturalize→TTS(N-best·연속성)→후처리까지 합성하고 변환텍스트를 반환.

    **튜닝 작업대와 실제 렌더가 공유하는 단일 경로**다. 양쪽이 각자 파이프라인을 조립하면
    인자가 갈려 "작업대에서 들은 소리 ≠ 영상 소리"가 된다(2026-07-15 리뷰 S3/S4/S5/S6).
    새 호출부를 만들지 말고 이 함수를 쓸 것.

    profile 미지정 시 voice 스냅샷의 naturalize_profile을 쓴다. seed/n_best는 merge_profile을
    거친 값으로 읽어 텍스트와 오디오가 같은 기준을 보게 한다(S10).

    customer_id: **누구 키로 합성하나**(2026-08-24). 0=사장님 키(기존 동작 그대로).
    하류는 이미 다 뚫려 있었다 — synthesize_best(**kw)가 그대로 넘기고
    synthesize_tts→tts._api_key→keyroute.keys_for가 받는다. 여기만 안 받아서
    회원이 일레븐랩스 키를 등록해도 항상 사장님 키로 돌았다(keyroute.py 주석 참조)."""
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
                        model_id=model_id, previous_text=previous_text, next_text=next_text,
                        customer_id=customer_id)
    # ★무음 제거 '전에' 어디를 자를지 재서 사이드카에 남긴다(2026-08-06). post_process는
    # 제자리 덮어쓰기라 뒤에는 원본 타임라인을 알 길이 없다. 이 구간들이 있어야 TTS
    # 타임스탬프를 조각별로 당겨 자막을 맞출 수 있다(선형사상으론 누적 드리프트가 남는다).
    # 반환값 대신 사이드카에 쓰는 이유: synthesize_line 호출부가 6곳이고 대부분 반환값을
    # 대사 텍스트로 쓴다 — 시그니처를 바꾸면 그 전부와 기존 스텁이 깨진다.
    if pace_mode:
        try:
            tts_timestamps.save_removed(str(out_path),
                                        audio_post.measure_removed_spans(str(out_path)))
        except Exception:
            pass                  # 측정 실패 = 선형 폴백(기존 동작), 렌더는 계속
    # 비트별 라우드니스 정규화는 **실제 음성일 때만** — 키 없는 개발용 무음 mock에
    # loudnorm을 걸면 무음 바닥을 노이즈로 끌어올린다(reference_local_tts_silent_mock_trap).
    # ★"실제 음성인가"는 그 비트가 쓰는 엔진의 키로 판정한다(2026-08-19). 종전엔
    #   ELEVENLABS_API_KEY만 봐서, 타입캐스트 성우로 뽑은 진짜 음성이 일레븐랩스 키가
    #   없다는 이유로 정규화를 건너뛰어 **혼자만 작게** 들렸다.
    #   ★2026-08-31: 키를 **그 job 주인 기준**으로 본다. 회원이 자기 타입캐스트 키를
    #   등록했으면 회사 키가 비어 있어도 진짜 음성이다 — customer_id를 안 넘기면
    #   회사 키만 보고 "무음 mock"으로 오판해 정규화를 건너뛴다.
    has_voice_key = (bool(typecast_tts.api_key(customer_id))
                     if typecast_tts.is_typecast(model_id)
                     else bool(config.ELEVENLABS_API_KEY))
    audio_post.post_process(str(out_path), str(out_path), tempo=extra_tempo,
                            silence_trim=trim, pace_mode=pace_mode,
                            loudnorm=has_voice_key)
    return natural


def _beat_tts_path(tts_dir, beat):
    """비트 TTS 파일 경로 — 파일명을 나레이션 '내용 해시'로 키잉한다(2026-07-27 실사고:
    B로 만들고 A로 바꾸면 자막은 A인데 음성은 B였다). 예전엔 beat_{idx}.mp3로 후보끼리
    파일명을 공유해, B 렌더가 그 파일을 B 음성으로 덮어쓴 뒤 A는 skip_existing으로 재합성을
    건너뛰어 B 음성을 그대로 재생했다. 내용 해시를 넣으면 대본이 다른 후보는 파일도 달라 절대
    안 섞이고(A는 A파일, B는 B파일), 같은 대본은 그대로 재사용(0원)된다."""
    key = hashlib.md5((beat.get("narration") or "").encode("utf-8")).hexdigest()[:10]
    return str(Path(tts_dir) / f"beat_{beat['beat_idx']}_{key}.mp3")


def tts_matches_narration(beat):
    """이 비트의 mp3가 **지금 대본**으로 만든 것이냐 — 어긋나면 False(2026-08-19 실사고).

    ★왜 필요한가: `beat["narration"] = ...` 를 하는 곳이 코드베이스에 20곳이 넘는다
      (edit_plan 12곳·single_source 6곳·backbone 2곳·mix_pipeline·app). 리라이터가
      하나 늘 때마다 "재합성도 같이 해라"를 사람이 기억하는 구조면 반드시 또 샌다.
      실제로 2026-07-27에 파일명 해시를 넣었는데도 2026-08-19에 같은 증상이 재발했다
      (잡 f8d373618c0f beat2: 대본은 '영양사 친구가 알려준…'인데 소리는
       '치즈와 우유에 계란까지 톡 까서 넣으면…' — 같은 초에 만들어진 형제 잡
       e7bf5dbccd04는 같은 대본으로 다른 파일명을 써서 대조로 확정했다).

    그래서 "기억"이 아니라 **판정**을 둔다. 판정 기준은 `_beat_tts_path` 하나뿐이므로
    파일명 규칙이 바뀌어도 두 벌이 되지 않는다(0순위-B).

    fail-open 두 가지 — 과잉 경보는 경보를 무의미하게 만든다:
      · tts_path 없음        = 아직 합성 전이다. 어긋남이 아니다.
      · 해시 없는 옛 이름     = 2026-07-27 이전 잡(beat_0.mp3). 판정 불가라 통과시킨다
                               (라이브 실측 758비트가 여기 해당 — 전부 빨개지면 아무도 안 본다).
    """
    tp = beat.get("tts_path")
    if not tp:
        return True
    name = Path(tp).name
    m = re.fullmatch(r"beat_(\d+)_([0-9a-f]{10})\.mp3", name)
    if not m:
        return True                     # 옛 비해시 이름 → 판정 불가(fail-open)
    return m.group(2) == hashlib.md5(
        (beat.get("narration") or "").encode("utf-8")).hexdigest()[:10]


def mismatched_beats(beats):
    """대본과 음성이 어긋난 비트 인덱스 목록 — 화면·로그가 근거로 쓴다."""
    return [b.get("beat_idx") for b in (beats or []) if not tts_matches_narration(b)]


def _synthesize_beats(beats, tts_dir, *, voice, skip_existing=False, global_pron=None,
                      customer_id=0):
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
            global_pron=global_pron, customer_id=customer_id,
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
        beat["cap_lead"] = 0.0
        _ensure_breath_lines(beat)   # 폴백 칸이면 Gemini 호흡 끊기(실패=규칙 폴백)
        words, _wsrc = _beat_words_src(str(out), _ad, removed=tts_timestamps.load_removed(str(out)))
        _timing = None
        if words:
            _timing = caption_sync.phrase_durs_from_words(
                beat["narration"], words, _ad or 0.0,
                preset=beat.get("caption_lines"))   # None일 수 있음 → 폴백
            if _timing:
                beat["cap_durs"] = _timing.durs
                beat["cap_lead"] = _timing.lead_in
        # 산출 단계 기록(⑦a) — 정렬까지 성공해야 그 단이다. 실패하면 글자수 추정.
        beat["cap_src"] = _wsrc if (words and _timing) else "estimate"

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


def _ensure_breath_lines(beat):
    """폴백 칸이면 Gemini 호흡 끊기로 caption_lines를 채운다(2026-08-29 사장님 "해봐").

    자연스러운 호흡은 문장 이해가 필요해 규칙(_caption_segments)의 마지막 10%가 안 닿는다
    — AI가 끊은 줄(caption_lines)이 있으면 규칙을 안 타므로, 없는 비트만 여기서 채운다.
    실패·무키·불일치는 조용히 None = 규칙 폴백(종전과 동일, 절대 죽이지 않는다).
    ⚠️같은 판단 두 곳 금지(0순위-B) — 재합성 경로 전부가 이 함수 하나를 거친다."""
    if beat.get("caption_lines"):
        return
    try:
        from shopping_shorts import script_generate
        beat["caption_lines"] = script_generate.ai_breath_lines(beat.get("narration"))
    except Exception:      # noqa: BLE001 — 호흡 끊기 실패로 합성을 죽이지 않는다
        traceback.print_exc(file=sys.stderr)


def invalidate_caption_meta(beat):
    """대본(narration)이 바뀌는 **모든 경로**가 반드시 부른다 — 옛 대본 기준의 자막 메타를 지운다.

    ★왜(2026-08-15 실사고, 잡 409f894230c6): cap_durs·cap_lead는 합성 시점에 한 번 계산되고
    그 뒤 무효화가 없었다. 대본 편집(app.py 후보선택 편집·자동 줄이기)이 narration만 바꾸고
    이 메타를 남겨서, 렌더가 옛 대본 기준 타이밍(구절 수 불일치 + 낡은 lead)으로 자막을 그려
    자막이 음성보다 늦게까지 남았다(칸1 자막끝 6.360 vs mp3 6.144).

    지우면 어떻게 되나: caption_lines은 정규식 분할 폴백, cap_durs는 글자수 비례 폴백,
    cap_lead 0.0 — 전부 **현재 대본** 기준이라 정확하진 않아도 어긋나진 않는다. 재합성 경로
    (_synthesize_beats·콘폼)가 돌면 ASR 실측으로 다시 채운다.

    ⚠️ 같은 판단을 두 군데 적지 마라(CLAUDE.md 0순위-B) — 새 편집 경로가 생기면 이 함수를 불러라."""
    beat["caption_lines"] = None
    beat["cap_durs"] = None
    beat["cap_lead"] = 0.0


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


def beat_screen_budget(beat):
    """비트의 화면 예산(초) = 재료 구간 길이 합 × _MAX_SLOWMO — **한 곳에서만** 계산(0순위-B).

    종전엔 _conform_beats와 app.py shorten이 같은 식을 따로 적고 있었다. ★장면실험실
    편성(scene_override, 2026-08-15)이 있으면 그 구간들이 재료다 — 트림(✂)으로 잘라낸
    구멍은 적용 시점에 이미 빠져 있으므로, 여기서 반영하지 않으면 없는 화면만큼 대본을
    길게 뽑는다(docstring "이 예산이 영상으로 채울 수 있는 최대"가 깨진다)."""
    segs = _beat_material(beat)
    return sum(max(0.0, float(s["end"]) - float(s["start"])) for s in segs if s) * _MAX_SLOWMO


def _conform_beats(beats, tts_dir, *, voice, global_pron=None):
    """싱크 콘폼 패스(2026-07-20 설계 T3) — 대사가 영상 예산을 넘는 비트만 표면 재단.

    예산 = beat_screen_budget(재료 구간 길이 합 × _MAX_SLOWMO — 실험실 편성·트림 반영).
    _plan_beat_clips가 세그먼트를
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
        # 예산은 공용 헬퍼 한 곳에서(0순위-B) — 실험실 편성·트림이 있으면 자동 반영된다.
        budget = beat_screen_budget(beat)
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
        # ★파일명은 **줄인 뒤의 대본**으로 짓는다(2026-08-19). 예전엔 해시 없는
        #   beat_{i}.mp3라 "어느 대본의 음성인지" 알 수 없었고, 그래서 대본이 또 갈려도
        #   tts_matches_narration이 판정을 못 해 어긋남이 조용히 통과했다.
        out = Path(_beat_tts_path(tts_dir, {**beat, "narration": new_n}))
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
        invalidate_caption_meta(beat)   # 대본 바뀜 → 옛 자막 메타 무효(아래에서 ASR로 재계산)
        beat["tts_path"] = str(out)
        new_dur = _probe_duration(str(out))
        # UI 표시 초 = 실제 발화초(빠른 보이스 speed까지 반영). 추정(글자÷5.7)은 speed를
        # 못 봐 오차가 커서 실측으로 둔다(2026-07-21). 실측 실패 시에만 추정 폴백.
        beat["target_seconds"] = round(new_dur, 1) if new_dur and new_dur > 0 \
            else round(max(1.5, len(new_n.strip()) / _SYLLABLES_PER_SEC), 1)
        words, _wsrc = _beat_words_src(str(out), new_dur, removed=tts_timestamps.load_removed(str(out)))
        _t = None
        if words:
            _t = caption_sync.phrase_durs_from_words(new_n, words, new_dur)
            beat["cap_durs"] = _t.durs if _t else None
            beat["cap_lead"] = _t.lead_in if _t else 0.0
        beat["cap_src"] = _wsrc if (words and _t) else "estimate"
        beat["sync_gap"] = round(max(0.0, new_dur - budget), 2)


# 추출이 영상의 이만큼도 구간화하지 못하면 '빈약'으로 본다(2026-07-31).
# 실측: 21초 영상이 2구간 7.4초(35%)로 나와 재료로 못 썼는데 화면엔 표시가 없었다.
# ★0.55 → 0.75 (2026-08-06). 55%는 **영상 절반이 날아가도 통과**시키는 기준이었다.
#   게다가 실측에서 실패값이 하필 정확히 55.0%(11.6/21.1=0.549)로 찍혀 경계에 걸렸다 —
#   재시도가 되기도 하고 안 되기도 하는 회색지대. 뒤쪽 대사가 통째로 빠지면 사장님
#   결과물이 11~16초로 짧아진다(원본 21초가 멀쩡히 있는데도). 같은 영상 5회 실측에서
#   95%도 나왔으므로 75%는 충분히 도달 가능한 기준이다.
_MIN_COVERAGE = 0.75
# 커버리지가 낮을 때 다시 뽑는 횟수. 편차가 커서(55~95%) 몇 번 더 뽑으면 좋은 게 나온다.
# 1회 추출이 20~30초라 무한정 늘릴 순 없다 — 3회면 실측 분포상 대부분 75%를 넘긴다.
_EXTRACT_RETRIES = 3


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


def _prepare_sources(urls, work, store=None):
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
        # ★기술 문구 앞에 '사람이 할 수 있는 말'을 붙인다(2026-08-19 총점검).
        #   원문은 지우지 않는다 — 디버깅에 필요하다.
        def _line(u, e):
            hint = _download_fail_hint(e)
            return f"· {u}: {hint} ({e})" if hint else f"· {u}: {e}"
        detail = "\n".join(_line(u, e) for u, e in skipped)
        # ★사람에게 밀어 올린다(2026-08-04). 08-03엔 이 실패가 조용히 DB에만 쌓여
        # 13:45부터 다음날까지 아무도 몰랐다. 소스를 하나도 못 받았다 = 통로가
        # 끊겼다는 뜻이고, 인스타는 이걸 한두 달 주기로 한다 — 즉시 알아야 한다.
        # 알림이 실패해도 아래 예외는 그대로 나간다(본작업 흐름 불변).
        try:
            from shopping_shorts import ops_alert
            ops_alert.raise_alert(
                "source_download",
                "소스 영상 다운로드가 전부 실패했습니다 — 수집 통로가 끊겼을 수 있습니다",
                detail, store=store)
        except Exception as _ae:      # noqa: BLE001 — 알림 실패가 본작업을 막지 않는다
            # ★사유는 남긴다(2026-08-19 F-2). 알림이 조용히 죽으면 "사고가 났는데
            #   아무도 모른다"가 되고, 그게 이 알림을 만든 이유(08-03 실사고)였다.
            print(f"[ops_alert] source_download 알림 실패(무해): {_ae!r}", file=sys.stderr)
        raise RuntimeError(
            "소스 영상을 하나도 못 받았습니다 — 모든 URL 다운로드 실패:\n" + detail)
    return video_paths, captions, skipped


# 이 비율을 넘어야 '가로형'으로 본다(2026-08-31). 1.0(= w>h)으로 재면 **1픽셀만 넓어도**
# 걸린다 — 실사고 cid110 job adb9eb74362e: 인스타 릴 736x718(1.025)이 "가로형(롱폼)"으로
# 막혔다. 18px 차이는 사람 눈엔 정사각이고 세로 화면에 넣어도 좌우가 잘리지 않는다.
# 원래 docstring도 "정사각은 가로형으로 치지 않는다"였는데 코드만 어긋나 있었다.
# 1.15는 실측 근거: 서버 script_extracts 399건에서 비율 1.0~1.5 구간은 0건이고
# 진짜 롱폼(1.78 등)만 3건이라, 문턱을 둬도 막아야 할 것은 그대로 막힌다.
LANDSCAPE_RATIO = 1.15


def is_landscape_wh(w, h):
    """(w,h) → 가로형인가. 못 재면 None. **판정은 여기 한 곳뿐이다(0순위-B).**

    화면(app.py source_brief의 `landscape`)과 실제 차단(_block_landscape)이 각자
    재면 "화면은 괜찮다는데 제작은 실패"가 난다. 그래서 둘 다 이 함수를 부른다.
    """
    if not (w and h):
        return None
    return (w / h) > LANDSCAPE_RATIO


def _is_landscape(path):
    """가로형인가 — 못 재면 None(모르면 막지 않는다).

    정사각(1:1)과 그 언저리는 가로형으로 치지 않는다. 세로 화면에 넣어도 위아래만
    남지 좌우가 잘려 나가지 않는다. 문턱은 LANDSCAPE_RATIO 참조.
    """
    try:
        w, h, _dur = _probe_wh_dur(path)
    except Exception:      # noqa: BLE001 — 못 재는 걸 막을 근거로 쓰지 않는다
        return None
    return is_landscape_wh(w, h)


def _block_landscape(video_paths, url_of=None):
    """가로형 소스가 하나라도 있으면 사람이 읽을 수 있는 사유로 실패시킨다.

    2026-08-27 실사고(job 6070eddd8a73): 세로 3편에 유튜브 롱폼 가로 4K 1편이 섞였다.
    붙임 캔버스가 그 한 편에 끌려가 세로 영상들이 가로로 늘어났고, 최종 세로 렌더에서
    크게 잘려 고객에겐 "원본은 일반영상인데 결과물이 줌한 것처럼 크다"로 보였다.

    비율 보존(_join_sources)은 그 왜곡을 없앴지만, **가로 영상 자체가 세로 숏폼에
    안 맞는다** — 세로 화면에 채우려면 좌우를 잘라내야 하고 그건 원본과 다른 그림이다.
    그래서 만들다 이상해지는 대신 **시작할 때 분명히 실패**시킨다(사장님 지시).
    """
    bad = []
    for vid, path in sorted((video_paths or {}).items()):
        if _is_landscape(path):
            try:
                w, h, _d = _probe_wh_dur(path)
            except Exception:      # noqa: BLE001
                w = h = 0
            bad.append((vid, (url_of or {}).get(vid, ""), w, h))
    if not bad:
        return
    lines = [f"· {u or vid} ({w}x{h} 가로)" for vid, u, w, h in bad]
    raise RuntimeError(
        f"가로형(롱폼) 영상이 {len(bad)}개 섞여 있어요 — 세로 숏폼으로 만들면 "
        "좌우가 잘려 원본과 다르게 확대된 것처럼 나옵니다. "
        "아래 영상을 빼고 다시 만들어 주세요:\n"
        + "\n".join(lines))


def _job_customer_id(db_path, job_id):
    try:
        job = Store(db_path).get_mix_job(job_id) or {}
        return job.get("customer_id")
    except Exception:      # noqa: BLE001 — 계측용이라 실패해도 본작업은 돈다
        return None


def _download_fail_hint(err_text):
    """다운로드 실패 원인 → **사람이 할 수 있는 말**(모르면 "").

    ★2026-08-19 총점검. 실측 28건의 실패 문구가 전부 기술 용어라 사장님은 무엇이
      잘못됐는지 알 수 없었다. 대표 예:
        yt-dlp 실패(rednote.com/search_result/689e…): Unsupported URL:
          https://www.rednote.com/404?source=/404/sec_PukRxsmn&redirectPath=…
      ← 주소가 잘못된 게 아니다(그 경로는 정상 담기 경로다, test_grab 참조).
        **404로 넘겨진 것** = 글이 지워졌거나 로그인벽에 막힌 것이다.
      이걸 "yt-dlp 실패"로만 보여주면 사장님은 우리 코드가 고장난 줄 안다.

    ⚠️ 원문을 지우지 않는다 — 힌트를 **앞에 덧붙일 뿐**이다(디버깅 정보 보존).
    """
    e = (err_text or "").lower()
    if "/404" in e or "404?source=" in e:
        return "원본이 지워졌거나 로그인해야 볼 수 있는 글이에요(주소는 정상)"
    if "cookies" in e and "browser" in e:
        return "이 영상은 로그인 쿠키가 있어야 받을 수 있어요"
    if "private" in e or "login required" in e or "sign in" in e:
        return "비공개이거나 로그인이 필요한 영상이에요"
    if "unsupported url" in e:
        return "이 주소에서는 영상을 찾지 못했어요 — 영상 페이지 주소인지 확인해 주세요"
    if "unavailable" in e or "removed" in e or "deleted" in e:
        return "원본이 삭제됐거나 더 이상 볼 수 없는 영상이에요"
    if "timed out" in e or "timeout" in e:
        return "받는 데 너무 오래 걸려 중단됐어요 — 잠시 후 다시 시도해 주세요"
    if "403" in e or "forbidden" in e:
        return "플랫폼이 접근을 막았어요(지역제한·차단)"
    return ""


def _edl_empty_reason(source_scripts, plan):
    """EDL이 빈 이유를 **갈라서** 말한다(2026-08-19 사장님 총점검 지시).

    ★종전 문구는 원인 2개를 뭉갰다: "대본 추출 실패 또는 Gemini 키 소진".
      그래서 사장님도 나도 엉뚱한 데를 봤다. 실측(라이브 13건)에서 대부분은
      **추출이 성공한 상태**였다 — extract_json 9,091자인데 edit_plan은 0이었다.
      즉 진짜 실패 지점은 추출이 아니라 **편집안 생성**이다.

    반환: (사유코드, 사람이 읽는 문구). 판정 근거는 '지금 손에 있는 것'뿐이다 —
    소스 대본이 실제로 비었나 / 있는데 편집안만 비었나.
    """
    texts = [(s.get("full_text") or "").strip() for s in (source_scripts or [])]
    chars = sum(len(t) for t in texts)
    got = [t for t in texts if t]
    gen = (plan or {}).get("generator") or ""
    if not (source_scripts or []):
        return ("no_source",
                "소스 영상이 없습니다 — 담긴 영상을 확인해 주세요.")
    if not got:
        return ("extract_empty",
                f"소스 {len(texts)}편에서 대본을 한 글자도 못 뽑았습니다"
                " — 자막·음성이 없거나 추출이 막혔습니다(키 소진과는 다른 문제).")
    if chars < 50:
        return ("extract_thin",
                f"뽑힌 대본이 너무 짧습니다({chars}자) — 편집안을 만들 재료가 부족합니다.")
    # ★여기가 실측 다수 경로다. 추출은 됐는데 편집안이 비었다.
    return ("plan_empty",
            f"대본은 {chars}자 뽑혔는데 편집안(EDL)이 비었습니다"
            f"{' [생성기=' + gen + ']' if gen else ''}"
            " — Gemini 응답이 비었거나(키 소진·차단·과부하) 편집안 파싱에 실패했습니다.")


def _owned_job(fn):
    """워커가 **누구 작업인지** 알고 돌게 한다.

    ★왜 필요한가: 제미나이 키를 고르는 쪽(keyroute.gemini_keys)은 인자로 cid를
      못 받는다 — 호출 체인이 3~4겹이라 시그니처를 20곳 넘게 고쳐야 하기 때문이다.
      대신 keyctx에 담아두고 그쪽이 읽는다. 워커는 HTTP 미들웨어를 안 거치고
      별도 스레드에서 도니까(contextvar는 스레드마다 따로) 여기서 직접 열어준다.

    안 열면 0(사장님)으로 떨어진다 — 남의 키를 쓰는 일은 생기지 않는다.
    """
    import functools
    import inspect

    sig = inspect.signature(fn)

    @functools.wraps(fn)
    def wrap(*a, **kw):
        from shopping_shorts import keyctx
        cid = 0
        try:
            b = sig.bind(*a, **kw)
            b.apply_defaults()
            cid = _job_customer_id(b.arguments.get("db_path"),
                                   b.arguments.get("job_id")) or 0
        except Exception:      # noqa: BLE001 — 주인을 못 알아내도 본작업은 돌아야 한다
            pass
        with keyctx.owner(cid):
            return fn(*a, **kw)

    return wrap


@_owned_job
def run_mix_job(job_id, db_path, work_root):
    """다운로드→추출→EDL→TTS. 완료 시 status='ready_for_review'."""
    # 이 job 안에서 나가는 모든 Gemini 콜에 job_id·customer_id를 붙인다(2026-08-16).
    # 호출부 34곳을 안 고치고 "영상 1편 = 얼마"를 집계하기 위한 문맥이다.
    # ⚠️ 본문을 딴 함수로 빼지 마라 — test_mix_pipeline_has_the_guard가
    #    inspect.getsource(run_mix_job)로 가드 코드를 검사한다(2026-08-16 실측).
    _meter = usage_meter.track(job_id=job_id, op="제작",
                               customer_id=_job_customer_id(db_path, job_id))
    with _meter:
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
            video_paths, captions, skipped = _prepare_sources(job["urls"], work, store=store)
            if skipped:
                print(f"run_mix_job[{job_id}]: {len(skipped)}개 소스 스킵 "
                      f"(불량 URL) — {[u for u, _ in skipped]}", file=sys.stderr)
            # ★가로형(롱폼) 소스는 여기서 막는다(2026-08-27 사장님 지시).
            #   숏폼 세로 화면에 가로 영상을 넣으면 좌우가 크게 잘려 "줌한 것처럼" 나온다.
            #   ⚠️ 여기가 유일한 관문이다 — 화면에서도 미리 알리지만, 화면 경고는
            #   지나칠 수 있으므로 **실제 차단은 이 한 곳**에서만 한다(0순위-B).
            _block_landscape(video_paths, {_source_video_id(i): u
                                           for i, u in enumerate(job["urls"])})

            # 2) 대본 추출(병렬)
            store.update_mix_job(job_id, status="extracting")
            # 프레임 태깅 추출전환(B1, 2026-07-29): 켜면 영상 통째 업로드 대신 파이썬 컷+프레임+오디오
            # 전사로 추출한다(느림·PROCESSING실패 근본해소). 기본 off=회귀0. 실측 후 승격.
            # 설계: docs/superpowers/specs/2026-07-29-프레임태깅-추출전환-design.md
            _use_frames = store.get_setting("frame_extract_enabled", "") == "1"
            # vid("s0") → 원래 URL. 캐시 키(shortcode)를 되찾는 데 쓴다.
            _url_of = {_source_video_id(i): u for i, u in enumerate(job["urls"])}

            def _extract(item):
                vid, path = item
                # 캐시 재사용(2026-07-24): 이 소스 대본을 담기/AI PICK/뽑기 때 이미 뽑아
                # script_extracts에 저장했으면 그대로 쓴다 — Gemini/Whisper 재전사 스킵(속도↑).
                # ★품질 무해 가드: extract_script와 동일한 {segments(seg_id 포함), full_text} 형태를
                #   그대로 저장했으므로 동일 데이터다. 단 seg_id가 다 있어야 장면매칭이 성립하므로,
                #   segments가 비었거나 seg_id 없는 항목이 하나라도 있으면 캐시를 버리고 새로 추출한다.
                cached = None
                try:
                    # ★캐시 키는 shortcode다(2026-08-06 수정). 예전엔 vid("s0")로 찾아
                    #   **한 번도 적중하지 않았다** — 위 _cache_key_for_url 주석 참고.
                    for _ck in _cache_keys_for_url(_url_of.get(vid)):
                        cached = store.get_extract(_ck)
                        if cached is not None:
                            break
                    if cached is None:
                        cached = store.get_extract(vid)      # 옛 방식도 남겨둔다(하위호환)
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
                    # ★영상 단위 요약을 함께 물려준다(2026-08-17). 여기서 캐시의 **일부
                    #   필드만** 골라 담기 때문에 source_brief가 통째로 떨어져 나갔다 —
                    #   도서관 추출본엔 있는데 job의 extract엔 없어서, 재태깅을 해도
                    #   대본 쪽에서는 영영 못 보는 상태였다(실측 job 8873eeb48a08:
                    #   s0·s1·s2 셋 다 source_brief 없음, 같은 소스의 도서관 캐시엔 있음).
                    #   옛 캐시엔 이 필드가 없어 {}가 되고 읽는 쪽은 그대로 견딘다.
                    if cached.get("source_brief"):
                        r["source_brief"] = cached["source_brief"]
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
                # ★추출 커버리지는 **같은 영상·같은 조건에서도 크게 흔들린다**(2026-08-06 실측).
                #   Dbjk5BXToB7(21.1초)을 5회 반복: 67% / 95% / 55% / 55% / 55% — 평균 65%.
                #   영상이나 힌트 문제가 아니라 모델 출력의 확률적 편차다(한때 '힌트가 범인'
                #   이라고 봤으나 표본 1개짜리 오판이었다). 뒷부분이 통째로 날아가면 사장님
                #   결과물이 11~16초로 짧아진다 — 원본 21초가 멀쩡히 있는데도.
                #   그래서 **낮으면 여러 번 다시 뽑고 가장 좋은 것을 쓴다**. 재시도는 조건을
                #   바꿔가며(힌트 on/off 번갈아) 한다 — 같은 조건 반복은 같은 실패를 부른다.
                cov = _extract_coverage(r, path)
                for _try in range(_EXTRACT_RETRIES):
                    if cov is None or cov >= _MIN_COVERAGE:
                        break
                    r2 = extract_script(path, vid, caption=captions.get(vid, ""),
                                        use_boundaries=bool(_try % 2))
                    cov2 = _extract_coverage(r2, path)
                    if cov2 is not None and cov2 > (cov or 0):
                        print(f"[extract] {vid} 재추출 {_try + 1}회차로 개선: "
                              f"{cov:.0%} → {cov2:.0%}", flush=True)
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
            _refund_mix_points(store, job.get("customer_id", 0), job.get("render_charge_day"),
                               job.get("mix_charged"))


def _refund_mix_points(store, customer_id, charge_day, charged=None):
    """영상제작 실패 → 차감한 포인트 환불. 크레딧 환불(_refund_render_charge)과 대칭.

    ★charge_day가 표식이다 — /api/mix/start 계열이 과금할 때만 채워지므로,
      과금 안 한 경로(produce 2단계·auto_run·retype)까지 환불해 잔액을
      부풀리는 일이 없다. 크레딧 환불이 쓰는 것과 같은 표식을 재사용한다.

    ★왜 필요한가: 이 코드베이스의 규칙은 '실패하면 돌려준다'다 — 크레딧도
      (_refund_render_charge), 자막제거 포인트도(_refund_clean) 돌려준다.
      영상제작 포인트(3P)만 빠지면 가장 비싼 작업이 실패할 때 잔액이
      조용히 갉힌다."""
    if not charge_day:
        return
    from shopping_shorts import keyroute, points, pricing
    if not keyroute.as_cid(customer_id):
        return                       # 사장님(cid 0)은 애초에 과금 안 했다
    try:
        if charged is not None:
            # ★정상 경로 — 차감할 때 정한 액수를 그대로 돌려준다.
            #   0이면 애초에 안 깎였으니 환불도 없다.
            if int(charged) > 0:
                points.refund(store, customer_id, int(charged), pricing.OP_MIX)
            return
        # ↓ mix_charged 칸이 생기기 전(2026-08-24 이전)에 시작된 job 호환.
        #   이 경로는 환불 시점에 다시 판단하므로 차감과 어긋날 수 있다 —
        #   개인 키로 0원 차감된 뒤 키를 지우면 없던 포인트가 생긴다.
        #   배포 직후 진행 중이던 job만 여기로 오고, 몇 분이면 사라진다.
        logging.warning("mix 환불: mix_charged가 없는 옛 job이라 재판단으로 환불한다 (cid=%s)",
                        customer_id)
        if keyroute.should_charge(store, customer_id, keyroute.SVC_GEMINI):
            points.refund(store, customer_id,
                          pricing.cost(store, pricing.OP_MIX), pricing.OP_MIX)
    except Exception:
        traceback.print_exc(file=sys.stderr)


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


def _prefer_structurally_sound(rec, candidates, target_seconds):
    """추천 후보의 골격이 무너졌으면 형제 후보 중 성한 것으로 바꾼다(순수·무과금).

    형태만 본다(비트 수·길이) — 문장 품질 판정은 judge 소관이라 건드리지 않는다.
    바꿀 게 없으면 추천을 그대로 돌려준다(회귀 0). 정렬은 안정적이라 같은 입력이면 같은 결과."""
    def _beats(c):
        return ((c or {}).get("plan") or {}).get("beats") or []

    def _secs(c):
        return round(sum(float(b.get("target_seconds") or 0) for b in _beats(c)), 1)

    def _broken(c):
        n = len(_beats(c))
        if n < plan_gate._MIN_BEATS:
            return True
        # 목표의 절반도 안 되면 이야기가 안 선다(게이트의 _SHORT_RATIO보다 느슨한 하한).
        return bool(target_seconds) and _secs(c) < target_seconds * 0.5

    if not _broken(rec):
        return rec
    # 성한 후보 중 비트가 가장 많은 것(같으면 원래 순서 유지 = 심사 순위 존중).
    sound = [c for c in (candidates or []) if c is not rec and not _broken(c)]
    if not sound:
        print("[골격] 추천 후보가 %d비트/%.1f초로 무너졌으나 성한 형제 후보가 없어 그대로 진행"
              % (len(_beats(rec)), _secs(rec)), file=sys.stderr)
        return rec
    best = max(sound, key=lambda c: len(_beats(c)))
    print("[골격] 추천 후보(%d비트/%.1f초)를 형제 후보(%d비트/%.1f초)로 교체"
          % (len(_beats(rec)), _secs(rec), len(_beats(best)), _secs(best)), file=sys.stderr)
    return best


def _run_gate_correction(plan, source_scripts, target_seconds):
    """게이트 검사→재픽 루프. 위반이 재픽 가능하면 통과할 때까지 재픽(상한 _MAX_REPICK).
    재픽이 무변화면 즉시 종료(수렴). 최종 gate를 plan["gate"]에 항상 저장 —
    프론트가 역할별로(관리자=경고/일반=숨김) 표시한다. 순수·무과금·나레이션 불변."""
    pool_ct = len({s.get("video_id") for s in (source_scripts or [])
                   if s.get("segments")} - {None})
    # 소재 천장(전 소스 세그 합) — 목표가 이보다 크면 게이트가 소재 기준으로 판정한다.
    mat_secs = 0.0
    for s in (source_scripts or []):
        for seg in (s.get("segments") or []):
            if isinstance(seg, dict):
                mat_secs += max(0.0, float(seg.get("end") or 0) - float(seg.get("start") or 0))
    mat_secs = round(mat_secs, 1) or None

    def _gate(bs):
        # material_seconds는 신규 인자 — 이를 모르는 구현(테스트 더블 등)이면 없이 부른다.
        try:
            return plan_gate.check_plan(bs, target_seconds, pool_video_count=pool_ct,
                                        material_seconds=mat_secs)
        except TypeError:
            return plan_gate.check_plan(bs, target_seconds, pool_video_count=pool_ct)

    beats = plan.get("beats")
    gate = _gate(beats)
    rounds = 0
    while rounds < _MAX_REPICK and _has_repickable(gate):
        new_beats = backbone.repick_for_gate(beats, source_scripts, gate)
        if new_beats == beats:
            break   # 더 못 고침 → 종료(잔여 위반은 §4 마감이 처리)
        beats = new_beats
        rounds += 1
        gate = _gate(beats)
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
    # ★언어 분리(2026-08-14 사장님 "샤오홍슈에 있는 영상은 대본과 아예 닿지 않게 하라"):
    #   외국어 소스의 **말만** 지운다 — 화면·특장점은 그대로 남아 장면 재료로 계속 쓰인다.
    #   ★반드시 여기 한 곳에서만 한다(0순위-B). 아래 모든 경로(훅패턴 material_text·
    #   scene_first·build_edit_plan 폴백)가 이 source_scripts 하나를 본다.
    source_scripts = script_lang.mute_foreign_speech(source_scripts)
    # ★1소스면 목표를 소재 천장에 맞춘다(2026-08-04). 릴 1개는 보통 20초인데 목표 30초가
    # 그대로 내려오면 없는 10초를 채우라는 요구가 돼 반복·무편집구간으로 늘리다 게이트에
    # 걸린다(실측: 1소스 100%가 소재부족). 하한 18초는 사장님 지시("스토리 기본이 서는 선").
    if single_source.is_single_source(source_scripts):
        _segs = next((s.get("segments") for s in source_scripts if s.get("segments")), [])
        _span, _budget = single_source.budget_for(_segs, target_seconds)
        if _budget and abs(_budget - (target_seconds or 0)) >= 0.5:
            print("[1소스] 원본 %.1f초 → 목표 %.1f초로 조정(요청 %s초)"
                  % (_span, _budget, target_seconds), file=sys.stderr)
            target_seconds = round(_budget, 1)
    # 소스 다수결이 레시피면 화면을 요리 시간순으로 재배치(장면 결 맞춤) — build_edit_plan 경로에 전달.
    is_recipe = _sources_is_recipe(source_scripts)
    _rec_cands = None   # 후보목록(카드) — conform 뒤 재저장해 카드=TTS 일치시키려고 잡아둔다
    # ★확정 대본이 있으면 **새로 쓰지 않는다**(2026-08-17 사장님: "어이없게 대본을 또 쓰냐 /
    #   당연히 대본은 확정해서 믹스 버튼을 누른 거지 / 거기서 대본 수정까지 마무리한 거니까").
    #
    #   이 함수 docstring이 원래 그렇게 적혀 있다 — "given_script: 있으면 확정 대본을 그대로
    #   비트로 쪼개 영상만 매칭(영상제작 2단계)". 그런데 `if scene_first:`가 **먼저** 걸려서
    #   그 분기를 못 탔다. produce.html은 scene_first를 **항상 true**로 보낸다(4950행).
    #   given_script와 reference_text에 같은 값이 들어가는데, scene_first 경로는 given_script를
    #   안 보고 reference_text를 '참고 대본'으로만 써서 후보 3~4개를 **새로 쓴다**.
    #
    #   실측 피해 둘:
    #     ① 2단계가 무의미해진다 — 확정 371자가 3단계에서 전혀 다른 162자로 바뀌었다
    #        (job 832a5ffa80d9: "요즘 인스타 감성…" → "저 이거 때문에 외출할 때마다…")
    #     ② 시간이 여기서 다 간다 — job 0bd83269a8ca 8분 48초 중 대본 생성+리라이트가
    #        460초(7.7분). 그나마 restyle 실호출은 78초뿐이고 나머지가 대본 새로 쓰기다.
    #        후보가 c1~c5까지 늘어나며(품질 미달 재생성) 매번 길이초과로 3~4회씩 재요청했다.
    #
    #   → 확정 대본이 오면 scene_first를 끄고 build_edit_plan(given_script 경로)으로 간다.
    #     대본은 2단계 것 그대로, 3단계는 **화면만 붙인다**(화면 설명 "문장마다 어떤 화면이
    #     붙는지 정하고 미리 봅니다"와도 이제 일치).
    #   ⚠️ 대본 없이 오는 경로(위키 직행·자동배치 등)는 종전대로 scene_first가 돈다(회귀 0).
    if scene_first and (given_script or "").strip():
        print("[mix] 확정 대본이 있어 scene_first를 끈다 — 대본은 그대로, 화면만 매칭"
              " (%d자)" % len((given_script or "").strip()), file=sys.stderr)
        scene_first = False
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
        # ★확정 훅패턴 10종 주입(2026-08-04 사장님 지시: "훅은 은행에서 빼서 지금 나랑 정해").
        # 은행 자동로테이션은 크롤한 남의 훅이라 매번 달라 뭐가 먹히는지 안 쌓인다. 우리가
        # 고른 10개 뼈대만 돌린다. 소재에 맞는 것만 후보가 되고("다이소 가면"은 원본이 다이소
        # 소재일 때만), "여러분~" 계열이 3개 중 1개꼴로 걸린다.
        try:
            from shopping_shorts import hook_patterns
            _mat = " ".join((s.get("full_text") or "") for s in (source_scripts or []))
            _pats = hook_patterns.choose(3, material_text=_mat)
            if _pats:
                bank_context = (hook_patterns.prompt_block(_pats[0])
                                + ("\n" + bank_context if bank_context else ""))
                print("[훅패턴] %s" % " / ".join(p[1] for p in _pats), file=sys.stderr)
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
            # ★골격이 무너진 후보는 추천이라도 쓰지 않는다(2026-08-07).
            #   심사(judge)는 대본 품질·장면싱크를 보지 형태(비트 수)를 안 본다. 실측 08-06:
            #   12건 중 6건이 5비트 미만으로 나갔고 그중 3건은 2비트(30초 목표에 14.2초)였다.
            #   같은 job의 다른 후보가 멀쩡하면 그걸 쓰는 게 항상 낫다 — 추가 호출·과금 없다.
            rec = _prefer_structurally_sound(rec, sf["candidates"], target_seconds)
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
        # ★사유를 갈라서 말한다(2026-08-19). 종전엔 "추출 실패 또는 키 소진"으로 뭉개서
        #   실측 13건 중 대부분이 **추출은 성공한 상태**(9,091자)였는데도 "추출 실패"로
        #   보였다 — 원인이 다르면 처방도 다르므로 여기서 갈라 기록·표시한다.
        code, why = _edl_empty_reason(source_scripts, plan)
        n_src = len(source_scripts or [])
        n_chars = sum(len((s.get("full_text") or "")) for s in (source_scripts or []))
        print(f"[EDL빈원인] code={code} sources={n_src} chars={n_chars} "
              f"generator={(plan or {}).get('generator')!r}", file=sys.stderr)
        # 같은 이유로 사람에게 올린다(2026-08-04) — 08-03엔 Gemini 키 403(project denied)로
        # 이 실패가 2건 났는데 역시 조용히 DB에만 남았다. 키 소진/차단은 사람이 손대야 풀린다.
        try:
            from shopping_shorts import ops_alert
            ops_alert.raise_alert(
                "edl_empty",
                f"편집안(EDL)을 만들지 못했습니다 — {why}",
                f"run_mix_job: EDL이 비어 있습니다. code={code} sources={n_src} chars={n_chars}. "
                "plan_empty면 Gemini 키풀(소진·403 PERMISSION_DENIED)과 편집안 파싱을, "
                "extract_empty면 소스 자막·음성 추출을 보세요.", store=store)
        except Exception as _ae:      # noqa: BLE001 — 알림 실패가 본작업을 막지 않는다
            print(f"[ops_alert] edl_empty 알림 실패(무해): {_ae!r}", file=sys.stderr)
        raise RuntimeError(f"EDL 비어있음({code}) — {why}")

    # 3.5/3.6) 장면 라이브러리 자동 배치(컷어웨이 + 효과음) — ★기본 OFF(2026-08-01 실사고).
    #
    # 사장님 제보 "완성 영상에 왜 감자 레시피 조각이 들어가지?"의 범인이 이 자동 배치였다.
    # 실측(job a75c22f644ad, 요거트 아이스크림 소재): 비트0(hook)에 asset 5 "감자튀김",
    # 비트1(process)에 asset 10 "채 썬 감자"가 붙었고 둘 다 match_type="role"이었다 —
    # **역할 이름만 같으면 붙인다**. 소재(subject)·카테고리·키워드는 보지 않는다.
    # 컷어웨이는 비트 영상 **위에 풀프레임 오버레이**라 우리 화면을 통째로 덮고, 그 자산에
    # 박힌 원본 자막("구황작물 극혐하던 남편도")까지 그대로 나갔다.
    #
    # 게다가 켜고 끄는 스위치가 없어 **자산이 하나라도 등록돼 있으면 모든 영상에 무조건**
    # 적용됐다(당시 12개 등록). 사장님 지시("장면 라이브러리 없애, 안 쓰니까")에 따라
    # 기본을 OFF로 두고 설정으로만 켜지게 한다 — 자산 데이터는 지우지 않는다(되돌리기 쉽게).
    # 다시 켜려면 설정 scene_library_auto_enabled=1. 매칭을 소재·카테고리까지 보도록 고치는
    # 일은 장면라이브러리 트랙 소관이다.
    if store.get_setting("scene_library_auto_enabled", "") == "1":
        assets = store.list_scene_assets(customer_id=customer_id, asset_type="clip")
        if assets:
            plan = match_scene_assets(plan, assets)
        sfx_assets = store.list_scene_assets(customer_id=customer_id, asset_type="sfx")
        if sfx_assets:
            plan = match_sfx(plan, sfx_assets)

    # 4) 비트별 TTS (naturalize + N-best + 연속성 + 프리셋 후처리)
    store.update_mix_job(job_id, status="tts")
    _synthesize_beats(plan["beats"], work / "tts", voice=voice, global_pron=global_pron,
                      customer_id=customer_id)

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


@_owned_job
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


def _vmake_keys(store, customer_id=0):
    """자막제거에 쓸 키 **전부**. 사용자가 등록했으면 그 키들, 아니면 사장님 키.
    ★keyroute가 유일한 판단처다 — 여기서 따로 고르지 마라(0순위-B).

    ★2026-08-29까지는 keys[0] **하나만** 돌려줬다. 그래서 키를 두 개 등록해도
      첫 키가 소진되면 그걸로 끝이었다(사장님 제보: "두개 키등록했다는데 한개 소진후
      다른걸로 안넘어가는것같은데"). 실측 cid 57: vmake 키 235·236 둘 다 status='ok'인데
      나중 것(236)만 쓰이고 235는 잔액이 남아도 영영 안 쓰였다.
    """
    from shopping_shorts import keyroute
    keys, _ = keyroute.keys_for(store, customer_id, keyroute.SVC_VMAKE)
    return list(keys or [])


def _vmake_clean(video_path, keys, out_path):
    """VMake 청소 1회 — **크레딧이 떨어진 키는 건너뛰고 다음 키로** 이어서 시도한다.

    ★키를 넘기는 판단은 여기 한 곳에서만 한다(0순위-B). 호출부 셋(_clean_one·
      _clean_joined·_final_clean_fn)이 각자 돌리면 어떤 경로로 들어왔느냐에 따라
      넘어가기도 하고 안 넘어가기도 한다.
    ★소진(60002) **말고 다른 실패는 즉시 올린다** — 네트워크·처리불가로 키를 갈아타면
      멀쩡한 키를 태우기만 하고 원인은 그대로다. 판정은 vmake_client.is_no_credit.
    ★전부 소진이면 마지막 오류를 그대로 올린다 → 화면은 종전처럼 'no_credit'을 띄운다
      (사장님 결정 2026-08-29: 회원 키가 다 떨어져도 본사 키로 넘기지 않는다).
    """
    from shopping_shorts.vmake_client import is_no_credit
    ks = [k for k in (keys or []) if k]
    if not ks:
        raise ValueError("자막제거 키가 없습니다")
    last = None
    for i, k in enumerate(ks):
        try:
            return remove_subtitles(video_path, k, out_path=out_path)
        except Exception as e:                      # noqa: BLE001 — 다음 키로 넘길지 가른다
            last = e
            if not is_no_credit(e):
                raise                               # 소진이 아니면 키 문제가 아니다
            print(f"[clean] 키 {i + 1}/{len(ks)} 크레딧 소진 → 다음 키로: {e}",
                  file=sys.stderr)
    raise last


class NotEnoughPoints(Exception):
    """포인트가 모자라 시작조차 못 함. 반만 청소되는 것보다 아예 안 하는 게 낫다."""


def _charge_clean(store, customer_id, n_sources):
    """자막제거 선차감. 깎은 액수를 반환(0=무료). 모자라면 NotEnoughPoints.

    ★소스 개수만큼 곱한다 — VMake는 소스 1편당 1콜이다(_ensure_clean_sources).
      job당 1회로 계산하면 소스 3개짜리에서 1,000원을 손해 본다.
    """
    from shopping_shorts import keyroute, points, pricing
    if n_sources <= 0:
        return 0
    # ★cid 0 = 사장님 본인(store.LEGACY_CUSTOMER_ID). 자기 키로 자기한테 청구하는 꼴이라
    #   과금 대상이 아니다. keyroute도 cid 0은 개인키 조회를 아예 건너뛴다.
    #   정규화는 keyroute.as_cid를 그대로 쓴다 — 여기서 int()를 또 부르면
    #   같은 판단이 두 곳에 흩어진다(0순위-B).
    if not keyroute.as_cid(customer_id):
        return 0
    if not keyroute.should_charge(store, customer_id, keyroute.SVC_VMAKE):
        return 0                                    # 내 키 → 무료
    need = pricing.cost(store, pricing.OP_VMAKE) * n_sources
    if not points.deduct(store, customer_id, need, pricing.OP_VMAKE):
        raise NotEnoughPoints(
            f"포인트가 부족합니다 (필요 {pricing.to_display(need)}P, "
            f"보유 {pricing.to_display(points.balance(store, customer_id))}P)")
    return need


def _refund_clean(store, customer_id, amount):
    """청소 실패 시 돌려준다. ★과금한 만큼만 — 안 깎은 호출자까지 환불하면 원장이 갉힌다."""
    from shopping_shorts import points, pricing
    if amount > 0:
        points.refund(store, customer_id, amount, pricing.OP_VMAKE)


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



def resolve_deco_media(deco, work):
    """deco의 BGM·오버레이 파일(업로드 시 work/{file}에 저장) → 절대경로(_abspath)를 심어 돌려준다.

    ★렌더와 캡컷 내보내기가 **같은 함수**를 쓴다(0순위-B) — 두 곳에 따로 적으면
      "완성본엔 음악이 있는데 캡컷엔 없다"처럼 조용히 갈린다.
    원본 dict는 건드리지 않는다(얕은 복사본 반환).
    """
    deco = dict(deco or {})
    work = Path(work)
    for key in ("bgm", "overlay"):
        item = deco.get(key) or {}
        if item.get("file"):
            p = work / item["file"]
            if p.exists():
                deco[key] = {**item, "_abspath": str(p)}
    return deco


def _template_layer(tpl, first_beat_dur=0):
    """꾸미기 템플릿 → 렌더가 쓸 레이어 dict. 없거나 모르는 id면 None.

    ★span('full'|'first')을 dur(초)로 바꾸는 **유일한 지점**이다(0순위-B).
    화면은 'first'라고 말하고 렌더는 dur만 안다 — 변환이 두 곳에 생기면 어긋난다.
    """
    from shopping_shorts import deco_templates
    tpl = tpl or {}
    # ★'내용물 있는 틀'(채널명·제목·조회수)은 미리보기와 **같은 함수**가 그린다.
    #   여기서 따로 그리면 화면과 결과가 갈린다(0순위-B). 옛 색띠 12종은 아래 경로 그대로.
    frame = tpl.get("frame")
    if frame:
        from shopping_shorts import deco_frame
        p = deco_frame.render_to(frame, deco_frame.cache_path(frame))
        tid = "frame:" + deco_frame.cache_key(frame)
        # 🩹 가림막의 **흐림**은 그림으로 못 한다(뒤 영상을 흐리게 하는 일이라).
        #   모양만 마스크로 넘기고, 실제 블러는 렌더(video_assemble)가 먹인다.
        #   ★모양은 미리보기와 **같은 함수**가 그린다 — 보이는 자리와 흐려지는 자리가 같다.
        _bm = deco_frame.render_blur_mask_to(frame)
        _bsig = deco_frame.blur_sigma(deco_frame.normalize(frame)["masks"])
    else:
        tid = tpl.get("id")
        if not tid:
            return None
        p = deco_templates.abs_path(tid)
    if not p or not p.exists():
        return None
    out = {"_abspath": str(p), "id": tid, "alpha": tpl.get("alpha", 1)}
    # ★이미지 틀(캔바 그림)은 화면을 꽉 채우므로 **글자보다 아래**에 깔아야 한다.
    #   안 그러면 자막·헤드카피가 그림에 통째로 묻힌다(2026-08-31 사장님 제보).
    #   기존 틀은 띠 말고 전부 투명이라 지금까지 그대로 얹혀도 문제가 없었다 —
    #   그래서 **이미지를 깐 틀만** 표시한다(옛 작업의 그림은 한 픽셀도 안 바뀐다).
    if frame and (frame.get("bg_image") or "").strip():
        out["under_text"] = True
    if frame and _bm and _bsig > 0:
        out["blur_mask"] = str(_bm)
        out["blur_sigma"] = _bsig
    # 'first'인데 비트 길이를 모르면 전체로 둔다 — dur=0을 주면 화면에서 아예 안 보인다.
    if tpl.get("span") == "first" and first_beat_dur and first_beat_dur > 0:
        out["dur"] = float(first_beat_dur)
    return out


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


# VMake가 간헐적으로 뱉는 처리 실패 — 같은 영상을 다시 넣으면 대개 통과한다.
# (실측 2026-07-23·08-18 두 건 모두 code 10101 "right reduce error", 잔액·인증은 정상이었다.
#  성공 35건+ 대비 실패 3건이라 상시 고장이 아니라 간헐 오류로 본다.)
_CLEAN_RETRY = 2          # 최초 1회 + 재시도 2회 = 최대 3번
_CLEAN_RETRY_WAIT = 5     # 초. 곧바로 다시 때리면 같은 이유로 또 실패하기 쉽다.


def _clean_one(item, keys, work):
    """소스 하나를 VMake로 청소 → (video_id, 클린경로, 지워진자막박스|None). ThreadPool 워커용(DB 미접근).
    청소 직후 원본↔클린을 diff해 '어디가 지워졌나'를 그 자리에서 구한다 — VMake는 좌표를 안 주지만
    우리가 before/after를 둘 다 쥐고 있어 계산 가능하다(best-effort, 실패해도 None으로 청소는 성공).

    ★간헐 실패 자동 재시도(2026-08-19): VMake는 멀쩡한 영상에도 가끔 10101을 준다.
      예전엔 그 한 번으로 작업 전체가 실패로 끝나 사장님이 손으로 다시 눌러야 했다.
      **재과금은 없다** — 과금은 호출부(_ensure_clean_sources)에서 소스 개수로 선차감하고
      여기선 같은 소스를 다시 시도할 뿐이다. VMake 쪽도 실패한 작업은 크레딧을 안 깎는다
      (실측: 실패 3건 동안 잔액이 그대로였다)."""
    vid, src = item
    out = str(Path(work) / f"clean_src_{vid}.mp4")
    last = None
    for attempt in range(_CLEAN_RETRY + 1):
        try:
            clean_path = _vmake_clean(src, keys, out)
            break
        except Exception as e:
            last = e
            if attempt >= _CLEAN_RETRY:
                print(f"[clean] {vid} 최종 실패({attempt + 1}회 시도): {e}", file=sys.stderr)
                raise
            # ★크레딧 소진은 재시도해도 영원히 같다 — _vmake_clean이 이미 등록된 키를
            #   전부 훑고 올린 것이므로 여기서 3번 더 때릴 이유가 없다(2026-08-29).
            from shopping_shorts.vmake_client import is_no_credit
            if is_no_credit(e):
                raise
            print(f"[clean] {vid} 실패 — {_CLEAN_RETRY_WAIT}초 뒤 재시도"
                  f"({attempt + 1}/{_CLEAN_RETRY}): {e}", file=sys.stderr)
            time.sleep(_CLEAN_RETRY_WAIT)
    region = sub_region.detect_erased_region(src, clean_path, work)
    return vid, clean_path, region


# ── 소스 이어붙여 1콜로 청소 (2026-08-25 사장님 지시) ─────────────────────
# 왜: 자막제거는 **건당 50크레딧**이라(pricing.py 실측) 소스마다 부르면 소스 개수배로
#     나간다. 실측 사고 — 고객 Plus 플랜 월 1,000크레딧 = 20건인데, 소스 4개짜리
#     영상 하나에 4건(200크레딧)이 나가 **영상 5개**만에 바닥났다. 화면 안내는
#     "영상 1편당 5P"인데 실제로는 소스 개수×5P를 깎고 있었다(안내와 구현 불일치).
#     소스를 하나로 붙여 1콜로 보내면 안내대로 영상 1편당 1건이 된다.
#
# 어떻게: 소스마다 해상도·fps가 제각각이라(실측: 720x1280·1080x1920·1440x2560,
#     24·30·60fps) 그냥 못 붙인다. **가장 큰 해상도**에 맞춰 정규화한 뒤 concat한다
#     — 작은 걸 키우는 방향이라 원본 정보 손실이 없다. 비율은 전부 9:16이라
#     레터박스가 필요 없다(실측).
#
# 안전장치: 붙이기·자르기 중 무엇이든 실패하면 **기존 소스별 방식으로 되돌아간다**.
#     새 경로가 고장나도 고객 작업은 그대로 된다(실패 대신 비싸게라도 완성).

# VMake에 한 번에 보낼 최대 길이(초). 넘으면 여러 묶음으로 나눠 붙인다.
# 처리 시간이 길이에 비례해 늘어나므로 무한정 붙이지 않는다.
_JOIN_MAX_SEC = float(os.environ.get("SHORTS_CLEAN_JOIN_MAX_SEC", "240"))
# 이어붙이기 자체를 끌 수 있는 스위치 — 문제가 생기면 배포 없이 되돌린다.
_JOIN_ENABLED = os.environ.get("SHORTS_CLEAN_JOIN", "1") != "0"


def _probe_wh_dur(path):
    """(width, height, duration) — ffprobe 1회."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height",
         "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    st = j["streams"][0]
    return int(st["width"]), int(st["height"]), float(j["format"]["duration"])


# ── 사용 구간만 청소(2026-08-25 사장님 "완성본 만들면 하나의 영상인데 그것만 지우면 안 되나") ──
# 실측(job e68b1bcf8900): 소스 원본 4개 111.6초를 청소했는데 완성본은 30.3초였다.
# 쓰지도 않을 81초까지 VMake에 보내 시간이 4배 가까이 들었다.
#
# 완성본을 직접 청소하지 않는 이유: 그러면 편집을 고칠 때마다 재청소(재과금)다.
# 소스별 캐시를 지키면서 **보내는 길이만** 줄인다.
#
# ★안전선: 청소 안 된 구간이 화면에 나오면 원본 자막이 그대로 보인다.
#   판정이 조금이라도 애매하면 전체 청소로 되돌린다(None 반환). 아끼려다 자막을 남기지 않는다.
_SPAN_PAD = float(os.environ.get("SHORTS_CLEAN_SPAN_PAD", "1.5"))     # 앞뒤 여유(초)
_SPAN_MIN_GAIN = float(os.environ.get("SHORTS_CLEAN_SPAN_MIN_GAIN", "0.8"))  # 이만큼 이하로 줄어야 자른다
_SPAN_ENABLED = os.environ.get("SHORTS_CLEAN_SPAN", "0") == "1"       # ★기본 꺼짐 — 실측 후 켠다


def _used_spans(plan):
    """편집안이 **실제로 화면에 쓰는** 소스 구간 {video_id: [(start, end), ...]}.

    재료 판정은 video_assemble._beat_material과 같은 규칙이다(0순위-B):
    사람이 편성한 scene_override가 있으면 그것, 없으면 primary + alternates.
    alternates를 빼면 안 된다 — 나레이션이 길면 실제로 화면에 나온다(빼면 자막이 남는다).

    하나라도 못 읽으면 **None** — 호출부는 소스 전체를 청소한다.
    """
    beats = (plan or {}).get("beats") or []
    if not beats:
        return None
    out = {}
    for b in beats:
        for m in _beat_materials(b):
            vid = m.get("video_id")
            try:
                st, en = float(m.get("start")), float(m.get("end"))
            except (TypeError, ValueError):
                return None                       # 숫자가 아니다 → 판정 포기(전체 청소)
            if not vid or en <= st:
                return None                       # 뒤집힌 구간 → 판정 포기
            out.setdefault(vid, []).append((st, en))
    return out or None


def _span_of_source(spans, src_dur, pad=None):
    """소스 하나에서 잘라 보낼 **한 구간** (start, end). 자를 이유가 없으면 None.

    흩어진 구간을 최소~최대로 묶는다 — 조각을 여럿 만들면 이어붙이기·자르기가 복잡해지고
    실패 지점이 는다. 대부분 소스는 앞뒤 어딘가에서 몇 초만 쓴다.
    """
    pad = _SPAN_PAD if pad is None else pad
    if not spans or not src_dur or src_dur <= 0:
        return None
    lo = max(0.0, min(s for s, _e in spans) - pad)
    hi = min(float(src_dur), max(e for _s, e in spans) + pad)
    if hi <= lo:
        return None
    if (hi - lo) > src_dur * _SPAN_MIN_GAIN:      # 거의 전체를 쓴다 → 그냥 통째로 보낸다
        return None
    return (lo, hi)


def _restore_span(orig, cleaned, lo, hi, out_path):
    """구간만 청소한 결과를 **원본 타임라인 그대로** 되돌린다 → out_path.

    앞[0,lo) + 청소본[lo,hi] + 뒤(hi,끝] 를 이어붙인다. 길이·시각이 원본과 같아야
    하류(video_assemble)가 edit_plan의 start로 자를 때 엉뚱한 장면이 안 나온다.
    ★규격을 맞춰서 붙인다 — VMake가 돌려준 청소본은 해상도·fps가 원본과 다를 수 있고,
      그대로 concat하면 깨진다(_join_sources와 같은 이유·같은 방식).
    """
    work = Path(out_path).parent
    W, H, dur = _probe_wh_dur(orig)
    parts = []

    def _cut(src, ss, to, tag):
        dst = str(work / f"rs_{tag}.mp4")
        cmd = ["ffmpeg", "-y", "-v", "error"]
        if ss is not None:
            cmd += ["-ss", f"{ss:.3f}"]
        cmd += ["-i", str(src)]
        if to is not None:
            cmd += ["-t", f"{to:.3f}"]
        # ★여기도 비율을 지킨다(2026-08-27, _join_sources와 같은 함정).
        #   W·H는 **원본** 크기다. 청소본이 다른 비율로 돌아오면 강제 스케일은 그림을
        #   늘려버린다 — 비율이 같으면 pad는 아무 일도 안 하고, 다를 때만 검게 채운다.
        cmd += ["-vf", (f"scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,"
                        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=30"),
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", dst]
        subprocess.run(cmd, check=True)
        return dst

    if lo > 0.05:                                   # 앞 조각(없으면 만들지 않는다)
        parts.append(_cut(orig, 0.0, lo, "head"))
    parts.append(_cut(cleaned, None, None, "mid"))   # 청소된 구간
    tail = dur - hi
    if tail > 0.05:                                  # 뒤 조각
        parts.append(_cut(orig, hi, tail, "tail"))

    if len(parts) == 1:
        shutil.copyfile(parts[0], out_path)
        return out_path
    lst = work / "rs_list.txt"
    lst.write_text("".join("file " + chr(39) + x + chr(39) + chr(10) for x in parts),
                   encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", str(out_path)], check=True)
    return out_path


def _cut_used_spans(todo, plan, work):
    """todo의 각 소스를 **쓰이는 구간만** 잘라낸 파일로 바꾼다.

    todo는 [(vid, src)] — 이 리스트를 **제자리에서** 고친다(호출부가 그대로 쓴다).
    반환: {vid: (원본경로, lo, hi)} — 나중에 _restore_all이 되돌릴 때 쓴다.
    자를 수 없거나 이득이 없는 소스는 그냥 두고 반환에도 안 넣는다(통째로 청소된다).
    """
    spans = _used_spans(plan)
    if not spans:
        return {}
    work = Path(work)
    cuts = {}
    for i, (vid, src) in enumerate(list(todo)):
        used = spans.get(vid)
        if not used:
            continue                      # 이 소스는 화면에 안 쓰인다 → 손대지 않는다
        try:
            _w, _h, dur = _probe_wh_dur(src)
            picked = _span_of_source(used, dur)
            if not picked:
                continue
            lo, hi = picked
            dst = str(work / f"span_src_{vid}.mp4")
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-ss", f"{lo:.3f}", "-i", str(src),
                 "-t", f"{hi - lo:.3f}", "-c:v", "libx264", "-preset", "veryfast",
                 "-crf", "18", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-ar", "48000", "-ac", "2", dst], check=True)
            todo[i] = (vid, dst)
            cuts[vid] = (src, lo, hi)
            print(f"[clean] {vid}: {dur:.1f}s 중 {lo:.1f}~{hi:.1f}s만 청소", file=sys.stderr)
        except Exception as e:            # noqa: BLE001 — 자르기 실패는 통째로 보내면 된다
            print(f"[clean] {vid} 구간 자르기 실패 → 전체 청소: {e}", file=sys.stderr)
    return cuts


def _restore_all(done, cuts, source_map, work):
    """구간 청소 결과를 원본 타임라인으로 되돌린 {vid: 경로}.

    되돌리기가 실패하면 그 소스는 **원본**을 쓴다 — 시각이 밀린 파일을 넘기면
    엉뚱한 장면이 나오므로, 자막이 남는 쪽(원본)이 그나마 덜 나쁘다.
    """
    out = dict(done)
    for vid, cleaned in done.items():
        if vid not in cuts:
            continue
        orig, lo, hi = cuts[vid]
        try:
            dst = str(Path(work) / f"clean_src_{vid}_full.mp4")
            out[vid] = _restore_span(orig, cleaned, lo, hi, dst)
        except Exception as e:            # noqa: BLE001
            print(f"[clean] {vid} 원복 실패 → 원본 사용: {e}", file=sys.stderr)
            out[vid] = source_map.get(vid, orig)
    return out


# 붙임 캔버스 한 변의 상한. 최종 출력이 1080x1920이라 1920이면 충분하다.
_JOIN_CANVAS_MAX = 1920


def _fit_box(w, h, W, H):
    """(w,h)를 비율 유지로 (W,H) 안에 넣었을 때 실제 그림이 차지하는 자리.

    반환 (cw, ch, cx, cy, w, h) — 잘라낼 크기·위치와 **되돌릴 원본 크기**.
    ffmpeg의 scale/pad와 **같은 계산**이어야 한다(짝은 함께 정한다). 짝수로 맞추는 것도
    같은 이유다 — libx264(yuv420p)는 홀수 크기를 못 받아 1px씩 어긋난다.
    """
    if not (w and h and W and H):
        return (W or 0, H or 0, 0, 0, w or 0, h or 0)
    f = min(W / w, H / h)
    cw = max(2, int(round(w * f)) // 2 * 2)
    ch = max(2, int(round(h * f)) // 2 * 2)
    return (cw, ch, (W - cw) // 2, (H - ch) // 2, w, h)


def _join_sources(items, work):
    """[(vid, src)] → (합본경로, [(vid, 시작초, 길이초)]). 실패하면 예외.

    ★규격을 통일하지 않으면 concat이 깨진다 — 해상도·fps·SAR을 맞춘다.

    ⚠️ **비율을 지키며** 맞춘다(2026-08-27 실사고). 전엔 `scale=W:H`로 최대 해상도에
      **강제로 늘렸다** — "업스케일 방향이라 원본 손실 없음"이라는 주석이 붙어 있었지만,
      그 가정은 **모든 소스의 비율이 같을 때만** 참이다. 세로와 가로가 섞이면 깨진다.

      실사고(job 6070eddd8a73): 세로 720x1280 · 1080x1920 · 720x1280에 유튜브 가로
      3840x2160이 섞였다. W·H가 3840x2160이 되어 세로 영상이 **가로로 5.3배 늘어난 채**
      청소를 거쳐 돌아왔고, 그걸 세로 1080x1920으로 렌더하니 크게 잘려 나갔다 —
      고객에겐 "원본은 일반영상인데 결과물이 줌한 것처럼 크다"로 보였다.

      그래서 **비율을 지켜 축소·확대하고 남는 곳은 검게 채운다(레터박스)**. 청소는
      화면 내용만 보므로 검은 여백은 무해하다. 그리고 자른 뒤 **원래 크기로 되돌린다**
      (아래 spans의 box) — 여백을 달고 돌아가면 렌더가 그 여백까지 화면으로 친다.
    """
    work = Path(work)
    info = [(vid, src) + _probe_wh_dur(src) for vid, src in items]
    # 세로와 가로를 함께 담으려면 캔버스가 정사각에 가까워진다(예: 1920x1920).
    # ★상한을 둔다 — 4K가 섞이면 3840x3840이 되어 청소 한 번에 수백 MB가 오간다.
    #   최종 결과물은 1080x1920이고, 아래 _split_cleaned가 각 소스를 **원래 크기로**
    #   되돌리므로 캔버스를 키워봐야 최종 화질에 보탬이 없다(디스크·인코딩만 먹는다).
    W = min(max(i[2] for i in info), _JOIN_CANVAS_MAX)
    H = min(max(i[3] for i in info), _JOIN_CANVAS_MAX)
    parts, spans, t = [], [], 0.0
    for idx, (vid, src, w0, h0, dur) in enumerate(info):
        norm = str(work / f"join_norm_{idx}.mp4")
        # 되돌릴 자리(여백을 뺀 실제 그림의 위치·크기)를 **여기서 함께** 정한다.
        # 짝으로 움직이는 값을 따로 계산하면 반드시 어긋난다(0순위-B).
        box = _fit_box(w0, h0, W, H)
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(src),
             "-vf", (f"scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,"
                     f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=30"),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
             "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-ar", "48000", "-ac", "2", norm], check=True)
        # ★길이는 정규화 **후** 다시 잰다 — fps 변환으로 소수점이 밀리면
        #   뒤 소스들의 시작점이 통째로 어긋난다(짝은 함께 정한다).
        _w2, _h2, dur2 = _probe_wh_dur(norm)
        parts.append(norm)
        spans.append((vid, t, dur2, box))
        t += dur2
    lst = work / "join_list.txt"
    lst.write_text("".join("file " + chr(39) + x + chr(39) + chr(10) for x in parts), encoding="utf-8")
    joined = str(work / "join_all.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", joined], check=True)
    return joined, spans


def _split_cleaned(cleaned, spans, work):
    """청소된 합본을 구간별로 잘라 {vid: 경로}. 잘라낸 파일이 비면 예외."""
    work = Path(work)
    out = {}
    for span in spans:
        vid, start, dur = span[0], span[1], span[2]
        box = span[3] if len(span) > 3 else None
        dst = str(work / f"clean_src_{vid}.mp4")
        # ★붙일 때 넣은 검은 여백을 잘라내고 **원래 크기로 되돌린다**(2026-08-27).
        #   여백을 달고 돌려보내면 렌더가 그 여백까지 그림으로 쳐서, 세로 영상이
        #   가로 화면 한가운데 작게 박히거나 반대로 크게 잘린다.
        vf = []
        if box:
            cw, ch, cx, cy, ow, oh = box
            vf.append(f"crop={cw}:{ch}:{cx}:{cy}")
            if (cw, ch) != (ow, oh):
                vf.append(f"scale={ow}:{oh}:flags=lanczos")
            vf.append("setsar=1")
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-i", str(cleaned),
             "-t", f"{dur:.3f}"]
            + (["-vf", ",".join(vf)] if vf else [])
            + ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", dst],
            check=True)
        if not Path(dst).exists() or Path(dst).stat().st_size < 1024:
            raise RuntimeError(f"합본 분할 결과가 비었습니다: {vid}")
        out[vid] = dst
    return out


def _join_batches(items, work):
    """길이 상한에 맞춰 [(vid,src)]를 묶음들로 가른다. 각 묶음이 VMake 1콜이다."""
    batches, cur, cur_sec = [], [], 0.0
    for vid, src in items:
        try:
            _w, _h, dur = _probe_wh_dur(src)
        except Exception:
            dur = 0.0
        if cur and cur_sec + dur > _JOIN_MAX_SEC:
            batches.append(cur)
            cur, cur_sec = [], 0.0
        cur.append((vid, src))
        cur_sec += dur
    if cur:
        batches.append(cur)
    return batches


def _clean_joined(items, keys, work, tag=""):
    """소스 여러 편을 붙여 **VMake 1콜**로 청소 → {vid: 클린경로}, {vid: region}.

    붙이기·청소·자르기 중 어디서 실패하든 예외를 올린다 — 호출부가 옛 방식으로 되돌린다.
    """
    sub = Path(work) / f"join{tag}"
    sub.mkdir(parents=True, exist_ok=True)
    joined, spans = _join_sources(items, sub)
    out = str(sub / "joined_clean.mp4")
    last = None
    for attempt in range(_CLEAN_RETRY + 1):
        try:
            cleaned = _vmake_clean(joined, keys, out)
            break
        except Exception as e:                      # noqa: BLE001 — 재시도 후 상위로
            last = e
            if attempt >= _CLEAN_RETRY:
                print(f"[clean] 합본 최종 실패({attempt + 1}회): {e}", file=sys.stderr)
                raise
            # ★크레딧 소진은 재시도해도 영원히 같다 — _vmake_clean이 이미 등록된 키를
            #   전부 훑고 올린 것이므로 여기서 3번 더 때릴 이유가 없다(2026-08-29).
            from shopping_shorts.vmake_client import is_no_credit
            if is_no_credit(e):
                raise
            print(f"[clean] 합본 실패 — {_CLEAN_RETRY_WAIT}초 뒤 재시도"
                  f"({attempt + 1}/{_CLEAN_RETRY}): {e}", file=sys.stderr)
            time.sleep(_CLEAN_RETRY_WAIT)
    paths = _split_cleaned(cleaned, spans, work)
    regions = {}
    src_map = dict(items)
    for vid, dst in paths.items():
        # region은 원본↔클린을 소스별로 대조해 구한다(합본이 아니라 조각 기준).
        try:
            r = sub_region.detect_erased_region(src_map[vid], dst, work)
        except Exception:                            # noqa: BLE001 — best-effort
            r = None
        if r:
            regions[vid] = r
    return paths, regions


# ── 완성본 1편만 청소(2026-08-26 사장님 "완성본 만들기 된 영상만 딱 자막제거") ──────
# 실측: VMake는 보낸 영상 1초당 약 9초를 쓴다(69초→632초 / 100초→1,692초).
#   소스 전체(100~150초)를 보내던 것을 완성본(30초)으로 바꾸면 **크레딧은 그대로 1콜**인데
#   시간이 4분의 1이 된다. 다른 서비스가 빠른 이유도 최종 결과물 하나만 처리하기 때문이다.
#
# ★재과금을 막는 열쇠는 '편성 서명'이다 — 편성이 그대로면 완성본도 같으니 청소본을 재사용한다.
#   장면을 진짜로 바꿨을 때만 다시 청소(=5P)한다.
_FINAL_CLEAN = os.environ.get("SHORTS_CLEAN_FINAL", "0") == "1"   # ★기본 꺼짐 — 실측 후 켠다


def _beat_materials(b):
    """비트 하나가 **화면에 쓰는 재료** 목록. video_assemble._beat_material과 같은 규칙.

    사람이 편성한 scene_override가 있으면 그것, 없으면 primary + alternates.
    alternates를 빼면 안 된다 — 나레이션이 길면 실제로 화면에 나온다.

    ★같은 판단을 여러 곳에 적으면 어긋난다(0순위-B) — _used_spans·_plan_signature·
      _final_time_of_source가 전부 이 함수를 쓴다.
    """
    over = b.get("scene_override")
    if over:
        return [dict(x) for x in over if x]
    return [x for x in ([b.get("primary")] + list(b.get("alternates") or [])) if x]


def _final_beat_ratios(plan):
    """완성본 타임라인에서 비트마다 차지하는 **비율 구간** [(lo, hi), ...].

    ★왜 초가 아니라 비율인가: 실제 조립 길이는 TTS 길이에 따라 target_seconds와
      달라진다. 비율로 주고 호출부가 실제 영상 길이에 곱하면 위치가 맞는다.
    """
    beats = (plan or {}).get("beats") or []
    if not beats:
        return []
    durs = []
    for b in beats:
        try:
            d = float(b.get("target_seconds") or 0) or 0.0
        except (TypeError, ValueError):
            d = 0.0
        durs.append(d if d > 0 else 2.0)      # 값이 없으면 평균치로 자리만 잡는다
    total = sum(durs)
    if total <= 0:
        return []
    out, t = [], 0.0
    for d in durs:
        out.append((t / total, (t + d) / total))
        t += d
    return out


def _clamp_ratio(v):
    return min(0.98, max(0.02, float(v)))


def _final_time_of_beat(plan, i):
    """완성본에서 **i번째 비트** 한가운데의 비율(0~1). 범위 밖이면 None."""
    rs = _final_beat_ratios(plan)
    if not rs or i < 0 or i >= len(rs):
        return None
    lo, hi = rs[i]
    return _clamp_ratio((lo + hi) / 2.0)


def _final_time_of_source(plan, vid):
    """완성본에서 소스 vid가 **처음 나오는** 지점의 비율(0~1). 없으면 None.

    (2026-08-27) 2단계가 완성본 1편만 청소하게 되면서 소스별 청소본이 없어졌다.
    화면(AFTER 썸네일·꾸미기 배경)을 완성본에서 뽑아야 하는데, 그러려면 그 소스가
    완성본 어디에 있는지 알아야 한다.
    """
    beats = (plan or {}).get("beats") or []
    rs = _final_beat_ratios(plan)
    if not rs:
        return None
    for b, (lo, hi) in zip(beats, rs):
        if any((m or {}).get("video_id") == vid for m in _beat_materials(b)):
            return _clamp_ratio((lo + hi) / 2.0)
    return None


def _final_source_indices(plan, n_sources):
    """완성본에 **실제로 쓰인** 소스의 si 목록(오름차순). 2026-08-27.

    왜 필요한가: 담은 영상이 5개여도 편성에 3개만 들어갈 수 있다. 안 들어간 소스는
    완성본 어디에도 없으므로 AFTER 프레임을 뽑을 수 없다. 그런데 화면은 "영상 1/5"로
    5개를 다 넘겨보게 해서, 안 쓰인 것을 넘기는 순간 엉뚱한 구간이 나왔다
    (사장님 제보 "다른 영상이 나옴" — BEFORE 벽 페인트칠 / AFTER 보라색 매트).

    ★판정을 새로 짜지 않고 _final_time_of_source를 그대로 부른다(0순위-B).
      "완성본에 있나"를 두 군데서 각자 계산하면 언젠가 반드시 어긋난다 —
      목록엔 있는데 시각은 None인 소스가 생기면 증상이 그대로 재발한다.
    """
    out = []
    for i in range(max(0, int(n_sources or 0))):
        if _final_time_of_source(plan, _source_video_id(i)) is not None:
            out.append(i)
    return out


def _clip_sig(clean_final, t0, dur):
    """완성본 조각 1개의 편성 서명(8자). 구간이나 원본이 바뀌면 값이 바뀐다.

    ★캐시가 조용히 옛것을 내주는 사고를 막는 자리다(버그헌트 P1-3). 파일 내용을
      다 읽지 않고 mtime·크기만 본다 — 조각은 완성본이 바뀌면 반드시 다시 만들어지고,
      완성본은 렌더가 새로 쓰므로 mtime이 바뀐다.
    원본을 못 읽어도 자르기 자체는 되어야 하므로(내보내기가 통째로 죽으면 안 된다)
    stat 실패 시 구간만으로 서명한다.
    """
    import hashlib
    try:
        st = Path(clean_final).stat()
        base = f"{int(st.st_mtime)}:{st.st_size}"
    except OSError:
        base = "na"
    return hashlib.md5(f"{base}:{t0:.3f}:{dur:.3f}".encode()).hexdigest()[:8]


def split_final_into_beat_clips(clean_final, timeline, work, prefix="cc"):
    """청소된 **완성본 1편**을 비트 경계로 잘라 {가상 video_id: 경로} (2026-08-27).

    캡컷 내보내기용이다. 캡컷은 소스 파일 + 타임라인 트림 구조라 소스별 청소본이
    필요한데, 완성본 1편만 청소하면 그게 없다. 그래서 **완성본을 컷별로 나눠** 준다.
      - VMake를 다시 부르지 않는다 → 추가 과금 0, 대기 0
      - 대신 컷을 원본 범위 **밖으로 늘리는 편집**은 못 한다(조각 뒤에 여분이 없다)

    경계는 _beat_timeline이 준 t0·dur을 그대로 쓴다 — 렌더가 쓰는 것과 같은 값이라
    조각이 화면과 어긋나지 않는다(여기서 따로 계산하면 어긋난다, 0순위-B).
    """
    work = Path(work)
    out = {}
    for row in timeline or []:
        idx = row.get("beat_idx")
        t0 = float(row.get("t0") or 0.0)
        dur = float(row.get("dur") or 0.0)
        if dur <= 0:
            continue
        vid = f"{prefix}{idx}"
        # ★파일명에 **편성 서명**을 넣는다(2026-08-30, 버그헌트 P1-3).
        #   종전엔 `capcut_clean_cc0.mp4`처럼 서명이 없어, 편성을 고친 뒤 다시 내보내면
        #   **옛 조각**이 그대로 나갔다(오류 0건 — 고객은 "고쳤는데 안 바뀜"만 본다).
        #   서명 = 잘라낼 구간(t0·dur) + 원본 완성본(mtime·크기). 셋 중 하나만 바뀌어도
        #   다른 이름이 되어 다시 자른다. 같으면 그대로 재사용한다(기존 이점 유지).
        dst = work / f"capcut_clean_{vid}_{_clip_sig(clean_final, t0, dur)}.mp4"
        if dst.exists() and dst.stat().st_size > 1024:
            out[vid] = str(dst)                     # 같은 편성이면 다시 안 자른다
            continue
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{t0:.3f}", "-i", str(clean_final),
             "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", str(dst)],
            check=True)
        if not dst.exists() or dst.stat().st_size < 1024:
            raise RuntimeError(f"완성본 분할 결과가 비었습니다: {vid}")
        out[vid] = str(dst)
    return out


def plan_using_beat_clips(plan, clips, timeline, prefix="cc"):
    """편집안을 **조각 기준**으로 바꾼 사본. 각 비트가 자기 조각을 통째로(0~끝) 쓴다.

    조각은 그 비트의 화면을 이미 담고 있으므로 재료를 하나로 접는다 —
    alternates·scene_override를 남기면 캡컷이 없는 파일을 찾는다.

    ★end는 **조각의 실제 길이**(timeline의 dur)다. target_seconds를 쓰면 안 된다 —
      실제 컷 길이는 TTS에 맞춰 달라지므로 조각보다 길거나 짧아 화면이 어긋난다.
    """
    import copy
    durs = {r.get("beat_idx"): float(r.get("dur") or 0.0) for r in (timeline or [])}
    out = copy.deepcopy(plan or {})
    for b in out.get("beats") or []:
        idx = b.get("beat_idx")
        vid = f"{prefix}{idx}"
        if vid not in clips:
            continue
        d = durs.get(idx) or 0.0
        b["primary"] = {"video_id": vid, "seg_id": f"{vid}-0", "start": 0.0,
                        "end": d if d > 0 else None}
        b["alternates"] = []
        b.pop("scene_override", None)
    return out


def final_clip_pairs(plan, tts_paths, src_durs):
    """완성본의 **컷 하나하나**를 (video_id, 원본 시각, 완성본 시각, 길이)로 편다.

    화면 조각 계획은 video_assemble.plan_beat_clips_for **한 곳**에서 온다 —
    렌더·캡컷·ZIP이 쓰는 그 함수다. 여기서 따로 계산하면 또 어긋난다(0순위-B).

    ★왜 필요한가 (2026-08-27, 세 번째 수정):
      비트 하나에 재료가 여럿 섞인다. 실측 job 9a3ff19fbceb의 beat 9는
        [s0 17.0~19.0, s4 5.7~8.2, s0 0.0~1.0, s4 1.1~2.8]
      4조각이 비트 시간을 나눠 갖는다. 그런데 앞선 수정은 '비트 전체'를 그 소스의
      구간으로 취급해, 비트 한가운데(pos=0.5)가 실제로는 **다른 소스** 자리였다.
      → 좌우에 딴 그림이 계속 떴다.
    """
    from shopping_shorts import video_assemble as _va
    out, t = [], 0.0
    for b in (plan or {}).get("beats") or []:
        tts = (tts_paths or {}).get(b.get("beat_idx"))
        try:
            tts_dur = _va._beat_effective_dur(b, tts) if tts else float(
                b.get("target_seconds") or 0) or 0.0
        except Exception:      # noqa: BLE001
            tts_dur = float(b.get("target_seconds") or 0) or 0.0
        if tts_dur <= 0:
            continue
        try:
            clips = _va.plan_beat_clips_for(b, tts_dur, src_durs or {})
        except Exception:      # noqa: BLE001 — 계획을 못 세우면 이 비트는 건너뛴다
            clips = []
        if not clips:
            t += tts_dur
            continue
        for cclip in clips:
            d = float(cclip.get("out_dur") or 0.0)
            if d > 0:
                out.append({"video_id": cclip.get("video_id"),
                            "beat_idx": b.get("beat_idx"),
                            "src": float(cclip.get("start") or 0.0),
                            "fin": t, "dur": d})
            t += d
    return out


def final_time_of_beat(plan, beat_idx, tts_paths=None, src_durs=None):
    """완성본에서 **그 칸의 첫 컷** 한가운데 시각(초). 없으면 None.

    ★비트 단위 근사를 쓰지 않는다(2026-08-27) — 비트에 재료가 여럿 섞이면
      비트 한가운데가 다른 소스 자리다. 화면에 나가는 최소 단위는 컷이다.
    """
    for cclip in final_clip_pairs(plan, tts_paths, src_durs):
        if cclip.get("beat_idx") == beat_idx:
            return cclip["fin"] + cclip["dur"] * 0.5
    return None


def final_pair_for_source(plan, vid, pos=0.5, tts_paths=None, src_durs=None):
    """자막제거 전/후 비교용 — **같은 장면**을 가리키는 (원본 시각, 완성본 시각).

    그 소스가 **처음 나오는 컷** 안의 pos 위치. 없으면 (None, None).

    ★세 번 틀리고 네 번째가 맞았다 — 기록으로 남긴다:
      1) pos를 소스 파일 전체의 비율로 → 원본 50%는 안 쓰인 딴 장면.
      2) pos를 재료 구간(start~end) 안 비율로 → 구간 5.7초인데 컷은 2.69초라
         뒷부분을 짚었다.
      3) pos를 비트 전체 안 비율로 → 비트에 재료가 4개 섞여 다른 소스 자리를 짚었다.
      4) **컷(clip) 단위**로 편다 → 이제야 맞는다. 컷은 화면에 실제로 나가는 최소 단위다.
    """
    try:
        pos = min(1.0, max(0.0, float(pos)))
    except (TypeError, ValueError):
        pos = 0.5
    for cclip in final_clip_pairs(plan, tts_paths, src_durs):
        if cclip["video_id"] == vid:
            d = cclip["dur"]
            return cclip["src"] + d * pos, cclip["fin"] + d * pos
    # ★컷 계획을 못 세웠을 때만 비트 기준으로 물러선다(소스 길이를 못 재는 등).
    #   판정이 목록(_final_source_indices, 비트 기준)보다 엄격하면 "목록엔 있는데 404"가
    #   나서 사장님이 또 헤맨다. 정확도는 떨어져도 같은 장면 근처는 잡는다.
    rs = _final_beat_ratios(plan)
    beats = (plan or {}).get("beats") or []
    if not rs:
        return None, None
    total = sum((float(b.get("target_seconds") or 0) or 2.0) for b in beats)
    for b, (lo, hi) in zip(beats, rs):
        for m in _beat_materials(b):
            if (m or {}).get("video_id") != vid:
                continue
            try:
                st = float(m.get("start"))
            except (TypeError, ValueError):
                return None, None
            d = (hi - lo) * total
            return st + d * pos, lo * total + d * pos
    return None, None


def _clean_strategy(job):
    """자막제거를 **어떤 단위로** 할지 정하는 유일한 자리 (2026-08-27).

      "final"   — 조립된 완성본 1편만 청소한다(기본). 보내는 길이가 30초라 가장 빠르다.
      "sources" — 옛 소스별/합본 청소. 되돌림 스위치가 내려갔거나, 이미 청소된 소스가
                  있어 그걸 그대로 쓰는 게 맞을 때(두 번 과금하지 않는다).

    ★왜 함수로 뽑았나 (0순위-B, 실사고):
      08-26에 완성본 경로를 만들면서 이 판단을 run_render에만 적었다. run_clean_sources
      (2단계 버튼)는 검사하지도 않고 늘 소스별로 청소해, 2단계를 누르는 순간
      clean_sources가 채워지고 3단계는 already=True로 완성본 경로를 건너뛰었다.
      → **2단계를 쓰는 사람에겐 개선이 통째로 없던 것과 같았다**(08-27 로그 실측:
        569MB를 보내 595초). 같은 판단이 두 군데 적히면 반드시 어긋난다.
      호출부는 이 함수만 부른다 — 새 진입 경로가 생겨도 여기 하나만 보면 된다.
    """
    if job.get("clean_sources"):
        return "sources"        # 이미 청소된 소스가 있다 — 재사용한다(재과금 0)
    return "final" if _FINAL_CLEAN else "sources"


def _plan_signature(plan):
    """편집안 → 완성본 **그림**을 결정하는 것만 뽑은 서명(sha1 앞 16자).

    들어가는 것: 비트 순서 · 각 비트의 재료(video_id·start·end) · 컷 길이(target_seconds)
                 · **장면 확대 구도(scene_zoom/pan)** — 잘라내는 자리가 곧 그림이다.
    빠지는 것:  대사·음성·자막 — 화면 그림을 안 바꾸므로 다시 청소할 이유가 없다.

    ★재료 판정은 video_assemble._beat_material과 같은 규칙이다(scene_override 우선).
      여기가 어긋나면 장면을 바꿨는데 옛 청소본이 그대로 나간다.
    ★확대(2026-08-30)도 같은 이유로 반드시 들어가야 한다 — 빼면 배율만 바꿨을 때
      서명이 그대로라 **옛 청소본(확대 전 화면)이 재사용된다**. 실제로 "최종렌더만
      다시 하면 되나"라는 질문에서 이 구멍을 찾았다.
    """
    import hashlib
    from . import video_assemble as _va       # 확대 해석은 저기 한 곳(0순위-B)
    beats = (plan or {}).get("beats") or []
    parts = []
    for b in beats:
        for m in _beat_materials(b):
            parts.append("%s:%s:%s" % (m.get("video_id"), m.get("start"), m.get("end")))
        parts.append("t=%s" % b.get("target_seconds"))
        _z, _px, _py = _va.scene_zoom_of(b)
        if _z > 1.0001:                        # 지정 없으면 아무것도 안 붙인다
            parts.append("z=%.4f,%.5f,%.5f" % (_z, _px, _py))   # → 옛 작업 서명 불변
        parts.append("|")
    return hashlib.sha1("".join(parts).encode("utf-8")).hexdigest()[:16]


def _final_clean_fn(store, job, job_id, work, keys, customer_id=0):
    """assemble에 넘길 clean_fn — **조립된 완성본 1편**을 VMake로 청소한다.

    assemble은 이미 3토막이다: _render_mix(조립) → clean_fn(청소) → _burn_captions(우리 자막).
    그 가운데 자리에 이 함수를 꽂으면 완성본만 청소된다.

    ★같은 편성이면 다시 안 청소한다(재과금 0) — 편성 서명으로 판단하고 파일을 남겨둔다.
    ★과금은 **1콜**이다. 소스가 몇 개든 완성본은 하나다.
    ★실패하면 예외를 올린다 — 호출부(run_render)가 환불하고 상태를 failed로 만든다.
    """
    def _clean(mix_raw):
        sig = _plan_signature(job.get("edit_plan") or {})
        out = Path(work) / f"final_clean_{sig}.mp4"
        if out.exists() and out.stat().st_size > 1024:
            print(f"[clean] 완성본 재사용(편성 그대로, 과금 0): {out.name}", file=sys.stderr)
            return str(out)
        charged = _charge_clean(store, customer_id, 1)
        try:
            print(f"[clean] 완성본 1편만 청소 시작 sig={sig}", file=sys.stderr)
            return _vmake_clean(str(mix_raw), keys, str(out))
        except Exception:
            if charged:
                _refund_clean(store, customer_id, charged)
            raise
    return _clean


def _ensure_clean_sources(store, job, job_id, work, keys, customer_id=0):
    """clean_sources 맵을 채워 반환. 이미 있고 파일이 존재하면 스킵(재과금 0).
    각 스레드는 remove_subtitles만 하고 경로를 반환 → DB 저장은 취합 후 메인에서 1회(경합 없음).

    ★돈이 나가는 함수다 — 청소할 소스 1편당 VMake 1콜(50크레딧)이고
      여기서 **선차감**한다(_charge_clean). 자막제거의 유일한 계량 지점이라
      run_clean_sources·run_render 어느 쪽으로 들어와도 여기를 지난다."""
    source_map = _resolve_sources(job, Path(work))
    cached = dict(job.get("clean_sources") or {})
    # 지워진 자막영역: 소스별 박스 맵 + 1등(primary). 이미 있으면 이어붙인다(재청소 안 한 소스는 유지).
    regions = dict((job.get("clean_regions") or {}).get("sources") or {})
    todo = [(vid, src) for vid, src in source_map.items()
            if not (cached.get(vid) and Path(cached[vid]).exists())]
    # ★쓰이는 구간만 보낸다(2026-08-25, 플래그 뒤 기본 꺼짐).
    #   실측 job e68b1bcf8900: 소스 111.6초를 청소했는데 완성본은 30.3초였다.
    #   VMake 처리 시간은 길이에 비례하므로 안 쓰는 부분을 빼면 그만큼 빨라진다.
    #   자른 뒤 청소한 결과는 _restore_span으로 **원본 타임라인에 되돌려** 놓는다
    #   → 하류(video_assemble)는 종전과 똑같이 동작한다(자를 시각이 안 밀린다).
    #   판정이 애매하면 spans가 None이라 통째로 보낸다(자막을 남기느니 느린 게 낫다).
    span_cuts = {}
    if _SPAN_ENABLED and todo:
        span_cuts = _cut_used_spans(todo, job.get("edit_plan") or {}, work)
    # ★과금은 **VMake 콜 수**로 한다 — 소스 개수가 아니다(2026-08-25 수정).
    #   예전엔 len(todo)로 깎아서, 소스 4개짜리 영상 하나에 20P가 나갔다.
    #   화면 안내는 "영상 1편당 5P"인데 실제로는 4배를 깎던 불일치(실사고).
    #   이제 소스를 붙여 1콜로 보내므로 콜 수 = 묶음 수이고, 보통 1이다.
    batches = _join_batches(todo, work) if (_JOIN_ENABLED and len(todo) > 1) else [[t] for t in todo]
    charged = _charge_clean(store, customer_id, len(batches))
    try:
        if todo:
            done = {}
            for bi, batch in enumerate(batches):
                if len(batch) > 1:
                    try:
                        paths, regs = _clean_joined(batch, keys, work, tag=str(bi))
                        done.update(paths)
                        for vid in dict(batch):
                            if vid in regs:
                                regions[vid] = regs[vid]
                            else:
                                regions.pop(vid, None)
                        continue
                    except Exception as e:      # noqa: BLE001
                        # ★붙이기가 깨져도 고객 작업은 살린다 — 옛 방식(소스별)으로 되돌린다.
                        #   콜이 늘어 비용은 더 들지만, 실패보다 낫다. 로그로 남겨 원인을 본다.
                        print("[clean] 합본 실패 → 소스별로 되돌림: %s" % e, file=sys.stderr)
                        extra = len(batch) - 1      # 이미 1콜분은 깎았다 → 나머지만 추가
                        if extra > 0:
                            charged += _charge_clean(store, customer_id, extra)
                with ThreadPoolExecutor(max_workers=len(batch)) as ex:
                    for vid, out, region in ex.map(lambda t: _clean_one(t, keys, work), batch):
                        done[vid] = out
                        if region:
                            regions[vid] = region
                        else:
                            regions.pop(vid, None)  # 이 소스엔 지속 변화 없음(원본에 자막 없었음)
            # 구간만 잘라 보냈다면 원본 타임라인으로 되돌린다(하류 무변경).
            if span_cuts:
                done = _restore_all(done, span_cuts, source_map, work)
            cached.update(done)
            # 넓고 자주 쓰인 위치를 1번으로 — 소스마다 자막 위치가 달라도 대표 한 자리를 고른다.
            primary = sub_region.pick_primary(list(regions.values()))
            store.update_mix_job(job_id, clean_sources=cached,
                                 clean_regions={"sources": regions, "primary": primary})
    except Exception:
        # ★전액 환불이 의도된 것이다 — 부분 환불로 "고치지" 마라.
        #   소스 3개 중 2번째가 실패해도 1·2번 VMake는 실제로 돌아 1,000원이 나갔다.
        #   그런데 결과를 저장하는 update_mix_job이 이 try 안쪽이라 **아무것도
        #   캐시되지 않는다** — 사용자는 못 쓰는 결과에 돈만 낸 꼴이 되고,
        #   재시도하면 3개분을 다시 낸다. 못 쓰는 작업에 청구하는 게 더 나쁘다.
        #   손실은 "실패 전까지 처리된 소스"로 한정되고 재시도 1회분뿐이다.
        _refund_clean(store, customer_id, charged)
        raise
    return cached


@_owned_job
def assemble_clean_video(job_id, db_path, work_root, clean_fn=None):
    """자막제거(2단계) 후 '자막 없는 조립본'(clean_video_path)을 만들어 DB에 저장하고 경로 반환.
    edit_plan이 없거나 조립 실패면 None. run_clean_sources(2단계)와 썸네일(5단계) 자가치유가
    공유한다 — 이전 조립이 재렌더/재매칭 레이스로 유실돼도 썸네일에서 다시 만들 수 있게(2026-07-21).

    두 가지로 쓰인다:
      clean_fn=None  — 소스가 이미 청소돼 있다(clean_sources). 재조립만 한다(추가과금 0).
      clean_fn 있음  — **원본 소스로 조립한 완성본 1편을 여기서 청소한다**(2026-08-27).
                       소스를 통째로 보내던 것(100~150초)을 완성본(30초)으로 줄이는 경로다.
    """
    store = Store(db_path)
    job = store.get_mix_job(job_id)
    if not job:
        return None
    plan = job.get("edit_plan")
    clean_map = job.get("clean_sources") or {}
    if not plan:
        return None
    if not clean_map:
        # 청소된 소스가 없다 — clean_fn(완성본 1편 청소)이 있으면 **원본**으로 조립해 그걸 청소한다.
        if clean_fn is None:
            return None
        clean_map = _resolve_sources(job, Path(work_root) / job_id)
        if not clean_map:
            return None
    try:
        tts_paths = {b["beat_idx"]: b["tts_path"] for b in plan["beats"] if b.get("tts_path")}
        out_path = Path(work_root) / job_id / "clean_preview.mp4"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # burn_captions=False — 이 조립본은 '자막 없는 clean 배경'(썸네일용)이다. 우리 나레이션
        # 자막을 구우면 썸네일 배경에 글자가 박혀 그 위에 제목을 얹을 수 없다(2026-07-22 사장님
        # 제보: clean_preview.mp4에 나레이션 자막이 박혀 나왔다). 원본 자막은 clean_map(자막제거
        # 소스)이 이미 없앴고, 여기선 우리 자막만 생략한다. 캡션 패스가 빠져 더 빠르기도 하다.
        assemble(plan, tts_paths, clean_map, str(out_path), clean_fn=clean_fn, deco={},
                 cutaway_paths=_resolve_cutaway_paths(store, plan, job.get("customer_id", 0)),
                 sfx_paths=_resolve_sfx_paths(store, plan, job.get("customer_id", 0)),
                 burn_captions=False)
        store.update_mix_job(job_id, clean_video_path=str(out_path))
        return str(out_path)
    except Exception:
        traceback.print_exc(file=sys.stderr)
        if clean_fn is not None:
            raise      # ★유료 청소가 이 안에서 돈다 — 삼키면 실패 사유가 사라진다(08-26 참조)
        return None


@_owned_job
def run_clean_sources(job_id, db_path, work_root):
    """2단계: 각 소스 원본을 VMake로 자막제거해 clean_sources에 캐시.
    BackgroundTasks로 불리므로 예외를 밖으로 안 던진다(clean_status로만 알린다)."""
    store = Store(db_path)
    _gpron = pron_corrections.load(store)
    job = store.get_mix_job(job_id)
    if not job:
        return
    final_fn = None
    try:
        work = Path(work_root) / job_id
        work.mkdir(parents=True, exist_ok=True)
        # ★★청소 전에 TTS를 확정한다 (2026-08-27, 사장님 "장면도 안바꾸고 클릭만 한번씩").
        #   왜: _synthesize_beats는 TTS 실측 발화초로 beat["target_seconds"]를 덮어쓴다
        #   (:552). 그런데 편성 서명(_plan_signature)에 target_seconds가 들어간다.
        #   자막제거가 TTS 확정보다 **먼저**라, 렌더 직전 run_render가 TTS를 보장하는 순간
        #   서명이 바뀌어 **캐시가 무효 → 같은 영상을 두 번 청소**했다.
        #     실측 job 1e6c1e1c8b28: 11:58 clean(sig=b2b36f3d) → 12:05 render(sig=73ab50ef).
        #     그 사이 사용자 조작·다른 작업 0. 3개 job 전부 청소본이 2개씩 남았다.
        #   → 자막제거 쓰는 **모든 고객이 편당 2콜**(VMake 100크레딧)을 쓰고 있었다.
        #   TTS는 어차피 다음 단계에서 필요하니 앞당기는 것뿐 — 추가 비용은 없다.
        #   덤: 2단계 미리보기가 실제 결과와 컷 길이까지 같아진다.
        #   호출 형태는 run_render와 **동일**하게 둔다(0순위-B — 갈리면 서명이 또 어긋난다).
        plan_for_tts = job.get("edit_plan")
        if plan_for_tts and plan_for_tts.get("beats"):
            try:
                _synthesize_beats(plan_for_tts["beats"], work / "tts", voice=job.get("voice"),
                                  skip_existing=True, global_pron=_gpron,
                                  customer_id=job.get("customer_id", 0))
                # ★훅 시작점도 여기서 확정한다 — 조립(_render_mix)이 첫 장면 start를
                #   피크 시점으로 **in-place로 옮긴다**(video_assemble._apply_hook_inpoint).
                #   그게 청소 뒤에 일어나면 서명이 또 바뀌어 렌더에서 재청소된다.
                #   실측 job 579c86e58b4f: clean 때 b0=('s3',0.0,1.8) → render 때 0.1.
                #   그 소수점 한 자리 때문에 VMake가 두 번 돌았다.
                #   렌더가 쓰는 함수를 그대로 부른다(0순위-B — 따로 계산하면 또 갈린다).
                try:
                    from shopping_shorts import video_assemble as _va2
                    _va2._apply_hook_inpoint(
                        plan_for_tts, _resolve_sources(job, work), work)
                except Exception as e2:      # noqa: BLE001 — 훅 이동 실패는 무해
                    print("[clean] 훅 시작점 선확정 건너뜀: %s" % e2, file=sys.stderr)
                store.update_mix_job(job_id, edit_plan=plan_for_tts)
                job = store.get_mix_job(job_id)      # 갱신된 편성으로 아래를 진행
            except Exception as e:      # noqa: BLE001 — TTS 실패가 자막제거를 막지 않는다
                print("[clean] TTS 선확정 실패(계속 진행): %s" % e, file=sys.stderr)
        # ★워커는 HTTP 요청이 없어 request.state가 없다 — job 레코드에서 읽는다.
        customer_id = job.get("customer_id") or 0
        keys = _vmake_keys(store, customer_id)
        if not keys:
            store.update_mix_job(job_id, clean_status="failed",
                                 clean_error="AI 자막 제거 설정이 완료되지 않았습니다 (관리자 문의)")
            return
        # ★완성본 1편만 청소한다(2026-08-27 사장님 "3단계 완성본 30초만 잘라서 돌리는건데
        #   소스별로 안하고"). 소스를 통째로 보내면 100~150초 → 15~22분인데, 완성본은 30초라
        #   같은 1콜로 4~5분이다(VMake 실측: 보낸 1초당 약 9초).
        #   ★실제 청소는 아래 조립의 clean_fn 자리에서 돈다 — assemble이 이미
        #     _render_mix(조립) → clean_fn(청소) → 자막 3토막이라 가운데에 꽂기만 하면 된다.
        #   ★clean_sources는 일부러 비워 둔다 — 그래야 3단계(run_render)가 already=False로
        #     같은 완성본 경로를 타고, 편성이 그대로면 final_clean_{sig}.mp4를 재사용해 과금 0.
        if _clean_strategy(job) == "final":
            final_fn = _final_clean_fn(store, job, job_id, work, keys, customer_id)
        else:
            _ensure_clean_sources(store, job, job_id, work, keys, customer_id)
            store.update_mix_job(job_id, clean_status="ready", clean_error=None)
    except NotEnoughPoints as e:
        store.update_mix_job(job_id, clean_status="failed", clean_error=str(e))
        return
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
    if final_fn is None:
        assemble_clean_video(job_id, db_path, work_root)
        return
    # 완성본 1편 청소 경로 — 유료 청소가 이 조립 안에서 돈다. 실패를 'ready'로 두면 안 된다.
    try:
        out = assemble_clean_video(job_id, db_path, work_root, clean_fn=final_fn)
    except NotEnoughPoints as e:
        store.update_mix_job(job_id, clean_status="failed", clean_error=str(e))
        return
    except Exception as e:  # noqa: BLE001 — BackgroundTasks라 밖에서 아무도 안 받는다
        traceback.print_exc(file=sys.stderr)
        store.update_mix_job(job_id, clean_status="failed", clean_error=str(e))
        return
    if not out:
        store.update_mix_job(job_id, clean_status="failed",
                             clean_error="자막 제거 결과를 만들지 못했습니다")
        return
    store.update_mix_job(job_id, clean_status="ready", clean_error=None)


@_owned_job
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
                          global_pron=_gpron, customer_id=job.get("customer_id", 0))
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


def _thumb_intro_png(job, thumb):
    """영상 앞에 붙일 썸네일 PNG 경로. 고른 것 우선, 안 골랐으면 마지막으로 만든 것.

    ★'고른 썸네일이 어느 파일이냐'는 app._selected_thumb_path가 이미 정하고 있다(8단계
    카드·카톡 전송이 그걸 쓴다). 여기서 경로를 다시 계산하면 언젠가 어긋난다(0순위-B)
    — 그래서 그 함수를 그대로 부르고, 안 골랐을 때만 마지막 결과로 내려앉는다.
    app import는 함수 안에서 한다(최상위면 순환 import)."""
    from shopping_shorts.app import _selected_thumb_path, _thumb_dir
    p = _selected_thumb_path(job)
    if p and Path(p).exists():
        return Path(p)
    results = list((thumb or {}).get("results") or [])
    if not results:
        return None
    d = _thumb_dir(job.get("job_id") or "")
    if d is None:
        return None
    last = d / results[-1]
    return last if last.exists() else None


def is_faststart(path) -> bool:
    """mp4의 moov가 앞쪽(mdat보다 먼저)인지. 아니면 앞부분만 읽는 수집기가 못 읽는다."""
    try:
        with open(path, "rb") as f:
            head = f.read(64)
    except Exception:
        return True                     # 못 읽으면 건드리지 않는다
    i = 0
    while i < len(head) - 8:
        sz = int.from_bytes(head[i:i+4], "big")
        typ = head[i+4:i+8]
        if typ == b"moov":
            return True
        if typ == b"mdat":
            return False                # mdat이 먼저 = moov는 뒤에 있다
        if sz < 8:
            break
        i += sz
    return False                        # 64바이트 안에 moov가 없다 = 뒤에 있다


def ensure_faststart(path):
    """moov가 뒤에 있으면 앞으로 옮긴다. 이미 앞이면 아무것도 안 한다.

    ★렌더 때뿐 아니라 **바깥으로 주소를 내줄 때**도 부른다 — 옛 영상은 렌더를 다시
      돌리지 않는 한 moov가 뒤에 남아 있어서, 렌더에만 걸면 옛 작업이 계속 거절된다
      (Buffer 실측 2026-08-30: 옛 완성본 2건 모두 거절, moov를 앞으로 옮기면 통과).
    """
    if not is_faststart(path):
        _faststart(path)


def _faststart(path):
    """mp4의 moov 원자를 파일 앞으로 옮긴다(-c copy 리멕스). 실패해도 원본을 지키고 넘어간다.

    왜: 스트리밍 수집기(Buffer→인스타 등)는 앞부분만 읽어 영상을 판정한다. moov가 끝에
    있으면 "읽을 수 없다"고 거절한다. 이미 앞에 있으면 그대로 복사할 뿐이라 무해하다.
    """
    p = Path(path)
    if not p.exists():
        return
    tmp = p.with_suffix(".fs.mp4")
    try:
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(p),
                            "-c", "copy", "-movflags", "+faststart", str(tmp)],
                           capture_output=True, text=True)
        if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 0:
            os.replace(str(tmp), str(p))
        else:
            print(f"[faststart] 실패(원본 유지): {(r.stderr or '')[:300]}", file=sys.stderr)
    except Exception:
        traceback.print_exc(file=sys.stderr)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass


@_owned_job
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
                          global_pron=_gpron, customer_id=job.get("customer_id", 0))
        store.update_mix_job(job_id, edit_plan=plan)
        tts_paths = {b["beat_idx"]: b["tts_path"] for b in plan["beats"] if b.get("tts_path")}
        source_video_paths = _resolve_sources(job, work)
        out_path = work / "final.mp4"

        # 자막제거: 소스 원본을 미리(2단계) 또는 여기서(버튼 미사용 시) 청소해 그 소스로 조립한다.
        # mix_raw 위 clean_fn(구방식)은 폐기 — 소스단위여야 TTS/컷과 무관하게 캐시가 성립한다.
        final_clean_fn = None
        if job.get("subtitle_removal"):
            # ★2단계 버튼을 안 거치고 바로 렌더로 오는 경로도 VMake를 탄다 — 여기도 과금해야
            #   구멍이 안 남는다(2단계에서 이미 청소됐으면 todo가 비어 자동으로 0원).
            customer_id = job.get("customer_id") or 0
            keys = _vmake_keys(store, customer_id)
            if not keys:
                raise RuntimeError("자막 제거가 켜져 있으나 설정이 완료되지 않았습니다 (관리자 문의)")
            if _clean_strategy(job) == "final":
                # 완성본 1편만 청소한다(2026-08-26). 소스를 다 지우던 것보다 보내는 길이가
                # 훨씬 짧아 같은 1콜로 몇 배 빠르다. 조립 뒤·우리 자막 앞에서 돈다.
                # 실측(08-27): 완성본 30.5초 → 130초. 합본 569MB를 보내던 것은 595초였다.
                # ★이미 청소된 소스가 있으면 _clean_strategy가 "sources"를 준다 — 두 번 안 낸다.
                final_clean_fn = _final_clean_fn(store, job, job_id, work, keys, customer_id)
                store.update_mix_job(job_id, clean_status="ready", clean_error=None)
            else:
                clean_map = _ensure_clean_sources(store, job, job_id, work, keys, customer_id)
                store.update_mix_job(job_id, clean_status="ready", clean_error=None)
                source_video_paths = {vid: clean_map.get(vid, p)
                                      for vid, p in source_video_paths.items()}

        # deco의 BGM·오버레이 파일을 절대경로로 해석해 넘긴다(캡컷 내보내기와 같은 함수).
        deco = resolve_deco_media(job.get("deco") or {}, work)
        # 템플릿은 job 폴더가 아니라 **정적 자산**이다(모두가 같은 12장을 쓴다).
        # span→dur 변환은 _template_layer 한 곳에서만 한다.
        _first = 0
        try:
            _tb = (job.get("edit_plan") or {}).get("beats") or []
            _first = float(_tb[0].get("dur") or 0) if _tb else 0
        except Exception:
            _first = 0
        _tl = _template_layer(deco.get("template"), first_beat_dur=_first)
        if _tl:
            deco = {**deco, "template": {**(deco.get("template") or {}), **_tl}}
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
        assemble(plan, tts_paths, source_video_paths, str(out_path), clean_fn=final_clean_fn,
                 headcopy=job.get("headcopy"), caption_style=caption_style,
                 deco=deco, cutaway_paths=cutaway_paths, sfx_paths=sfx_paths)
        # 🖼 썸네일을 영상 맨 앞에 붙이기(2026-08-18 사장님 요청, 9단계 체크박스).
        #   켠 경우에만 돈다. 실패해도 렌더 자체는 살린다 — 인트로 때문에 완성 영상을
        #   통째로 잃는 게 더 나쁘다(실패는 로그로만 남기고 원본 final.mp4를 그대로 쓴다).
        _thumb = job.get("thumbnail") or {}
        if _thumb.get("intro"):
            try:
                _png = _thumb_intro_png(job, _thumb)
                if _png:
                    prepend_still(str(out_path), str(_png),
                                                 seconds=float(_thumb.get("intro_sec") or 1.2))
                else:
                    print(f"[thumb-intro] {job_id}: 붙일 썸네일 PNG를 못 찾음", file=sys.stderr)
            except Exception:
                traceback.print_exc(file=sys.stderr)
        # ★moov 앞으로(faststart). 안 하면 moov가 파일 끝에 남아, 헤더만 읽어 판단하는
        #   외부 수집기가 영상을 못 읽는다 — Buffer 실측 2026-08-30:
        #   "Invalid post: Video could not be read from its URL"(HEAD 200인데 거절).
        #   재인코딩이 아니라 -c copy 리멕스라 화질 손실도 시간도 거의 없다.
        #   ★여기 한 곳에서만 한다 — 완성본 경로를 DB에 박는 유일한 출구다(0순위-B).
        ensure_faststart(out_path)
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
    # ★현재 대본의 해시 경로로 쓴다(2026-08-19). 톤·성우만 바꾸는 경로라 대본이 같으면
    #   경로도 같아 **같은 파일을 덮어쓴다**(기존 동작 유지). 캐시는 tts_ver가 깬다.
    #   대본 편집 뒤 호출되면(=/narration 경로) 새 해시로 가므로 어긋남이 남지 않는다 —
    #   예전 beat_{i}.mp3는 어느 대본 것인지 알 수 없어 판정이 영영 불가능했다.
    out = Path(_beat_tts_path(tts_dir, beat))
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
        _ensure_breath_lines(beat)   # 폴백 칸이면 Gemini 호흡 끊기(실패=규칙 폴백)
        words, _wsrc = _beat_words_src(str(out), _rdur, removed=tts_timestamps.load_removed(str(out)))
        _t = None
        if words:
            _t = caption_sync.phrase_durs_from_words(
                beat["narration"], words, _rdur or 0.0,
                preset=beat.get("caption_lines"))
            beat["cap_durs"] = _t.durs if _t else None
            beat["cap_lead"] = _t.lead_in if _t else 0.0
        beat["cap_src"] = _wsrc if (words and _t) else "estimate"
        # ★싱크 마무리 — 렌더가 하던 것을 여기서도 한다(2026-08-20 실사고 job 087e03b69dc2).
        #   대본수정으로 hook 대사가 105자가 돼 mp3가 16.8초가 됐는데 target_seconds는
        #   옛 2.9초 그대로였다. 미리보기는 mp3 실길이를, 편성·예산은 옛 초를 따라가
        #   **초가 두 벌**이 됐고(0순위-B), 화면이 5배 모자라 앞 장면을 되풀이했다
        #   = 사장님이 겪은 "끝나고 계속 반복" · 자막 어긋남. 렌더까지 가야 _conform_beats가
        #   뒤늦게 맞춰줘서 미리보기 단계에선 영영 깨져 보였다.
        #   새 계산을 만들지 않는다 — 렌더가 쓰는 그 함수를 그대로 부른다.
        if _rdur and _rdur > 0:
            beat["target_seconds"] = round(_rdur, 1)
        # 화면 예산을 넘으면 대본을 줄여 다시 굽는다(target_seconds·cap_durs·sync_gap까지
        # _conform_beats가 갱신한다). 한 칸짜리 리스트로 부르므로 앞뒤 문맥은 없지만
        # 판정·교정 규칙은 렌더와 완전히 같다.
        try:
            _conform_beats([beat], tts_dir, voice=voice_override,
                           global_pron=pron_corrections.load(store))
        except Exception:      # noqa: BLE001 — 교정 실패로 재합성을 죽이지 않는다
            traceback.print_exc(file=sys.stderr)
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
                          global_pron=pron_corrections.load(store),
                          customer_id=job.get("customer_id", 0))
        store.update_mix_job(job_id, edit_plan=plan, status="ready_for_review")
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        store.update_mix_job(job_id, status="failed", error=str(e))
