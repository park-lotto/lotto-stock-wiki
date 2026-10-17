# -*- coding: utf-8 -*-
"""연예인 이름 TTS 발음 사전 + 싼 사전 점검 — 이름 구절만 합성해 받아쓰기로 표기를 고른 뒤 본 TTS 를 1회만 부른다 (관제 097, 2026-10-18).

왜: 최은경 편에서 Typecast 가 '최은경'을 '최화정'으로 읽어 TTS 전체를 21번 다시 불렀다. 이름 구절(3~8자) 합성은 전체 문장의 1/10 값이고
받아쓰기는 서버 제미나이(무료 풀)다 — 전체 TTS 전에 이름만 확인하면 재합성 0 이 된다.

    PYTHONUTF8=1 py tools/calcopy/hybrid/name_check.py apply "<tts 글>" 최은경          # 사전 표기로 바꾼 글
    PYTHONUTF8=1 py tools/calcopy/hybrid/name_check.py check 최은경 --voice tc_… [--work 폴더]   # 후보 합성(Typecast, 후보당 1회) → 받아쓰기 → 사전 갱신

판단 주인: 표기 = tools/calcopy/engine/name_dict.json + name_dict.py(10-18 엔진으로 옮김 — preset_make 등 모든 TTS 가 읽는다) · pick()(어느 후보가 맞는가 = 받아쓰기 글에 이름이 그대로 들어 있는 모델 수).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.hybrid.common import StageError, jsave  # noqa: E402
from tools.calcopy.engine import name_dict as ND  # noqa: E402

DICT = ND.DICT
CANDIDATES = ["{n}", "{n} 씨", "방송인 {n} 씨", "{s}, {g}", "방송인, {s}, {g} 씨", "{s}, {g}이"]   # 최은경 편에서 통한 꼴 순서
PHRASE = "{c}가 직접 산 거예요."       # 이름 뒤에 조사·문장을 붙여 자연스럽게 읽히게(홑 낱말 합성은 억양이 다르다)


load = ND.load
spelling = ND.spelling
apply = ND.apply            # 읽는 글(tts)에서 이름을 사전 표기로. 자막(text)은 건드리지 않는다.


def _norm(t: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", t or "")


def pick(name: str, results: list[dict]) -> dict | None:
    """results = [{"cand": 표기, "texts": [모델별 받아쓰기]}] → 이름이 그대로 들린 모델 수가 가장 많은 후보(전 모델 일치 우선, 순서 앞 우선)."""
    best = None
    for r in results:
        hits = sum(1 for t in r["texts"] if name in _norm(t))
        score = (hits == len(r["texts"]) and hits > 0, hits)
        if best is None or score > best[0]:
            best = (score, r)
    return None if best is None or best[0][1] == 0 else best[1]


def check(name: str, voice_id: str, work: Path, tempo: float | None = None, log=print) -> dict:
    """후보 표기마다 이름 구절 1회 합성(Typecast) → 서버 받아쓰기(모델 2개) → 맞는 표기를 사전에 적는다. 사전에 그 성우 표기가 이미 있으면 안 부른다."""
    from tools.calcopy.hybrid import server_ai
    d = load()
    ent = d["names"].setdefault(name, {"tts": name, "bad": [], "voices": {}})
    if voice_id in (ent.get("voices") or {}):
        log(f"[name_check] 사전에 있음: {name} → {ent['voices'][voice_id]} ({voice_id})")
        return {"name": name, "tts": ent["voices"][voice_id], "from": "dict"}
    from shopping_shorts.channelkit import providers
    synth = providers.typecast_synth(voice_id, tempo=tempo)
    work = Path(work); work.mkdir(parents=True, exist_ok=True)
    s, g = name[0], name[1:]
    cands = [c.format(n=name, s=s, g=g) for c in CANDIDATES]
    results = []
    for k, c in enumerate(cands):
        mp3 = work / f"name_{k}.mp3"
        if not mp3.exists():
            synth(PHRASE.format(c=c), str(mp3))
        res = server_ai.asr_clips(mp3, None)
        texts = server_ai.texts_of(res, 0)
        results.append({"cand": c, "texts": texts, "models": res.get("ok_models")})
        log(f"[name_check] {c!r} → {texts}")
        if len(texts) >= 2 and all(name in _norm(t) for t in texts):
            break                                             # 첫 후보가 전 모델 일치면 그만(싼 쪽)
    best = pick(name, results)
    bad = sorted({_norm(t)[:len(name) + 1] for r in results for t in r["texts"] if name not in _norm(t) and _norm(t)})
    ent.setdefault("bad", [])
    for b in bad:
        if b and b not in ent["bad"]:
            ent["bad"].append(b)
    ent["candidates_tried"] = sorted(set(ent.get("candidates_tried", []) + cands[:len(results)]))
    if best is None:
        ND.save(d)
        raise StageError(f"이름 {name} 을 또렷하게 읽는 표기를 못 찾았다: {results}")
    ent.setdefault("voices", {})[voice_id] = best["cand"]
    if ent.get("tts", name) == name:
        ent["tts"] = best["cand"]
    import time
    ent["verified"] = f"{time.strftime('%Y-%m-%d')} name_check {voice_id} 후보 {len(results)}개 → {best['cand']!r} {best['texts']}"
    ND.save(d)
    jsave(work / "name_check.json", {"name": name, "voice": voice_id, "results": results, "picked": best})
    return {"name": name, "tts": best["cand"], "results": results}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("apply"); a.add_argument("text"); a.add_argument("name"); a.add_argument("--voice")
    c = sub.add_parser("check"); c.add_argument("name"); c.add_argument("--voice", required=True); c.add_argument("--work", default="C:/숏템_칼카피/yanshottem/_name_check"); c.add_argument("--tempo", type=float)
    x = ap.parse_args()
    if x.cmd == "apply":
        print(apply(x.text, x.name, x.voice))
    else:
        print(json.dumps(check(x.name, x.voice, Path(x.work) / x.name, x.tempo), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
