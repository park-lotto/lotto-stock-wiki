# -*- coding: utf-8 -*-
"""얜샷템 박세리 면세점 스킨 — 렌더 감싸기(엔진 코드는 안 고친다, 관제 097, 2026-10-17).
    PYTHONUTF8=1 py channel/yanshottem/박세리_면세점/make_render.py [--dry] [--mix-only] [--gain 15,15]

정본 = channel/annapick/1편_한고은채소통/make_render.py 와 같은 길(같은 장르 직전 통과작):
  미나 1회 narr_mina.mp3(1.0 원음) → 줄마다 atempo(TEMPO) 로 잘라 대본 시각표(원음 2구간 사이)에 끼운 narr_gapped.wav
  (처음 4.93초 = 원음 훅 자리 무음 — gap_tts 는 맨 앞 무음을 못 넣는다)
  → 재료.json 8컷(시각은 여기 PLAN 한 곳) → 렌더용 대본 = 나레 한 문장(narr_video 줄 시작 찾기 우회) + 자막 전부 caption_events emph
  → narr_video.build(BGM 없음, line_asr=False) → hottem_audio.add_source_bed(컷 단위 소리, 원음 = 박세리 말만)
  → BGM 원음 창 덕킹 섞기·LUFS → render/final.mp4
시각의 주인 = 이 파일 PLAN·TEMPO·GAPS(대본.json·재료.json 의 t_final 은 여기서 써 넣는 사본).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.calcopy import narr_video as nv, hottem_audio as ha  # noqa: E402
from shopping_shorts import bgm_lib  # noqa: E402

D = Path(__file__).resolve().parent
W = Path("C:/숏템_칼카피/yanshottem/박세리_면세점")
SRC = W / "src"
R = W / "render"
MINA = R / "narr_mina.mp3"            # 일레븐랩스 미나 expressive 1회(14.16초) — 다시 부르지 않는다
WAV = R / "narr_gapped.wav"
SRCV = "seri_WHzwVWvEvQ8.mp4"
VOICE = "seri_voice.wav"
VOICE_AF = "highpass=f=90,acompressor=threshold=0.03:ratio=2:attack=10:release=150:makeup=1"   # 한고은 편과 같은 약한 처리
TITLE = "박세리가 해외 갈 때마다\n6개씩 사 오는 스킨"
LABEL = "출처 : 박세리의 속사정"
FRAME = ROOT / "channel/mantem/frame_얜샷템.json"
TTEUTGI = D / "뜯기/뜯기.json"
GAINS = [12.5, 11.5, 14.5]    # 원음 창 올림(dB): O1 · O3 앞('솔직히 쟁여 놓고 쓰거든') · O3 뒤('여기 또 엑스트라 하나 있잖아' — 원본 −25~−30dB 로 작아 단독 받아쓰기가 '요것도 엑스라지'로 흔들려 +3dB)
O3_SPLIT = 1.35              # O3 앞뒤 가르는 쉼(144.80~145.0)
LUFS_NARR = -15.0
LUFS_FINAL = -16.0            # 벤치 BzEO7 −15.9 ±1.5 · 만템 8편 −15.0(−16.9~−12.5)
BGM, BGM_DB, DUCK_DB = "sweets", -27.0, -10.0   # 만템 8/8 배경음악 있음(밝은·경쾌) — 한고은 편과 같은 곡·크기

# 나레 원음(1.0) 안 줄 구간 [a,b] — silencedetect −30dB/0.08 실측(1.09·3.63·3.91·4.87~5.66·7.66·7.96·8.80·10.51·10.92~11.89·12.71·13.66)
SLICES = [(0.00, 4.88), (5.64, 10.93), (11.87, 14.16)]
TEMPO = [1.60, 1.66, 1.62]    # 줄마다 8.5자/초(만템 8.4 +1%) — 1판 1.70/1.70/1.84 는 공백 뺀 글자 26·27·12 로 다시 세니 9.06/8.68/9.64(+8~15%)라 내림. 셋 차 ≤4%(B17 ±10% 안)
# 조각 경계(원음 1.0 초) — 20ms 에너지 음절 봉우리 세기 실측: 0~1.09 7음절(박세리가 출국길)·쉼 1.09~1.24 / 1.2~3.63 '면세점에서 쟁여 온다는'·쉼 3.63~3.72
#   (0~3.80 받아쓰기 '…온다는 분홍이') / 5.6~7.96 12음절(제작진이 한 번만 발라 보자니까, '만' 7.06·'발' 7.18)·쉼 7.96~8.23 /
#   9.05~ '제일 안쪽에' 5음절(9.08~9.96)·'넣' 10.10 / '여분까지' 11.95~12.57·쉼 12.71~12.79·'따로' 12.86·13.02·'챙' 13.18
RAW_BREAKS = [[1.16, 3.676], [7.12, 8.10, 10.03], [13.10]]
# 줄 자막 조각(≤13자) — 원문 줄 text 와 같은 낱말
NCHUNK = [["박세리가 출국길", "면세점에서 쟁여 온다는", "분홍빛 스킨이라는데"],
          ["제작진이 한 번만", "발라 보자니까", "웃으며 제일 안쪽에", "넣어 버렸대요"],
          ["여분까지 따로", "챙겨 뒀다네요"]]
O1 = (0.0, 4.93)              # 원음 1 = 130.86~134.51 + 134.82~136.10 (쉼 0.31초 잘라 냄)
N1_T0 = 4.98
GAP_12 = 0.10                 # N1 끝 → N2
GAP_2O = 0.10                 # N2 끝 → O3 화면(143.51 원본 컷)
O3_LEAD = 0.04                # 화면 컷 143.51 → 말 143.55
O3_DUR = 2.40                 # 143.55~145.95 '솔직히 쟁여 놓고 쓰거든 / 여기 또 엑스트라 하나 있잖아'(1판 1.25초 단독 받아쓰기 '솔직히 챙겨'만 — 원본도 단독이면 같음, 2.55초로 늘리면 2.5-flash·pro 다 '…쓰거든. 여기 또 엑스트라…')
O3_B = 1.45                   # 145.0 '여기 또 엑스트라 하나 있잖아' 시작(원본 흰 편집 자막 144.75~146.0)
S6_MAX = 146.21               # 원본 컷 146.246 앞
GAP_O3 = 0.06
TAIL_MIN = 0.15
END_CUT = 1.64                # 끝 컷 146.28~147.92(원본 컷 148.715 앞)
STASH = (123.98, 125.618)     # 보물창고 = 원음 '솔직히 쟁여 놓고 쓰거든' 화면
# (2판 끝 컷 = 보물창고 123.98~125.62(원본 컷 125.659 앞 — 2판에서 2.1초로 넘겨 다음 샷 '팔 뻗기'가 섞였음) — 3판에서 O3 화면으로 옮김)
S6_V = 4.93 + (140.03 - 136.10) + (143.505 - 141.203)   # (S5B 는 143.47 에서 끝 — s5a 가 0.035초 앞에서 시작)   # 11.162 — 뒷머리 컷(143.51)이 가장 늦게 시작할 수 있는 시각
PUNCH = [620, 60, 720, 720]   # 원음 뒤쪽 확대(얼굴+병, 아래 편집 자막 y≥900 밖)


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def lufs(p):
    e = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(p), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace").stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1])


def plan():
    """(판단 주인) 모든 시각 — 나레 줄 시작·원음 창·컷·자막."""
    L = [(b - a) / k for (a, b), k in zip(SLICES, TEMPO)]
    n1 = (N1_T0, N1_T0 + L[0])
    n2 = (n1[1] + GAP_12, n1[1] + GAP_12 + L[1])
    # 화면은 원본 분량이 정한다(136.10~140.03 + 141.203~143.505) — 나레가 길어 모자란 만큼은 뒷머리 컷(입 안 보임)을 먼저 띄우고 원음은 나레 뒤에
    s6 = min(n2[1] + GAP_2O, S6_V)
    o3s = max(s6 + O3_LEAD, n2[1] + GAP_2O)
    o3 = (o3s, o3s + O3_DUR)
    n3 = (o3[1] + GAP_O3, o3[1] + GAP_O3 + L[2])
    # 3판(지휘 줄별 대조): 1·2판 원음 O3 화면 = 흐린 뒷머리 2.7초 → 말과 안 맞음. '솔직히 쟁여 놓고 쓰거든' = 보물창고 수납장(쌓아 둔 화장품),
    # '여기 또 엑스트라 하나 있잖아' = 수납장 앞 박세리(145.15~ 그 말을 하는 장면), 끝 나레 '여분까지 따로 챙겨 뒀다네요' = 같은 수납장 칸칸이 쌓인 화장품(146.28~, 원본 컷 146.246 뒤 앞으로)
    s6b = s6 + STASH[1] - STASH[0]
    t7 = s6b + (S6_MAX - 145.15)          # 수납장 앞 박세리 컷은 원본 컷 146.246 앞까지
    dur = round(t7 + END_CUT, 3)
    assert dur - n3[1] >= TAIL_MIN, (dur, n3)
    # 컷: (ss, 길이 또는 None=다음 컷까지, crop, 소리 ss 또는 None)
    c = [  # t0, ss, crop, audio_ss
        (0.0, 130.86, [560, 0, 850, 850], 130.86),
        (1.82, 132.68, PUNCH, 132.68),   # 원음 중간 확대 한 번(B4: 1판 컷 중앙 1.5 vs 벤치 1.117 +34% → 원음 3.65초 한 컷을 둘로)
        (3.65, 134.82, PUNCH, 134.82),
        (4.93, 136.10, [560, 0, 850, 850], None),
        (4.93 + (137.037 - 136.10), 137.037, [520, 0, 860, 860], None),
        (4.93 + (138.739 - 136.10), 138.739, [370, 0, 860, 860], None),
        (4.93 + (140.03 - 136.10), None, [730, 0, 580, 580], None),   # 140.03: 원본 컷 140.073 뒤 프레임(감추는 손 자막)이 2프레임 새던 것(렌더 실측 8.80·8.84초) 끊음   # ss = 끝이 142.18 에 닿게(아래) — '(급하게 감추는 손)' 위 y<580
        (None, 142.18, [560, 0, 860, 860], None),   # 142.18 원본 자막이 아래 노랑(y≥900)으로 바뀐 뒤 — 손·병 다 보이게 넓힘(x≥1725 제작진 얼굴 밖)
        (s6, STASH[0], [480, 0, 880, 880], "O3"),   # 보물창고(원본 컷 125.659 앞) — 소리는 O3 원음(아래 소리 시간표)
        (s6b, 145.15, [1040, 0, 880, 880], "O3"),     # '여기 또 엑스트라' 장면
        (t7, 146.28, [960, 0, 880, 880], None),        # 끝 컷 — 칸칸이 쌓인 화장품, 아래 노랑 편집 자막(y≈925~) 밖
    ]
    S5B = 143.47 - 142.18   # 3판: 143.505 로 끝내면 원본 컷 143.51 뒤 뒷머리 1프레임이 샘(11.16초 실측) — 뒤 컷이 이제 다른 장면
    c[7] = (s6 - S5B,) + c[7][1:]
    shots = []
    for i, (t0, ss, crop, ass) in enumerate(c):
        t1 = c[i + 1][0] if i + 1 < len(c) else dur
        if ss is None:
            ss = round(142.18 - (t1 - t0), 3)
        shots.append({"t0": round(t0, 3), "t1": round(t1, 3), "ss": ss, "crop": crop, "audio_ss": ass})
    return {"L": L, "n": [n1, n2, n3], "o1": O1, "o3": o3, "dur": dur, "shots": shots}


def chunk_times(i, t0):
    """줄 i 의 자막 조각 시각 — 원음(1.0) 안 조각 경계 RAW_BREAKS 를 atempo 로 옮김."""
    a, _ = SLICES[i]
    return [t0 + (r - a) / TEMPO[i] for r in RAW_BREAKS[i]]


def gapped(P):
    fc, lab, t = [], [], 0.0
    for i, ((a, b), (t0, _)) in enumerate(zip(SLICES, P["n"])):
        fc.append(f"anullsrc=r=48000:cl=mono,atrim=0:{t0 - t:.3f}[g{i}]"); lab.append(f"[g{i}]")
        fc.append(f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=N/SR/TB,aresample=48000,aformat=channel_layouts=mono,atempo={TEMPO[i]}[p{i}]"); lab.append(f"[p{i}]")
        t = t0 + (b - a) / TEMPO[i]
    fc.append(f"anullsrc=r=48000:cl=mono,atrim=0:{P['dur'] - t:.3f}[ge]"); lab.append("[ge]")
    fc.append("".join(lab) + f"concat=n={len(lab)}:v=0:a=1[a]")
    run(["ffmpeg", "-y", "-i", str(MINA), "-filter_complex", ";".join(fc), "-map", "[a]", "-c:a", "pcm_s16le", "-ar", "48000", str(WAV)])


def ramp(a, b, g, up=0.08, down=0.10, depth=6.0):
    st = 4
    out = [[round(a + up * i / st, 3), round(a + up * (i + 1) / st, 3), round(g - 12 * (1 - (i + 1) / st), 2)] for i in range(st)]
    out.append([round(a + up, 3), round(b - down, 3), g])
    out += [[round(b - down + down * i / st, 3), round(b - down + down * (i + 1) / st, 3), round(g - depth * (i + 1) / st, 2)] for i in range(st)]
    return out


def bgm_mix(src_mp4, out_mp4, win, dur):
    bgm = bgm_lib.path_of(BGM)
    k = 10 ** (DUCK_DB / 20)
    terms = "*".join(f"(1-{1 - k:.4f}*clip(min((t-{a - 0.15:.3f})/0.15,({b + 0.15:.3f}-t)/0.15),0,1))" for a, b in win)
    tmp = R / "work_bgm.wav"
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", bgm, "-t", f"{dur:.3f}", "-af", f"aresample=48000,aformat=channel_layouts=mono,loudnorm=I={BGM_DB}:TP=-6:LRA=11,"
         f"volume='{terms}':eval=frame,afade=t=out:st={dur - 0.6:.3f}:d=0.6", "-c:a", "pcm_s16le", str(tmp)])
    mixed = R / "work_mix.wav"
    run(["ffmpeg", "-y", "-i", str(src_mp4), "-i", str(tmp), "-filter_complex",
         "[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=mono[m];[1:a]aformat=sample_fmts=fltp:channel_layouts=mono[b];"
         "[m][b]amix=inputs=2:normalize=0:duration=first[a]", "-map", "[a]", "-c:a", "pcm_s24le", str(mixed)])
    I = lufs(mixed)
    g = round(LUFS_FINAL - I, 2)
    run(["ffmpeg", "-y", "-i", str(src_mp4), "-i", str(mixed), "-filter_complex", f"[1:a]volume={g}dB,alimiter=limit=0.89:level=false[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(out_mp4)])
    return {"bgm": BGM, "bgm_lufs": BGM_DB, "duck_db": DUCK_DB, "mix_I": I, "gain": g}


def write_docs(P, ev):
    """대본.json·재료.json 에 이 PLAN 의 시각을 써 넣는다(사본 — 주인은 plan())."""
    S = json.loads((D / "대본.json").read_text(encoding="utf-8"))
    F = S["final"]
    for i, l in enumerate(F["lines"]):
        a, b = SLICES[i]
        n = len(re.sub(r"[\s,.?!~]", "", l["tts"]))
        l.update({"slice_raw": [a, b], "atempo": TEMPO[i], "t_final": [round(P["n"][i][0], 3), round(P["n"][i][1], 3)],
                  "sec": round(P["L"][i], 3), "cps": round(n / P["L"][i], 2)})
    F["orig_audio"][0]["t_final"] = list(P["o1"])
    F["orig_audio"][1].update({"t_final": [round(P["o3"][0], 3), round(P["o3"][1], 3)], "spans": [[143.55, 143.55 + O3_DUR]], "dur": O3_DUR,
                               "said": "솔직히 쟁여 놓고 쓰거든 / 여기 또 엑스트라 하나 있잖아"})
    F["check"]["chars_no_space"] = [len(re.sub(r"[\s,.?!~]", "", l["tts"])) for l in F["lines"]]
    F["check"]["total_chars"] = sum(F["check"]["chars_no_space"])
    F["check"]["total_sec"] = P["dur"]
    F["check"]["narr_cps"] = [l["cps"] for l in F["lines"]]
    F["check"]["orig_sec"] = round((P["o1"][1] - P["o1"][0]) + (P["o3"][1] - P["o3"][0]), 2)
    S["captions_plan"] = [{"t0": e["t0"], "t1": round(e["t0"] + e["dur"], 3), "text": e["text"], "kind": e["who"]} for e in ev]
    S["notes"] = [n for n in S.get("notes", []) if not n.startswith("시각은 8.4자/초 추정")] + [
        "TTS = 일레븐랩스 미나 expressive 1회(14.16초) → 줄별 atempo 1.70/1.70/1.84 (make_render.py PLAN 이 시각의 주인)."]
    (D / "대본.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
    M = json.loads((D / "재료.json").read_text(encoding="utf-8"))
    for sh, p in zip(M["shots"], P["shots"]):
        d = round(p["t1"] - p["t0"], 3)
        sh.update({"ss": p["ss"], "dur": d, "src_span": [p["ss"], round(p["ss"] + d, 3)], "t_final": [p["t0"], p["t1"]], "src_crop": p["crop"],
                   "scale": round(1080 / p["crop"][2], 2)})
        if p["audio_ss"] is not None and p["audio_ss"] != "O3":
            sh["audio_src"], sh["audio_ss"] = VOICE, p["audio_ss"]
        if p["audio_ss"] == "O3":
            sh.pop("mute", None)
            sh["audio_src"], sh["audio_ss"] = VOICE, "O3"
            sh["audio_note"] = f"소리 = O3 원음 143.51~ 이 {round(P['o3'][0] - 0.04, 3)}초부터 두 컷(보물창고·수납장 앞)에 걸쳐 이어짐(말 143.55~{143.55 + O3_DUR:.2f}) — 화면은 원음과 다른 장면(말과 맞는 화면)"
    M["_note"] = M["_note"].split(" 시각은")[0] + " 시각 = make_render.py PLAN(미나 TTS 뒤 확정)."
    (D / "재료.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    return S, M


def main(render=True, mix_only=False):
    R.mkdir(parents=True, exist_ok=True)
    if not (SRC / VOICE).exists():
        run(["ffmpeg", "-y", "-i", str(SRC / SRCV), "-vn", "-ac", "1", "-ar", "48000", "-af", VOICE_AF, str(SRC / VOICE)])
    P = plan()
    dur = P["dur"]
    fr0 = json.loads(FRAME.read_text(encoding="utf-8"))
    ycol = next(l for l in fr0["layers"] if l.get("role") == "caption")["rgb"]
    # 자막 시각표: 원음 흰 / 나레 노랑 — 조각은 다음 조각 시작까지
    caps = [(0.0, "꼭 나갈 때마다", "원음"), (0.95, "한 여섯 개씩", "원음"), (2.75, "기본 사고", "원음"), (3.65, "또 틈만 나면 사는 거야", "원음")]
    for i, (t0, _) in enumerate(P["n"]):
        ts = [t0] + chunk_times(i, t0)
        caps += [(t, w, "나레") for t, w in zip(ts, NCHUNK[i])]
        if i == 1:
            caps.append((P["o3"][0], "솔직히 쟁여 놓고 쓰거든", "원음"))
            caps.append((P["o3"][0] + O3_B, "여기 또 엑스트라 하나 있잖아", "원음"))
    caps.sort()
    ev = []
    for j, (t, txt, who) in enumerate(caps):
        b = caps[j + 1][0] if j + 1 < len(caps) else dur
        ev.append({"kind": "emph", "text": txt, "rgb": ycol if who == "나레" else [255, 255, 255], "t0": round(t, 3), "dur": round(b - t, 3), "who": who})
    S, M = write_docs(P, ev)
    win = [tuple(P["o1"]), (round(P["o3"][0], 3), round(P["o3"][1], 3))]
    print("dur", dur, "lines", [[round(x, 3) for x in n] for n in P["n"]], "orig", win)
    for p in P["shots"]:
        print("  shot", p)
    for e in ev:
        print(f"  emph {e['t0']:6.2f}+{e['dur']:.2f} {e['who']} {e['text']}")
    if not render:
        return
    if not mix_only:
        gapped(P)
        L = [" ".join(l["text"].rstrip(".").replace(",", "") for l in S["final"]["lines"]) + "."]
        steps, dur2 = nv.time_steps(nv.steps_of(L, 10, "replace"), str(WAV), lines=L, asr=False)
        print("wav dur", dur2)
        shots_r = [{"i": 0, "full": True, "kind": "원본재편집", "src": SRCV, "ss": P["shots"][0]["ss"], "src_crop": P["shots"][0]["crop"],
                    "cuts": [{"src": SRCV, "ss": p["ss"], "src_crop": p["crop"], "dur": round(p["t1"] - p["t0"], 3), "plan_i": k} for k, p in enumerate(P["shots"])],
                    "t_final": [0.0, dur]}]
        (D / "재료_render.json").write_text(json.dumps({"_note": "make_render.py — 페이지 1개 × shots[].cuts(PLAN 시각 그대로)", "cand_dir": M["cand_dir"],
                                                      "shots": shots_r}, ensure_ascii=False, indent=1), encoding="utf-8")
        SR = dict(S, final=dict(S["final"], lines=[{"text": L[0], "note": "렌더용 한 문장(엔진 우회 — 한고은 편 ⑥과 같음) — 원문 줄은 대본.json"}]),
                  caption_events=ev, render={"windows": [list(w) for w in win], "dur": dur, "tts": "일레븐랩스 미나 1회 → 줄별 atempo " + "/".join(map(str, TEMPO))})
        (D / "대본_render.json").write_text(json.dumps(SR, ensure_ascii=False, indent=1), encoding="utf-8")
        fr = json.loads(FRAME.read_text(encoding="utf-8"))
        for l in fr["layers"]:
            if l.get("role") == "title":
                l["text"] = TITLE
            if l.get("role") == "label":
                l["text"] = LABEL
        (D / "frame_render.json").write_text(json.dumps(fr, ensure_ascii=False, indent=1), encoding="utf-8")
        plan_ = {"tteutgi": str(TTEUTGI), "frames": [{"frame": str(D / "frame_render.json"), "t_end": None}],
                 "script": str(D / "대본_render.json"), "tts": str(WAV), "materials": str(D / "재료_render.json"), "out": str(R), "bgm": None,
                 "lufs": LUFS_NARR, "chunk": 10, "caption_mode": "replace", "line_asr": False}
        final = nv.build(plan_)
        Path(final).replace(R / "final_narr.mp4")
    # 소리 시간표: 컷 단위. 뒷머리 컷은 [무음(나레 끝까지) | 원음 143.51~ | 말 끝+0.08 뒤 무음(다음 나레 밑에 원음이 깔리지 않게)]
    tl, aud = [], []
    for k, p in enumerate(P["shots"]):
        segs = [(p["t0"], p["t1"], p["audio_ss"])]
        if p["audio_ss"] == "O3":   # O3 원음은 화면 두 컷에 걸쳐 끊김 없이 143.51~ (말 143.55 = o3 시작)
            a0 = round(P["o3"][0] - 0.04, 3)
            cut = round(P["o3"][1] + 0.08, 3)
            lo, hi = max(p["t0"], a0), min(p["t1"], cut)
            segs = [(p["t0"], lo, None), (lo, hi, round(143.51 + lo - a0, 3)), (hi, p["t1"], None)]
        for a, b, ass in [x for x in segs if x[1] - x[0] > 0.01]:
            tl.append([a, b])
            snd = {"i": len(aud), "src": SRCV, "ss": p["ss"], "plan_i": k, "t_final": [a, b]}
            if ass is None:
                snd["mute"] = True
            else:
                snd["audio_src"], snd["audio_ss"] = VOICE, ass
            aud.append(snd)
    (R / "audio_timeline.json").write_text(json.dumps({"shots": tl, "dur": dur}, ensure_ascii=False, indent=1), encoding="utf-8")
    (R / "audio_materials.json").write_text(json.dumps({"cand_dir": M["cand_dir"], "shots": aud}, ensure_ascii=False, indent=1), encoding="utf-8")
    gains = [float(x) for x in sys.argv[sys.argv.index("--gain") + 1].split(",")] if "--gain" in sys.argv else GAINS
    gwin = [win[0], (win[1][0], win[1][0] + O3_SPLIT), (win[1][0] + O3_SPLIT, win[1][1])]
    gg = [r for w, g in zip(gwin, gains) for r in ramp(w[0], min(w[1] + 0.10, dur), g)]
    ha.add_source_bed(str(R / "final_narr.mp4"), str(R / "audio_timeline.json"), str(R / "audio_materials.json"), str(WAV), str(R / "final_src.mp4"),
                      1.0, 10.0, work=str(R / "srcbed"), gap_gain=gg)
    res = bgm_mix(R / "final_src.mp4", R / "final.mp4", win, dur)
    print(json.dumps(res, ensure_ascii=False))
    print("나레", json.dumps(ha.measure(str(R / "final.mp4"), [tuple(n) for n in P["n"]]), ensure_ascii=False))
    print("원음", json.dumps(ha.measure(str(R / "final.mp4"), win), ensure_ascii=False))
    print("전체", json.dumps(ha.measure(str(R / "final.mp4"), [(0, dur)]), ensure_ascii=False))


if __name__ == "__main__":
    main(render="--dry" not in sys.argv, mix_only="--mix-only" in sys.argv)
