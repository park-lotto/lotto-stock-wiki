# -*- coding: utf-8 -*-
"""나레 TTS 와 글자 시각 맞춤의 주인 한 곳 (관제 097, 2026-10-18) — ① 합성 캐시(글·목소리·배속 해시) ② 타입캐스트 글자별 시각(align) 보관
③ align 없는 옛 합성본은 문장부호 ↔ 소리 틈 짝짓기(여러 문턱 틈 후보 + 동적 계획)로 어림.

왜: 10-18 손태영 편 — 잇썸 문장 자르기가 쉼표 쉼을 문장 끝으로 골라 B2 4.7자/초·B4 23.9자/초, 재미썸 문장부호 쉼 찾기가 세 번 멈춤(Typecast 가
마침표 뒤에 안 쉬고 구절 가운데서 쉼 — −40dB 무음만으론 못 찾음), auto_tempo 가 끝 문장 시작을 '마지막 말 구간'으로 잡아 rate_last 14.3.
또 줄 tts 를 고쳐도 narr_full.mp3 가 있으면 옛 소리를 그대로 썼다(파일 유무로만 재합성 판단).
→ 합성은 **타임스탬프 엔드포인트**(typecast_tts.synthesize, 추가 과금 없음)로 글자 시각을 받아 두고, 문장 경계·문장부호 자리·끝 문장 시작을
  소리 짐작이 아니라 **글자 시각**으로 정한다. 캐시 열쇠 = md5(글|목소리|배속|모델) — 글이 바뀌면 다시 합성(사이드카 <mp3>.tts.json).
  align 이 없을 때(옛 합성본·403)만 dips()+match_punct() 로 어림하고, 그 사실을 결과에 적는다.

    from tools.calcopy.engine import narr_align as NA
    align = NA.synth_cached(text, voice_id, tempo, out_mp3)          # dict|None (None = 타임스탬프 못 받음 — 옛 방식으로)
    NA.punct_slots(text, align)   → [(kind, a, b)]  문장부호마다 앞 글자 끝·뒤 글자 시작(초, 합성본 기준) — 마지막 마침표 포함
    NA.dips(audio)                → [(a, b)]  여러 문턱(−40/−32/−26dB)의 틈 후보 합집합
    NA.match_punct(marks, before, total, dips, t0, t1) → [(kind, (a,b)|None)]  차례를 지키는 짝짓기 중 말속도가 가장 고른 것
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TTS_MODEL = "ssfm-v30"
TTS_CONCURRENCY = int(os.environ.get("CALCOPY_TTS_CONCURRENCY", "2"))   # Typecast 동시 합성 상한 — 10-18 한혜진: 6개 동시 → 429
_TTS_SEM = threading.BoundedSemaphore(TTS_CONCURRENCY)
_LOCK_DIR = Path(os.environ.get("TEMP") or "/tmp") / "calcopy_tts_lock"
PUNCT_RE = re.compile(r"[,.?!]")
NORM = {"?": ".", "!": ".", ",": ",", ".": "."}


# ── 합성 캐시 ────────────────────────────────────────────────────────────
def cache_key(text: str, voice_id: str, tempo: float | None, model: str = TTS_MODEL) -> str:
    return hashlib.md5(f"{text}|{voice_id}|{tempo}|{model}".encode("utf-8")).hexdigest()


def voice_of(voice_id: str, provider: str | None = None, emotion: str | None = None) -> tuple[str | None, str | None]:
    """(provider, emotion) — 판단 주인은 engine/voices(provider_of·emotion_of: 명시 provider 우선, 없으면 voice_id 꼴 · 'normal'=감정 없음)."""
    from tools.calcopy.engine import voices as VO
    return VO.provider_of({"voice_id": voice_id, **({"provider": provider} if provider else {})}), VO.emotion_of({"emotion": emotion})


def old_path(voice_id: str, provider: str | None = None, emotion: str | None = None) -> bool:
    """이 파일이 원래 합성하던 길인가 — 타입캐스트 tc_ / 일레븐 미나 kr-(서버·회원 키 _synth_eleven), 감정 없음. 그 밖(감정·피쉬·일레븐 검색 성우)은
    회원 목소리 넓히기(관제 266)의 provider 분기 주인 preset_make.make_synth 로 간다(타입캐스트 감정만 글자 시각 때문에 여기 typecast_tts 로)."""
    prov, emo = voice_of(voice_id, provider, emotion)
    return emo is None and (prov is None or (prov == "typecast" and not is_eleven(voice_id)) or (prov == "elevenlabs" and is_eleven(voice_id)))   # 꼴 모르는 옛 id = 옛 타입캐스트 길 그대로


def voice_key(text: str, voice_id: str, tempo: float | None, model: str = TTS_MODEL, provider: str | None = None, emotion: str | None = None) -> str:
    """캐시 열쇠 주인(이 파일 캐시) — 옛 길(old_path)은 옛 cache_key 그대로(받아 둔 캐시 무효 금지, preset_make.tts_key 와 같은 원칙), 그 밖은 provider·감정까지."""
    if old_path(voice_id, provider, emotion):
        return cache_key(text, voice_id, tempo, model)
    prov, emo = voice_of(voice_id, provider, emotion)
    return hashlib.md5(f"{text}|{voice_id}|{tempo}|{model}|{prov}|{emo}".encode("utf-8")).hexdigest()


def sidecar_of(mp3) -> Path:
    return Path(str(mp3) + ".tts.json")


def load_align(mp3) -> dict | None:
    sc = sidecar_of(mp3)
    if not sc.exists():
        return None
    try:
        return json.loads(sc.read_text(encoding="utf-8")).get("align")
    except ValueError:
        return None


def _proc_slots() -> list:
    """프로세스끼리도 동시 합성 상한을 지킨다 — 디렉터리 안 잠금 파일(O_EXCL) 슬롯. 60초 넘은 잠금은 죽은 것으로 보고 치운다."""
    _LOCK_DIR.mkdir(parents=True, exist_ok=True)
    while True:
        for k in range(TTS_CONCURRENCY):
            lk = _LOCK_DIR / f"slot{k}.lock"
            try:
                if lk.exists() and time.time() - lk.stat().st_mtime > 600:
                    lk.unlink()
                fd = os.open(str(lk), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode()); os.close(fd)
                return [lk]
            except FileExistsError:
                continue
        time.sleep(1.0)


def synth_cached(text: str, voice_id: str, tempo: float | None, out_mp3, model: str = TTS_MODEL, log=print,
                 provider: str | None = None, emotion: str | None = None) -> dict | None:
    """합성 1회(캐시) → align|None. 캐시 열쇠가 다르면(글·목소리·배속 바뀜) 다시 합성하고 그 사실을 로그에 적는다.
    사이드카 없는 옛 mp3 는 '그 글로 만든 것'으로 받아들여 사이드카만 적는다(유료 재합성 금지 — 10-18 진행 중인 편들).
    provider·emotion(회원 팩 tts, 관제 266): 옛 길(old_path)이면 옛 그대로, 아니면 열쇠에 넣고 합성은 아래 _synth_member."""
    out = Path(out_mp3)
    key = voice_key(text, voice_id, tempo, model, provider, emotion)
    sc = sidecar_of(out)
    if out.exists() and out.stat().st_size > 1000:
        if sc.exists():
            try:
                meta = json.loads(sc.read_text(encoding="utf-8"))
            except ValueError:
                meta = {}
            if meta.get("key") == key:
                return meta.get("align")
            log(f"[tts] 글·목소리·배속이 바뀌어 다시 합성: {out.name} (옛 {meta.get('key', '')[:8]} → {key[:8]})")
            bak = out.with_name(out.stem + f"_old_{meta.get('key', 'x')[:8]}.mp3")
            try:
                out.replace(bak)
            except OSError:
                pass
        else:
            meta = {"key": key, "text": text, "voice": voice_id, "tempo": tempo, "model": model, "align": None, "legacy": True,
                    "at": time.strftime("%Y-%m-%d %H:%M:%S"), "note": "사이드카 없는 옛 합성본을 그대로 받아들임(글자 시각 없음 → 소리 틈 어림)"}
            sc.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
            log(f"[tts] 옛 합성본 재사용(글자 시각 없음): {out.name}")
            return None
    if not old_path(voice_id, provider, emotion):
        return _synth_member(text, voice_id, tempo, out, key, model, log, *voice_of(voice_id, provider, emotion))
    if is_eleven(voice_id):
        return _synth_eleven(text, voice_id, tempo, out, key, model, log)
    from shopping_shorts import typecast_tts
    from shopping_shorts.channelkit import providers
    key_tc = providers.typecast_key(None)
    if not key_tc:
        raise RuntimeError("Typecast 키가 없다(~/.volcano/keys/typecast 또는 TYPECAST_API_KEY)")
    typecast_tts.api_key = lambda *a, **k: key_tc
    locks = _proc_slots()
    try:
        with _TTS_SEM:
            t0 = time.time()
            align = typecast_tts.synthesize(text, str(out), voice_id=voice_id, speed=tempo, model_id=model)
    finally:
        for lk in locks:
            try:
                lk.unlink()
            except OSError:
                pass
    meta = {"key": key, "text": text, "voice": voice_id, "tempo": tempo, "model": model, "align": align, "legacy": False,
            "at": time.strftime("%Y-%m-%d %H:%M:%S"), "sec": round(time.time() - t0, 1)}
    sc.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    log(f"[tts] Typecast 1회 {meta['sec']}초 → {out.name} (글자 시각 {'있음' if align else '없음'})")
    return align


# ── 글자 시각 → 문장부호 자리 ───────────────────────────────────────────
def is_eleven(voice_id: str) -> bool:
    """일레븐랩스 목소리 = voice_presets 의 프리셋 id('kr-mina-expressive' 꼴). 타입캐스트는 'tc_…' 성우 id — 10-18 사장님 '잇썸홈판은 일레븐랩스 미나'."""
    return str(voice_id or "").startswith("kr-")


def fixed_tempo(voice_id: str) -> float | None:
    """일레븐랩스 프리셋의 배속 = 서비스 규칙 voice_presets.json default_speed(미나 1.35) 그대로 — 자/초로 재보정하지 않는다
    (shopping_shorts/voice_presets.py: '미나 1.35 = 6.87자/초, 귀에는 다른 목소리 1.25 와 같다. 숫자로 재보정하지 마라'). 타입캐스트는 None(목표 자/초로 맞춘다)."""
    if not is_eleven(voice_id):
        return None
    d = json.loads((ROOT / "shopping_shorts/assets/voice_presets.json").read_text(encoding="utf-8"))
    rows = d if isinstance(d, list) else next(iter(d.values()))
    p = next((x for x in rows if x.get("preset_id") == voice_id), None)
    if not p or not p.get("default_speed"):
        raise RuntimeError(f"voice_presets 에 배속이 없다: {voice_id}")
    return float(p["default_speed"])


def eleven_direct(text: str, preset_id: str, out: Path, api_key: str) -> dict | None:
    """회원 PC(사장님 10-21 '미나 = 회원 본인 일레븐랩스 키'): 회원 키로 일레븐랩스를 직접 — 요청 꼴은 서버 서비스와 같다
    (shopping_shorts/tts.py synthesize_tts: POST /v1/text-to-speech/<voice>/with-timestamps · xi-api-key · {text, model_id, voice_settings}, v3 는 use_speaker_boost 뺌).
    성우 값 주인 = voice_presets.json(base_voice_id·model_id·voice_settings). 속도는 1.0 — 배속은 렌더러 atempo(미나 1.35 고정)."""
    import base64
    import urllib.error
    import urllib.request
    d = json.loads((ROOT / "shopping_shorts/assets/voice_presets.json").read_text(encoding="utf-8"))
    rows = d if isinstance(d, list) else next(iter(d.values()))
    p = next((x for x in rows if x.get("preset_id") == preset_id), None)
    if not p and re.fullmatch(r"[A-Za-z0-9]{20}", str(preset_id or "")):   # 일레븐 검색 성우 id(관제 266) — 추천 프리셋 밖. 모델 = 숏템 tts.py 기본값(실합성 미확인)
        p = {"base_voice_id": preset_id, "model_id": "eleven_multilingual_v2"}
    if not p:
        raise RuntimeError(f"voice_presets 에 없는 일레븐랩스 성우: {preset_id}")
    settings = dict(p.get("voice_settings") or {})
    if "v3" in (p.get("model_id") or ""):
        settings.pop("use_speaker_boost", None)
    body = json.dumps({"text": text, "model_id": p["model_id"], **({"voice_settings": settings} if settings else {})}).encode("utf-8")
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{p['base_voice_id']}/with-timestamps", data=body, method="POST",
                                 headers={"xi-api-key": api_key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        why = {401: "일레븐랩스 키가 맞지 않습니다", 402: "일레븐랩스 크레딧이 부족합니다", 429: "일레븐랩스 사용량 한도에 걸렸습니다"}.get(e.code, f"일레븐랩스 오류 {e.code}")
        raise RuntimeError(why) from None
    if not data.get("audio_base64"):
        raise RuntimeError("일레븐랩스 응답에 소리가 없습니다")
    Path(out).write_bytes(base64.b64decode(data["audio_base64"]))
    return data.get("alignment")


def _synth_member(text: str, voice_id: str, tempo, out: Path, key: str, model: str, log, prov: str | None, emo: str | None) -> dict | None:
    """옛 길 밖 목소리(관제 266) — 타입캐스트 감정 = 타임스탬프 엔드포인트(typecast_tts.synthesize, 글자 시각 유지 · 요청 꼴 주인 typecast_tts.build_payload)
    · 일레븐 검색 성우·피쉬 = preset_make.make_synth(provider 분기 주인, 회원 키). make_synth 가 글자 시각을 돌려주면(일레븐) 그대로, 아니면 None(소리 틈 어림)."""
    locks = _proc_slots()
    try:
        with _TTS_SEM:
            t0 = time.time()
            if prov == "typecast":
                from shopping_shorts import typecast_tts
                from shopping_shorts.channelkit import providers
                key_tc = providers.typecast_key(None)
                if not key_tc:
                    raise RuntimeError("Typecast 키가 없다(~/.volcano/keys/typecast 또는 TYPECAST_API_KEY)")
                typecast_tts.api_key = lambda *a, **k: key_tc
                align = typecast_tts.synthesize(text, str(out), voice_id=voice_id, speed=tempo, model_id=model, emotion=emo)
            else:
                from tools.calcopy.engine import preset_make as PM
                r = PM.make_synth(prov, voice_id, tempo, emo)(text, str(out))
                align = r if isinstance(r, dict) else None
    finally:
        for lk in locks:
            try:
                lk.unlink()
            except OSError:
                pass
    meta = {"key": key, "text": text, "voice": voice_id, "tempo": tempo, "model": model, "provider": prov, "emotion": emo, "align": align, "legacy": False,
            "at": time.strftime("%Y-%m-%d %H:%M:%S"), "sec": round(time.time() - t0, 1)}
    sidecar_of(out).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    log(f"[tts] {prov} {voice_id}" + (f" 감정 {emo}" if emo else "") + f" 1회 {meta['sec']}초 → {out.name} (글자 시각 {'있음' if align else '없음'})")
    return align


def _synth_eleven(text: str, preset_id: str, tempo, out: Path, key: str, model: str, log) -> dict | None:
    """일레븐랩스는 서버에서 합성하고 mp3·글자 시각만 받는다(키 반출 금지 — 주인 tools/calcopy/mina_tts). 배속은 렌더러 atempo 가 맞춘다.
    회원 PC(CALCOPY_CUSTOMER_MODE=1) = 회원 일레븐랩스 키로 직접(eleven_direct) — 서버를 부르지 않는다."""
    import os
    tone = preset_id.rsplit("-", 1)[-1]
    customer = os.environ.get("CALCOPY_CUSTOMER_MODE") == "1"
    if customer and not os.environ.get("ELEVENLABS_API_KEY") and os.environ.get("CALCOPY_DEV_MINA_SERVER") == "1":
        customer = False      # 개발 PC 시험 전용(10-21) — 회원 일레븐랩스 키 자리를 서버 미나로 흉내. mina_tts(서버 SSH)는 설치본에 없다
    if customer and not os.environ.get("ELEVENLABS_API_KEY"):
        raise RuntimeError("이 목소리(미나)는 일레븐랩스 키가 필요합니다 — 설정 화면 '소리'의 '목소리 키(일레븐랩스)'에 넣어 주세요")
    if not customer and not preset_id.startswith("kr-mina-"):
        raise RuntimeError(f"서버 합성 도구는 미나만 받는다: {preset_id}")
    locks = _proc_slots()
    try:
        with _TTS_SEM:
            t0 = time.time()
            if customer:
                align = eleven_direct(text, preset_id, out, os.environ["ELEVENLABS_API_KEY"])
            else:
                from tools.calcopy import mina_tts
                _, align = mina_tts.synth_align(text, str(out), tone)
    finally:
        for lk in locks:
            try:
                lk.unlink()
            except OSError:
                pass
    meta = {"key": key, "text": text, "voice": preset_id, "tempo": tempo, "model": model, "align": align, "legacy": False,
            "at": time.strftime("%Y-%m-%d %H:%M:%S"), "sec": round(time.time() - t0, 1), "engine": "elevenlabs(회원 키)" if customer else "elevenlabs(서버)"}
    sidecar_of(out).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    log(f"[tts] 일레븐랩스 {preset_id} 1회 {meta['sec']}초 → {out.name} (글자 시각 {'있음' if align else '없음'})")
    return align


def punct_marks(text: str) -> list[tuple[str, int]]:
    """글의 문장부호 순서대로 (종류, 앞까지 읽는 글자 수). ?·! 은 마침표."""
    out = []
    for m in PUNCT_RE.finditer(text):
        out.append((NORM[m.group()], len(re.findall(r"[가-힣A-Za-z0-9]", text[:m.start()]))))
    return out


def ends_with_mark(text: str) -> bool:
    """(판단 주인 — 줄 끝 문장부호) 줄 글이 문장부호(PUNCT_RE)로 끝나나. 이어 붙여 합성한 소리를 글자 시각으로 줄마다 자를 때
    줄 끝 = 그 줄 마지막 부호라서, 끝에 부호가 없으면 다음 줄 소리가 밀린다(98 #75). 대본 단계(script_audit.text_defects)와
    합성 뒤 자르기(render_itssum.split_by_align)가 이 함수 하나를 부른다."""
    return bool(PUNCT_RE.fullmatch((text or "").rstrip()[-1:]))


def punct_slots(text: str, align: dict) -> list[tuple[str, float, float]]:
    """align(characters·start·end) 에서 문장부호마다 (종류, 앞 글자 끝, 뒤 글자 시작). 주인은 engine/tts_pause.pause_slots — 글 끝 마침표는 (끝, 끝)."""
    from tools.calcopy.engine import tts_pause as TP
    ch = align["characters"]; e = align["character_end_times_seconds"]
    slots = list(TP.pause_slots(align))
    marks = punct_marks(text)
    if len(slots) == len(marks) - 1 and marks and marks[-1][0] == ".":       # 글 끝 마침표(뒤 글자 없음)
        last = max(float(x) for x in e)
        slots.append((".", last, last))
    if len(slots) != len(marks):
        raise ValueError(f"글자 시각의 문장부호 수({len(slots)})와 글({len(marks)})이 다르다")
    return slots


def speech_bounds(align: dict) -> tuple[float, float]:
    """첫 글자 시작·마지막 글자 끝(초)."""
    ch = align["characters"]; s = align["character_start_times_seconds"]; e = align["character_end_times_seconds"]
    idx = [i for i, c in enumerate(ch) if not c.isspace() and c not in ",.?!"]
    return float(s[idx[0]]), float(e[idx[-1]])


# ── align 없을 때: 소리 틈 후보 + 짝짓기 ──────────────────────────────────
def _silences(audio, noise: str, d: float) -> list[tuple[float, float]]:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(audio), "-af", f"silencedetect=n={noise}:d={d}", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL).stderr
    st = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", r)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r)]
    dur = duration(audio)
    return list(zip(st, en + [dur] * (len(st) - len(en))))


def duration(audio) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(audio)],
                                capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout.strip() or 0)


DIP_PENALTY = 0.35       # 얕은 문턱(−32·−26dB) 틈 하나당 짝짓기 비용 가산(단계마다) — 10-18 손태영: 가산 없이 섞으면 −26dB 잔틈(0.04초)을 진짜 쉼(0.26초) 대신 골랐다


def dips(audio, d: float = 0.06, levels=(("-40dB", None), ("-32dB", 0.05), ("-26dB", 0.04))) -> list[tuple[float, float, int]]:
    """틈 후보 = 여러 문턱의 무음 합집합 (a, b, 깊이 단계 0=−40dB·1=−32·2=−26 — 겹치면 가장 깊은 문턱 것으로).
    10-18 손태영 재미썸: '거.|한국' 사이가 −25dB 에서만 0.07초 — −40dB 만으론 못 찾았다. 얕은 틈은 DIP_PENALTY 로 뒤로 민다."""
    out: list[tuple[float, float, int]] = []
    for lv, (noise, dd) in enumerate(levels):
        for a, b in _silences(audio, noise, dd if dd is not None else d):
            if any(x[0] - 0.02 <= a <= x[1] + 0.02 or x[0] - 0.02 <= b <= x[1] + 0.02 or (a <= x[0] and b >= x[1]) for x in out):
                continue
            out.append((a, b, lv))
    return sorted(out)


def dip_level(s) -> int:
    return int(s[2]) if len(s) > 2 else 0


def match_punct(marks: list[str], before: list[int], total: int, dips_: list[tuple[float, float]], t_start: float, t_end: float,
                skip_cost=None) -> tuple[list[tuple[str, tuple[float, float] | None]], float]:
    """문장부호 ↔ 틈 짝짓기(차례 유지, 동적 계획). 비용 = 부호 사이 구간마다 (말한 시간당 글자 ÷ 평균 − 1)² + 건너뜀(쉼표 0.15 · 마침표 0.6).
    반환 ([(종류, (a,b)|None)…], 평균 말속도). None = 그 자리에 쉼이 없다(글자 수 비례로 어림한 시각은 predict() 로)."""
    skip_cost = skip_cost or {",": 0.15, ".": 0.6}
    sil = sorted(s for s in dips_ if s[0] > t_start + 0.05 and s[1] < t_end - 0.05)

    def talk(a, b):
        return (b - a) - sum(max(0.0, min(e, b) - max(s, a)) for s, e in sil)
    mean = total / max(talk(t_start, t_end), 0.1)

    def cost(c0, t0, c1, t1):
        tk = talk(t0, t1)
        if tk <= 0.05:
            return 9e9
        return (((c1 - c0) / tk) / mean - 1) ** 2
    M, K = len(marks), len(sil)
    INF = 9e18
    sys.setrecursionlimit(max(10000, sys.getrecursionlimit()))

    @lru_cache(None)
    def go(i, last_j, c0):
        t0 = sil[last_j][1] if last_j >= 0 else t_start
        if i == M:
            return cost(c0, t0, total, t_end), ()
        best = (INF, ())
        v, path = go(i + 1, last_j, c0)
        best = min(best, (v + skip_cost[marks[i]], (None,) + path))
        for j in range(last_j + 1, K):
            cv = cost(c0, t0, before[i], sil[j][0])
            if cv >= 9e9:
                continue
            v, path = go(i + 1, j, before[i])
            best = min(best, (v + cv, (j,) + path))
        return best
    v, path = go(0, -1, 0)
    if v >= INF or len(path) != M:
        raise ValueError("문장부호 짝짓기 실패(틈 후보 없음)")
    return [(k, (sil[j] if j is not None else None)) for k, j in zip(marks, path)], mean


def predict_none(pairs: list, before: list[int], total: int, t_start: float, t_end: float) -> list[tuple[str, tuple[float, float]]]:
    """None 자리(쉼 없는 부호)를 이웃 짝 사이 글자 수 비례로 어림해 (t, t) 로 채운다 — 쉼을 거기에 새로 넣기 위해."""
    out = []
    for i, (k, sl) in enumerate(pairs):
        if sl is not None:
            out.append((k, sl)); continue
        pa = next(((pairs[j][1][1], before[j]) for j in range(i - 1, -1, -1) if pairs[j][1] is not None), (t_start, 0))
        pb = next(((pairs[j][1][0], before[j]) for j in range(i + 1, len(pairs)) if pairs[j][1] is not None), (t_end, total))
        frac = (before[i] - pa[1]) / max(1, pb[1] - pa[1])
        t = pa[0] + (pb[0] - pa[0]) * frac
        out.append((k, (t, t)))
    return out
