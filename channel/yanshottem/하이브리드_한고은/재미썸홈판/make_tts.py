# -*- coding: utf-8 -*-
"""타입캐스트 필재 1회 합성 → 앞 한마디 / 뒤 나레로 가른다(관제 097). narr_full.mp3 가 있으면 다시 안 부른다.
    PYTHONUTF8=1 py channel/yanshottem/하이브리드_한고은/재미썸홈판/make_tts.py
"""
import json
import re
import subprocess
import sys
from pathlib import Path

D = Path(__file__).resolve().parent
ROOT = D.parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(D))
import make_plan as MP  # noqa: E402

R = MP.W / "render"
VOICE = "tc_68257f68bc6e3c161ab5078d"   # 필재(재미썸홈 정본)
TTS_TEMPO = 1.4                          # 작품1 수정본과 같은 Typecast output.audio_tempo


def run(cmd):
    return subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace")


def dur_of(p):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).stdout.strip())


def silences(p, db=-40, d=0.12):
    e = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(p), "-af", f"silencedetect=n={db}dB:d={d}", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL).stderr
    st = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", e)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", e)]
    return list(zip(st, en))


TRIM = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02"
MID = "silenceremove=stop_periods=-1:stop_duration=0.15:stop_threshold=-45dB:stop_silence=0.1"


def main():
    R.mkdir(parents=True, exist_ok=True)
    front = MP.FRONT_TTS["tts"]
    back = [s for _, s in MP.LINES]
    text = " ".join([front] + back)
    full = R / "narr_full.mp3"
    if not full.exists():
        from shopping_shorts.channelkit import providers
        providers.typecast_synth(VOICE, tempo=TTS_TEMPO)(text, str(full))
        print("TTS 1회:", full)
    df = dur_of(full)
    sil = silences(full)
    nf, nall = MP.nchar(front), MP.nchar(text)
    exp = df * nf / nall
    cut = min((s for s in sil if s[0] > 0.5 and s[1] < df - 0.5), key=lambda s: abs((s[0] + s[1]) / 2 - exp))
    print("full", round(df, 2), "silences", [(round(a, 2), round(b, 2)) for a, b in sil], "exp", round(exp, 2), "cut", cut)
    fr_raw, bk_raw = R / "front_raw.wav", R / "back_raw.wav"
    run(["ffmpeg", "-y", "-i", str(full), "-af", f"atrim=0:{cut[0] + 0.03:.3f},{TRIM},areverse,{TRIM},areverse", "-ar", "44100", "-ac", "1", str(fr_raw)])
    run(["ffmpeg", "-y", "-i", str(full), "-af", f"atrim={cut[1] - 0.03:.3f},{TRIM},areverse,{TRIM},areverse,{MID}", "-ar", "44100", "-ac", "1", str(bk_raw)])
    cb = sum(MP.nchar(s) for s in back)
    d_b = dur_of(bk_raw)
    tempo = round(MP.CPS / (cb / d_b), 4)
    out = {"tts_text": text, "voice": VOICE, "tts_tempo": TTS_TEMPO, "full_sec": round(df, 3), "cut": cut,
           "back_raw_cps": round(cb / d_b, 2), "front_raw_cps": round(nf / dur_of(fr_raw), 2), "atempo": tempo}
    # 앞 한마디는 원속도가 이미 빠르다(9.4자/초) — 줄별로 8.8자/초에 맞춘다(B15·B17: 일괄 atempo 금지, ±10% 안)
    t_front = round(MP.CPS / (nf / dur_of(fr_raw)), 4)
    out["atempo_front"] = t_front
    for raw, name, t in ((fr_raw, "front_tts.wav", t_front), (bk_raw, "back_narr.wav", tempo)):
        run(["ffmpeg", "-y", "-i", str(raw), "-af", f"atempo={t}", "-ar", "44100", "-ac", "1", str(R / name)])
        out[name] = round(dur_of(R / name), 3)
    out["front_cps"] = round(nf / out["front_tts.wav"], 2)
    out["back_cps"] = round(cb / out["back_narr.wav"], 2)
    (R / "tts.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


VOICED = 10.43        # 이븐쇼핑 47편 말소리 구간 속도(프리셋 chars_per_s_voiced)
PAUSE = {".": 0.26, ",": 0.22}   # B18 쉼 0.22~0.30


def fix_lines():
    """뒤 나레를 줄(문장)별로 가른다 → 줄 말속도 고르게(±10% 안, B15·B17) + 쉼 길이 맞춤(B18). TTS 재호출 없음.
    줄 경계 = −32dB 0.05초 쉼 중 글자 비례 예상 위치에 가장 가까운 것(쉼마다 한 번)."""
    src = R / "back_narr.wav"
    lines = [s for _, s in MP.LINES]
    d = dur_of(src)
    sil = [(a, b) for a, b in silences(src, -32, 0.05) if a > 0.05 and b < d - 0.02]
    n = [MP.nchar(l) for l in lines]
    exp = [d * sum(n[:k + 1]) / sum(n) for k in range(len(lines) - 1)]
    used, bounds = set(), []
    for e in exp:
        j = min((j for j in range(len(sil)) if j not in used and (not bounds or sil[j][0] > bounds[-1][0])), key=lambda j: abs((sil[j][0] + sil[j][1]) / 2 - e) - 2 * (sil[j][1] - sil[j][0]))
        used.add(j); bounds.append(sil[j])
    # 긴 쉼 사이 숨소리 조각(12.20~12.23 같은)까지 한 쉼으로 묶는다: 경계 쉼 바로 뒤 0.1초 안에 또 쉼이 있으면 그 끝까지
    merged = []
    for a, b in bounds:
        nxt = [s2 for s2 in sil if s2[0] >= b and s2[0] - b < 0.1]
        prv = [s2 for s2 in sil if s2[1] <= a and a - s2[1] < 0.1]
        merged.append((prv[-1][0] if prv else a, nxt[0][1] if nxt else b))
    spans, st = [], 0.0
    for a, b in merged:
        spans.append((st, a)); st = b
    spans.append((st, d))
    rate = [round(k / (b - a), 2) for k, (a, b) in zip(n, spans)]
    tempo = [round(min(1.1, max(0.9, VOICED / r)), 4) if abs(r / VOICED - 1) > 0.05 else 1.0 for r in rate]
    parts, labs = [], []
    for i, ((a, b), t) in enumerate(zip(spans, tempo)):
        f = f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS" + (f",atempo={t}" if t != 1.0 else "") + f"[l{i}]"
        parts.append(f); labs.append(f"[l{i}]")
        if i < len(spans) - 1:
            pz = PAUSE[lines[i].strip()[-1]]
            parts.append(f"anullsrc=r=44100:cl=mono,atrim=0:{pz}[z{i}]"); labs.append(f"[z{i}]")
    out = R / "back_narr_fix.wav"
    run(["ffmpeg", "-y", "-i", str(src), "-filter_complex", ";".join(parts) + ";" + "".join(labs) + f"concat=n={len(labs)}:v=0:a=1[o]",
         "-map", "[o]", "-ar", "44100", "-ac", "1", str(out)])
    # 새 파일의 줄 말 구간(계산) — 렌더 시각표가 쓴다
    new, t = [], 0.0
    for i, ((a, b), tt) in enumerate(zip(spans, tempo)):
        L = (b - a) / tt
        new.append([round(t, 3), round(t + L, 3)]); t += L
        if i < len(spans) - 1:
            t += PAUSE[lines[i].strip()[-1]]
    nd = dur_of(out)
    rate2 = [round(k / (b - a), 2) for k, (a, b) in zip(n, new)]
    J = json.loads((R / "tts.json").read_text(encoding="utf-8"))
    J["fix"] = {"bounds_before": merged, "spans_before": spans, "rate_before": rate, "tempo": tempo, "spans": new, "rate_after": rate2,
                "dur": round(nd, 3), "cps_total": round(sum(n) / nd, 2)}
    (R / "tts.json").write_text(json.dumps(J, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(J["fix"], ensure_ascii=False))


# ── 2판(관제 097, 10-17): 줄 갈아 끼우기 — 바뀐 줄만 새로 받고 나머지는 1판 back_narr_fix.wav 의 줄 구간을 그대로 쓴다 ──
OLD_LINES = ["한고은이 저렇게까지 말하길래 반신반의하고 직접 사 봤는데,", "이건 바로 물 빠지는 채반 보관통.",
             "근데 진짜 충격적인 포인트는, 씻은 채소를 그냥 넣었는데 물이 바닥으로 쫙 빠진다는 거.", "그래서 잎이 하나도 안 무르고 멀쩡함.",
             "심지어 일주일 지나도 아삭해서 채소를 처음으로 안 버림.", "이거 진짜 미쳤음.", "버리는 채소값이면 이미 본전이라,",
             "이거 본 사람들은 어디서 사냐고 댓글로 줄줄이 묻는 중."]


def patch2():
    """MP.LINES 를 차례로: 1판에 같은 글이 있으면 그 줄 구간(1판 fix.spans)을, 없으면 필재 1회 합성(줄 하나) → 앞뒤 무음 정리 → 다른 줄 말속도에 맞춘다.
    쉼 = PAUSE(쉼표 0.22·마침표 0.26). 결과 back_narr_fix.wav·tts.json fix 를 새 줄 기준으로 다시 쓴다(1판 파일은 _v1 로 남김)."""
    src1 = R / "back_narr_fix_v1.wav"
    if not src1.exists():
        import shutil
        shutil.copyfile(R / "back_narr_fix.wav", src1)
        shutil.copyfile(R / "tts.json", R / "tts_v1.json")
    J1 = json.loads((R / "tts_v1.json").read_text(encoding="utf-8"))
    sp1 = J1["fix"]["spans"]
    lines = [s for _, s in MP.LINES]
    old_rate = [MP.nchar(OLD_LINES[k]) / (b - a) for k, (a, b) in enumerate(sp1)]
    target = sorted(old_rate)[len(old_rate) // 2]
    parts, labs, new, t, calls = [], [], [], 0.0, []
    ins = ["-i", str(src1)]
    for i, line in enumerate(lines):
        if line in OLD_LINES:
            a, b = sp1[OLD_LINES.index(line)]
            parts.append(f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS[l{i}]")
            L = b - a
        else:
            raw = R / f"line2_{i}.mp3"
            if not raw.exists():
                from shopping_shorts.channelkit import providers
                providers.typecast_synth(VOICE, tempo=TTS_TEMPO)(line, str(raw))
                calls.append(line)
            tr = R / f"line2_{i}_trim.wav"
            run(["ffmpeg", "-y", "-i", str(raw), "-af", f"{TRIM},areverse,{TRIM},areverse,{MID}", "-ar", "44100", "-ac", "1", str(tr)])
            d0 = dur_of(tr)
            tempo = round(min(1.1, max(0.9, target / (MP.nchar(line) / d0))), 4)   # 다른 줄 말속도(1판 중앙)에 맞춤, ±10% 안(B17)
            ins += ["-i", str(tr)]
            k = len(ins) // 2 - 1
            parts.append(f"[{k}:a]aresample=44100,aformat=channel_layouts=mono,atempo={tempo}[l{i}]")
            L = d0 / tempo
            calls.append({"line": line, "raw_s": round(d0, 3), "atempo": tempo})
        labs.append(f"[l{i}]")
        new.append([round(t, 3), round(t + L, 3)]); t += L
        if i < len(lines) - 1:
            pz = PAUSE[line.strip()[-1]]
            parts.append(f"anullsrc=r=44100:cl=mono,atrim=0:{pz}[z{i}]"); labs.append(f"[z{i}]"); t += pz
    out = R / "back_narr_fix.wav"
    run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(parts) + ";" + "".join(labs) + f"concat=n={len(labs)}:v=0:a=1[o]",
         "-map", "[o]", "-ar", "44100", "-ac", "1", str(out)])
    J = dict(J1)
    J["fix"] = {"v2_from": "1판 줄 구간 + 바뀐 줄 새 합성(patch2)", "spans": new, "dur": round(dur_of(out), 3),
                "rate_after": [round(MP.nchar(l) / (b - a), 2) for l, (a, b) in zip(lines, new)], "target_rate": round(target, 2), "new_lines": calls}
    (R / "tts.json").write_text(json.dumps(J, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(J["fix"], ensure_ascii=False))


if __name__ == "__main__":
    if "--patch2" in sys.argv:
        patch2()
    elif "--fix" in sys.argv:
        fix_lines()
    else:
        main()
