# 롱폼 재현일치도 자(관제 337 모둠경제 · 계획서 C:\숏템_칼카피\modum\_계획서_모둠경제.md §2-1).
# 측정 주인 = measure() 하나 — 벤치 편과 우리 완성본을 **같은 함수**로 잰다. 비교 주인 = tools/calcopy/engine/match_core.match.
# 디코드 한 번(ffmpeg filter_complex split): ① scene>0.3 컷(축소본) ② 2fps 480x270 회색 파이프(정지·자막) ③ ebur128(소리) — Jev q2a F1 0.79.
# 사용:
#   python -X utf8 steps/bench_read.py measure <mp4> [--info x.info.json] [--vtt x.ko.vtt] [--screen x_screen.json] [--timeline timeline.json] --out m.json
#   python -X utf8 steps/bench_read.py match --bench a.json b.json ... --ours o.json --out 재현일치도.md
from __future__ import annotations

import argparse, json, os, re, statistics, subprocess, sys, tempfile, time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import match_core  # noqa: E402

SCENE_T = 0.3          # kal_analyze.SCENE_T 와 같은 문턱 — 롱폼에선 참고값(cut.scene_n)만. 디졸브를 못 본다(아래 CUT_TH 주석)
# 컷 주인 = _cuts(): 1초 간격(표본 CUT_LAG 개) 위쪽 8x8 블록평균 차이의 국소 최대 ≥ CUT_TH, CUT_MERGE_S 안은 하나.
# 근거(Jev q2a_컷자c 통과 — 뿌리 0.91·근본해결 0.72·한줄기 0.91·두더지 0.13): 모둠경제 전환은 대부분 디졸브라 scene>0.3 이 손 표시 14 중 2만 잡음.
# 손 표시 3구간(q2dWQkJHEd8 30~78·96~144초 + 보류 시험 VvO39Cb58Hc 300~348초) 20 중 19 재현·후보 19 중 19 정밀. 인포그래픽 요소 하나 뜸 = 차이 11~34(걸러짐), 화면 바뀜 = 44~119.
CUT_LAG = 2
CUT_TH = 40.0
CUT_MERGE_S = 1.5
MERGE_S = 0.2          # 0.2초 안 컷은 하나(kal_analyze.scene_cuts merge_s 와 같다)
SCENE_W, SCENE_H = 480, 270     # scene 검출 축소 크기(속도) — 색은 그대로 둔다
PW, PH = 480, 270      # 표본 파이프 크기(회색)
SAMPLE_FPS = 2
TOP_FRAC = 0.78        # 정지 판정은 화면 위 78%만 — 아래 자막 띠는 문장마다 바뀌어 정지 그림을 움직임으로 잡는다(Jev q2a 뿌리 0.75)
STILL_TH = 1.0         # 위쪽 60x... 블록평균 프레임 차이(0~255) 90번째 백분위가 이 아래면 정지 컷
CAP_BAND = (0.78, 0.94, 0.12, 0.88)   # 자막 띠(세로 시작·끝, 가로 시작·끝 비율) — 모둠경제 벤치 자막 y≈860~940/1080
CAP_INK_TH = 0.012     # 띠 안 '밝은(>200) 화소 옆 2px 이 어두운(<110)' 경계 비율이 이 위면 자막 있음
CAP_RATE_TH = 0.3      # 표본 프레임의 이만큼 이상에 자막이 있으면 caption=있음
MISSING = "미측정"

# (key, kind, tol, core, why) — 계획서 §2-1 합격선(후보, 실측 뒤 조정). kind 뜻 = match_core.judge_cell
LONG_RULES = [
    ("len.duration", "rel", 15, True, "길이 ±15% 또는 벤치 min~max"),
    ("chapter.n", "db", 1, True, "챕터 수 ±1개(info.json chapters / 우리 timeline 챕터)"),
    ("chapter.sec", "rel", 20, True, "챕터 중앙 길이 ±20%"),
    ("hook.sec", "rel", 30, True, "훅 끝(과거 장면 복귀 첫 단어 자막 시각, 판독 json — hook_of) ±30%. 벤치 31~50초 leave-one-out 4/4(Jev q2a_훅c 통과)"),
    ("chapter.first", "rel", 20, False, "첫 챕터 경계까지 초 — 참고(올린 사람의 챕터 나누기: 30·38·196·334초 두 갈래)"),
    ("shot_mix", "pctp", 10, True, "샷 종류 비율 종류마다 ±10%p(화면 판독 screen.json)"),
    ("cut.median", "rel_slow", 30, True, "컷 중앙(_cuts 같은 함수 — 디졸브 포함) +30%/−15%"),
    ("still.rate", "pctp", 10, True, "정지 컷 시간 비율 ±10%p(자막 띠 뺀 위쪽 프레임 차이)"),
    ("cut.p90", "rel", 30, False, "컷 길이 90번째 백분위 — 참고(긴 컷 꼬리)"),
    ("caption", "eq", 0, True, "자막 유무 같음(하단 띠 글자 잉크)"),
    ("caption.rate", "pctp", 10, False, "자막 있는 표본 비율 — 참고"),
    ("speech.cps", "rel", 10, True, "나레 글자/초(공백 제외 ÷ 말한 초) ±10%"),
    ("mix.lufs", "db", 1, False, "통합 LUFS 벤치와 비교 — 참고(사장님 통일 목표 −14±1 은 따로 본다, 계획서 §9 #9)"),
]


def _ffprobe(mp4: str) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", mp4],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("ffprobe 실패: " + r.stderr[-300:])
    d = json.loads(r.stdout)
    return {"duration": float(d["format"]["duration"]), "audio": any(s.get("codec_type") == "audio" for s in d.get("streams", []))}


def _decode(mp4: str, has_audio: bool):
    """(프로그램) 디코드 한 번 → (컷 시각, 표본 프레임 회색 배열 [n,PH,PW], LUFS)."""
    fc = (f"[0:v]scale={SCENE_W}:{SCENE_H},split[sa][sb];[sa]select='eq(n,0)+gt(scene,{SCENE_T})',showinfo[o1];"
          f"[sb]fps={SAMPLE_FPS},format=gray[o2]")
    args = ["ffmpeg", "-hide_banner", "-nostats", "-i", mp4, "-filter_complex", fc + (";[0:a]ebur128[o3]" if has_audio else ""),
            "-map", "[o1]", "-f", "null", "-", "-map", "[o2]", "-f", "rawvideo", "pipe:1"]
    if has_audio:
        args += ["-map", "[o3]", "-f", "null", "-"]
    # scene 갈래 크기를 표본 크기와 같게 둬서 split 한 번으로 끝낸다(SCENE_W==PW)
    assert (SCENE_W, SCENE_H) == (PW, PH)
    with tempfile.TemporaryFile() as errf:
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=errf)
        fs = PW * PH
        frames = []
        while True:
            b = p.stdout.read(fs)
            if not b or len(b) < fs:
                break
            frames.append(np.frombuffer(b, np.uint8).reshape(PH, PW))
        p.wait()
        errf.seek(0)
        err = errf.read().decode("utf-8", "replace")
    if p.returncode != 0:
        raise RuntimeError("ffmpeg 측정 실패: " + err[-400:])
    ts = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", err)]
    cuts = []
    for t in ts:
        if t <= 0.05 or (cuts and t - cuts[-1] < MERGE_S):
            continue
        cuts.append(round(t, 3))
    lufs = None
    m = re.findall(r"Integrated loudness:\s*\n\s*I:\s*(-?[0-9.]+) LUFS", err)
    if m:
        lufs = float(m[-1])
    return cuts, (np.stack(frames) if frames else np.zeros((0, PH, PW), np.uint8)), lufs


def _top_diffs(fr: np.ndarray) -> np.ndarray:
    """표본 사이 위쪽 블록평균(8x8) 차이 — diffs[i] = 표본 i 와 i+1 사이."""
    if len(fr) < 2:
        return np.zeros(0)
    return np.abs(np.diff(_blocks(fr), axis=0)).mean(axis=(1, 2))


def _caption_ink(fr: np.ndarray) -> np.ndarray:
    y0, y1, x0, x1 = (int(CAP_BAND[0] * PH), int(CAP_BAND[1] * PH), int(CAP_BAND[2] * PW), int(CAP_BAND[3] * PW))
    b = fr[:, y0:y1, x0:x1].astype(np.int16)
    bright, dark = b > 200, b < 110
    edge = (bright[:, :, :-2] & dark[:, :, 2:]) | (dark[:, :, :-2] & bright[:, :, 2:])
    return edge.mean(axis=(1, 2)) if len(fr) else np.zeros(0)


def _blocks(fr: np.ndarray) -> np.ndarray:
    top = fr[:, : int(PH * TOP_FRAC)].astype(np.float32)
    h, w = top.shape[1] // 8 * 8, top.shape[2] // 8 * 8
    return top[:, :h, :w].reshape(len(fr), h // 8, 8, w // 8, 8).mean(axis=(2, 4))


def _cuts(fr: np.ndarray, scene_at: list[float] | None = None) -> list[float]:
    """(판단 주인) 컷 시각 — 벤치·우리 같은 함수. 디졸브·밀어내기도 1초 간격 차이로 잡는다(표본 2fps 라 시각은 ±0.5초).
    같은 자리(±1초)에 scene>0.3 컷이 있으면 그 시각으로 맞춘다(딱 끊는 컷은 프레임 단위로 정확하게)."""
    if len(fr) <= CUT_LAG:
        return []
    bl = _blocks(fr)
    d = np.abs(bl[CUT_LAG:] - bl[:-CUT_LAG]).mean(axis=(1, 2))
    w = int(CUT_MERGE_S * SAMPLE_FPS)
    out = []
    for i in range(len(d)):
        if d[i] >= CUT_TH and d[i] == d[max(0, i - w):i + w + 1].max():
            t = round((i + CUT_LAG / 2) / SAMPLE_FPS, 2)
            near = [c for c in (scene_at or []) if abs(c - t) <= 1.0]
            if near:
                t = min(near, key=lambda c: abs(c - t))
            if t > 0.05 and (not out or t - out[-1] > CUT_MERGE_S):
                out.append(t)
    return out


def _still(cuts: list[float], dur: float, diffs: np.ndarray) -> tuple:
    """컷 안 위쪽 프레임 차이 90번째 백분위 < STILL_TH 인 컷 = 정지(1초보다 짧아 표본이 없는 컷은 분모에서 뺀다). → (정지 시간 비율, 정지 컷 수 비율, 잰 컷 수)."""
    bounds = [0.0] + cuts + [dur]
    st_t = tot_t = 0.0
    st_n = tot_n = 0
    for a, b in zip(bounds, bounds[1:]):
        # 컷 경계 표본(경계 ±1초 — 디졸브 몫)을 빼고 컷 안 차이만
        i0, i1 = int(np.ceil((a + 1.0) * SAMPLE_FPS)), int(np.floor((b - 1.0) * SAMPLE_FPS))
        seg = diffs[i0:i1] if i1 > i0 else diffs[0:0]
        if len(seg) == 0:
            continue                 # 1초보다 짧은 컷은 정지를 판정할 표본이 없다 — 분모에서 뺀다
        still = float(np.percentile(seg, 90)) < STILL_TH
        tot_t += b - a; tot_n += 1
        if still:
            st_t += b - a; st_n += 1
    if not tot_n:
        return MISSING, MISSING, 0
    return round(st_t / tot_t, 4), round(st_n / tot_n, 4), tot_n


def _chapters_from(info_json, timeline, chapters):
    if chapters is not None:
        return [float(x) for x in chapters], "인자 chapters"
    if info_json and os.path.exists(info_json):
        ch = json.load(open(info_json, encoding="utf-8")).get("chapters") or []
        if ch:
            return [float(c["start_time"]) for c in ch], "info.json chapters"
    if timeline and os.path.exists(timeline):
        L = json.load(open(timeline, encoding="utf-8")).get("lines") or []
        out, prev = [], object()
        for l in L:
            if l.get("chapter") != prev:
                out.append(float(l["t0"])); prev = l.get("chapter")
        if out:
            out[0] = 0.0
            return out, "timeline.json lines.chapter"
    return None, MISSING


def _ts(s: str) -> float:
    h, m, r = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(r)


PAUSE_S = 1.0          # 낱말 시각 사이가 이보다 길면 쉼 — 말한 초에서 뺀다(우리 timeline 은 줄 녹음 길이라 줄 사이 쉼이 빠진 값과 맞춘다)


def speech_from_vtt(vtt: str) -> tuple:
    """(글자 수 공백 제외, 말한 초). 유튜브 자동자막(굴러가는 꼴)은 <c> 낱말 시각이 붙은 줄(새 말)만 세고,
    말한 초 = 큐 시작·낱말 시각·큐 끝 사이 간격 합(간격 > PAUSE_S 는 쉼으로 뺌). 일반 자막(낱말 시각 없음)은 큐 길이 합."""
    txt = open(vtt, encoding="utf-8").read()
    cues = re.findall(r"(\d+:\d\d:\d\d\.\d+) --> (\d+:\d\d:\d\d\.\d+)[^\n]*\n(.*?)(?:\n\n|\Z)", txt, re.S)
    rolling = "<c>" in txt
    chars, talk = 0, 0.0
    for a, b, body in cues:
        lines = [l for l in body.split("\n") if l.strip()]
        if rolling:
            lines = [l for l in lines if "<c>" in l or re.search(r"<\d\d:", l)]
        if not lines:
            continue
        t = re.sub(r"<[^>]+>", "", " ".join(lines))
        chars += len(re.sub(r"\s", "", t))
        pts = [_ts(a)] + [_ts(x) for x in re.findall(r"<(\d+:\d\d:\d\d\.\d+)>", " ".join(lines))] + [_ts(b)]
        talk += sum(d for d in (q - p for p, q in zip(pts, pts[1:])) if 0 < d <= PAUSE_S) if rolling else max(0.0, _ts(b) - _ts(a))
    return chars, round(talk, 3)


def speech_from_timeline(timeline: str) -> tuple:
    L = json.load(open(timeline, encoding="utf-8")).get("lines") or []
    return sum(len(re.sub(r"\s", "", l.get("text", ""))) for l in L), round(sum(float(l["t1"]) - float(l["t0"]) for l in L), 3)


def shot_mix_from(screen_json: str) -> tuple:
    """화면 판독 screen.json → (종류별 시간 비율, 샷 수, 판독 컷 시각). 샷 칸 이름은 t0/t1/kind(또는 start/end/type)."""
    d = json.load(open(screen_json, encoding="utf-8"))
    shots = d.get("shots") if isinstance(d, dict) else d
    acc, n, cuts = {}, 0, []
    for s in shots or []:
        t0 = float(s.get("t0", s.get("start", 0))); t1 = float(s.get("t1", s.get("end", t0)))
        k = str(s.get("kind") or s.get("type") or "?")
        if t1 <= t0:
            continue
        acc[k] = acc.get(k, 0.0) + (t1 - t0); n += 1
        cuts.append(t0)
    tot = sum(acc.values())
    return ({k: round(v / tot, 4) for k, v in sorted(acc.items())} if tot else MISSING), n, sorted(cuts)[1:]


def hook_of(read_json) -> tuple:
    """(판단 주인) 훅 끝 초 — 벤치·우리 같은 꼴 판독 json {'hook': {'sec': ..}} 에서만 읽는다(정의 = 과거 장면으로 되돌아가는 첫 단어의 자막 시작 시각).
    우리 완성본도 같은 대본 판독 절차를 우리 자막에 돌려 같은 꼴 파일을 만든다 — timeline 에서 따로 계산하지 않는다(판단 두 벌 금지). 없으면 미측정."""
    if not (read_json and os.path.exists(read_json)):
        return MISSING, MISSING
    h = (json.load(open(read_json, encoding="utf-8")).get("hook") or {})
    v = h.get("sec")
    return (round(float(v), 2), f"판독 {os.path.basename(read_json)} hook.sec") if isinstance(v, (int, float)) else (MISSING, MISSING)


def measure(mp4: str, info_json=None, vtt=None, screen_json=None, timeline=None, chapters=None, read_json=None) -> dict:
    """(측정 주인) 롱폼 한 편 → LONG_RULES 칸 값. 못 잰 칸은 '미측정'(통과 아님 — match_core 가 failed 로 판정)."""
    t_start = time.time()
    pr = _ffprobe(mp4)
    dur = pr["duration"]
    scene_cuts, fr, lufs = _decode(mp4, pr["audio"])
    cuts = _cuts(fr, scene_cuts)
    bounds = [0.0] + cuts + [dur]
    lens = [b - a for a, b in zip(bounds, bounds[1:]) if b - a > 0.05]
    diffs = _top_diffs(fr)
    still_t, still_n, still_den = _still(cuts, dur, diffs)
    ink = _caption_ink(fr)
    cap_rate = round(float((ink > CAP_INK_TH).mean()), 4) if len(ink) else MISSING
    out = {"src": os.path.abspath(mp4), "len.duration": round(dur, 2),
           "cut.n": len(cuts), "cut.at": cuts, "cut.scene_n": len(scene_cuts), "cut.scene_at": scene_cuts,
           "cut.median": round(statistics.median(lens), 3) if lens else MISSING,
           "cut.p90": round(float(np.percentile(lens, 90)), 3) if lens else MISSING,
           "still.rate": still_t, "still.rate_by_count": still_n, "still.n_shots_judged": still_den,
           "caption.rate": cap_rate,
           "caption": MISSING if cap_rate == MISSING else ("있음" if cap_rate >= CAP_RATE_TH else "없음"),
           "caption.ink_median": round(float(np.median(ink)), 4) if len(ink) else MISSING,
           "mix.lufs": lufs if lufs is not None else MISSING}
    ch, ch_from = _chapters_from(info_json, timeline, chapters)
    if ch:
        ch = sorted(set(ch))
        cl = [b - a for a, b in zip(ch, ch[1:] + [dur])]
        out.update({"chapter.n": len(ch), "chapter.sec": round(statistics.median(cl), 2),
                    "chapter.first": round(ch[1], 2) if len(ch) > 1 else MISSING, "chapter.at": ch})
    else:
        out.update({"chapter.n": MISSING, "chapter.sec": MISSING, "chapter.first": MISSING})
    out["hook.sec"], out["hook.from"] = hook_of(read_json)
    out["chapter.from"] = ch_from
    if vtt and os.path.exists(vtt):
        c, s = speech_from_vtt(vtt); src = "vtt"
    elif timeline and os.path.exists(timeline):
        c, s = speech_from_timeline(timeline); src = "timeline"
    else:
        c, s, src = 0, 0, None
    out["speech.cps"] = round(c / s, 3) if s else MISSING
    out["speech.chars"], out["speech.sec"], out["speech.from"] = c, s, src or MISSING
    if screen_json and os.path.exists(screen_json):
        mix, n, scuts = shot_mix_from(screen_json)
        out.update({"shot_mix": mix, "screen.n_shots": n, "screen.cut_agree": cut_agreement(cuts, scuts)})
    else:
        out["shot_mix"] = MISSING
    out["_method"] = {"cut": f"{SAMPLE_FPS}fps 위 {TOP_FRAC:.0%} 8x8 블록 {CUT_LAG / SAMPLE_FPS:g}초 간격 차이 국소최대≥{CUT_TH:g} · {CUT_MERGE_S}s 안 하나",
                      "scene(참고)": f"ffmpeg scale {SCENE_W}x{SCENE_H} select gt(scene,{SCENE_T}) merge {MERGE_S}s",
                      "still": f"{SAMPLE_FPS}fps 회색 위 {TOP_FRAC:.0%} 8x8 블록 차이 p90<{STILL_TH}(컷 경계 ±0.5초 제외, 시간 비율)",
                      "caption": f"띠 {CAP_BAND} 밝음>200·어둠<110 경계 비율>{CAP_INK_TH} 표본 ≥{CAP_RATE_TH}",
                      "lufs": "ffmpeg ebur128 Integrated", "sec": round(time.time() - t_start, 1)}
    return out


def cut_agreement(auto: list[float], hand: list[float], tol: float = 0.5) -> dict:
    """자동 컷 ↔ 판독 컷 짝짓기(±tol 초). 일치율 = 짝 / 판독 컷 수(재현율) · 짝 / 자동 컷 수(정밀도)."""
    used, hit = set(), 0
    for h in hand:
        j = min((i for i in range(len(auto)) if i not in used and abs(auto[i] - h) <= tol), key=lambda i: abs(auto[i] - h), default=None)
        if j is not None:
            used.add(j); hit += 1
    return {"auto": len(auto), "hand": len(hand), "matched": hit,
            "recall": round(hit / len(hand), 4) if hand else MISSING, "precision": round(hit / len(auto), 4) if auto else MISSING, "tol_s": tol}


def loo(stats: list[dict], names: list[str]) -> dict:
    """(검사 도구) leave-one-out — 편마다 나머지 편을 벤치로 match. 기준 칸이 벤치 자신도 못 넘으면 합격선이 너무 좁다는 뜻."""
    res = {}
    for i, n in enumerate(names):
        res[n] = match_core.match(LONG_RULES, stats[:i] + stats[i + 1:], stats[i])
    return res


def loo_md(T: dict) -> str:
    names = list(T)
    mark = {"in": "✓", "out": "✗", "failed": "미측정"}
    L = ["| 칸 | 기준 | " + " | ".join(names) + " |", "|---|---|" + "---|" * len(names)]
    for k, r0 in enumerate(T[names[0]]["rows"]):
        cells = []
        for n in names:
            r = T[n]["rows"][k]
            cells.append(f"{mark[r['judge']]} {r['ours'] if not isinstance(r['ours'], dict) else '분포'} (차 {r['diff']})")
        L.append(f"| {r0['key']} | {'기준' if r0['core'] else '참고'} | " + " | ".join(cells) + " |")
    L.append("| **판정** | | " + " | ".join(("통과" if T[n]["pass"] else "미달: " + ", ".join(T[n]["core_fail"])) for n in names) + " |")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("measure")
    m.add_argument("mp4"); m.add_argument("--info"); m.add_argument("--vtt"); m.add_argument("--screen"); m.add_argument("--timeline")
    m.add_argument("--read", help="대본 판독 json(hook.sec) — 벤치·우리 같은 꼴")
    m.add_argument("--out", required=True)
    c = sub.add_parser("match")
    c.add_argument("--bench", nargs="+", required=True); c.add_argument("--ours", required=True); c.add_argument("--out", required=True)
    c.add_argument("--title", default="")
    lo = sub.add_parser("loo", help="벤치 자기시험: 한 편씩 '우리'로 놓고 나머지와 같은 자로 — 벤치가 못 넘는 합격선을 찾는다")
    lo.add_argument("--bench", nargs="+", required=True); lo.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "measure":
        r = measure(a.mp4, a.info, a.vtt, a.screen, a.timeline, read_json=a.read)
        Path(a.out).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps({k: v for k, v in r.items() if k not in ("cut.at", "chapter.at")}, ensure_ascii=False))
    elif a.cmd == "loo":
        T = loo([json.load(open(p, encoding="utf-8")) for p in a.bench], [Path(p).stem.replace("measure_", "") for p in a.bench])
        Path(a.out).write_text(loo_md(T), encoding="utf-8")
        print(loo_md(T))
    else:
        B = [json.load(open(p, encoding="utf-8")) for p in a.bench]
        T = match_core.match(LONG_RULES, B, json.load(open(a.ours, encoding="utf-8")))
        Path(a.out).write_text(match_core.match_md(T, a.title), encoding="utf-8")
        print(("통과" if T["pass"] else "미달"), "· 미달 기준 칸:", T["core_fail"])


if __name__ == "__main__":
    main()
