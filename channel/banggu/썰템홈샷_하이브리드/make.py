# -*- coding: utf-8 -*-
"""썰템홈샷 하이브리드 한 편 제작기 (관제 097, 2026-10-22 사장님 "썰템홈샷 스타일 영상 · 방구석이랑 다르게 · 표절 안 걸리게").

    PYTHONUTF8=1 py channel/banggu/썰템홈샷_하이브리드/make.py <단계> <편>
    단계: frames | tts | plan | render | checks | all(=frames→tts→plan→render→checks)

편 = 이 폴더의 <편>/ — 대본.json(topic·hook[2줄]·post·tempo·final.lines[{fn,text,seg:A|B,facts,sources}]·facts) · 재료.json · 근거.md
작업물(git 밖) = C:/숏템_칼카피/banggu/썰템홈샷_하이브리드/<편>/ (src·narr·final.mp4)

하이브리드 = 앞(seg A) 썰 + 뒤(seg B) "저도 사 봤는데" 체험 — 한 렌더(같은 목소리·같은 틀·같은 BGM, §14 앞뒤 전환).
틀 = 썰템홈샷 외관(10-17 샘플 B 차콜·민트 — make_썰템홈샷.py 의 header/text/band/CORNER 를 그대로 부른다).
목소리 = 박창수 tc_6059dad0b83880769a50502f · tempo 기본(대본 tempo 로만 바꿈, 상한 1.25) — 필재 금지(§12).
받아쓰기 = 스피치매틱스(asr_local, 규칙 12) — narr_video 줄 시작 캐시(<mp3>.asr.json)를 먼저 채워 제미나이를 부르지 않는다.
컷 시각 = narr_video.plan_times 한 곳(plan 표와 렌더가 같은 계산). 재료.json sfx 는 t(초) 또는 line(대본 줄 번호 — 그 줄 첫 자막 시각).
관문(checks) = 길이 · LUFS · bench_distance(방구석 표절) · 나레 받아쓰기 대조 · 광고 표시(engine/ad_mark) · 1초 시트.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path

H = Path(__file__).resolve().parent
ROOT = H.parents[2]
sys.path.insert(0, str(ROOT))
WORK = Path("C:/숏템_칼카피/banggu/썰템홈샷_하이브리드")
VOICE = "tc_6059dad0b83880769a50502f"   # 박창수
TEMPO_MAX = 1.25
LENGTH = (30.0, 42.0)                   # 앞 썰(방구석 결 중앙 ~26초) + 뒤 체험 10~15초
BGM, BGM_RATIO, LUFS = "honwaka_puppu", 0.22, -14.0
CHUNK = 13
TTEUTGI = ROOT / "channel/banggu/칼카피_ILIi/뜯기2/뜯기.json"   # 그림 칸 분포만 씀(내용 아님)

_spec = importlib.util.spec_from_file_location("make_sth", H.parent / "make_썰템홈샷.py")
K = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(K)


def _j(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _w(p, d):
    Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def paths(piece: str) -> dict:
    d, w = H / piece, WORK / piece
    w.mkdir(parents=True, exist_ok=True)
    return {"d": d, "w": w, "script": d / "대본.json", "mat": d / "재료.json", "full": w / "narr_full.mp3", "tts": w / "narr_tight.mp3",
            "hook": d / "frame_hook.json", "body": d / "frame_body.json", "out": w / "render"}


def frames(piece: str):
    P = paths(piece); S = _j(P["script"])
    hook, post = S["hook"], S["post"]
    meta = K.BRAND + " · 14:25"
    post2 = K.split2(post)
    body = {"canvas": [1080, 1920], "made_by": K.schema.MADE_BY, "source": None,
            "made_from": {"tool": "channel/banggu/썰템홈샷_하이브리드/make.py", "note": "썰템홈샷 외관(샘플 B 차콜·민트) — make_썰템홈샷 body 와 같은 층"},
            "layers": [
                {"kind": "bg", "rgb": K.PAGE},
                {"kind": "video", "x": 0, "y": 510, "w": 1080, "h": 1300, "radius": 0},
                K.band(0, 510, 48, 1300, K.PAGE, 0), K.band(1032, 510, 48, 1300, K.PAGE, 0),
                {"kind": "image", "src": K.CORNER, "x": 48, "y": 510, "w": 984, "h": 1300},
                *K.header(),
                K.band(48, 250, 984, 220, K.WHITE, K.R),
                K.text("label", "CcPretendard-SemiBold", meta, 284, 24, 540, 900, "center", K.MINT_DK, text=meta),
                K.text("label", "SUITBold", post2, 336, 50, 540, 920, "center", K.INK, lines=2, line_h=70, text=post2),
                K.text("caption", "CcPretendard-Bold", "아웃백에서 사람들이", 1604, 50, 540, 900, "center", K.WHITE, lines=2, line_h=82, valign="top",
                       box={"rgb": K.CHAR, "pad": 22, "radius": 22}),
            ]}
    hookf = {"canvas": [1080, 1920], "made_by": K.schema.MADE_BY, "source": None,
             "made_from": {"tool": "channel/banggu/썰템홈샷_하이브리드/make.py", "note": "훅 카드 — make_썰템홈샷 hook 과 같은 층"},
             "layers": [
                 {"kind": "bg", "rgb": K.CHAR},
                 {"kind": "video", "x": 0, "y": 780, "w": 1080, "h": 1140, "radius": K.R},
                 *K.header(),
                 K.text("title", "SUITBold", hook[0], 290, 92, 540, 1000, "center", K.WHITE, lines=2, line_h=150,
                        text=chr(10).join(hook), line_rgb=[K.WHITE, [90, 240, 200]]),
                 K.text("label", "CcPretendard-SemiBold", post, 650, 36, 540, 960, "center", [168, 180, 184], text=post),
             ]}
    for p, f in ((P["hook"], hookf), (P["body"], body)):
        K.schema.validate(f); _w(p, f)
    print("틀 ok", P["hook"].name, P["body"].name)


def _lines(S):
    return [l["text"] for l in S["final"]["lines"]]


def tts(piece: str):
    P = paths(piece); S = _j(P["script"])
    tempo = S.get("tempo")
    if tempo and tempo > TEMPO_MAX:
        raise SystemExit(f"tempo {tempo} > 상한 {TEMPO_MAX} — 배속 말고 글을 줄인다")
    text = " ".join(_lines(S))
    stamp = P["w"] / "narr_full.txt"
    same = P["full"].exists() and stamp.exists() and stamp.read_text(encoding="utf-8") == f"{tempo}|{text}"
    if not same:   # 대본·배속이 같으면 다시 합성하지 않는다(타입캐스트 과금 1회)
        from shopping_shorts.channelkit import providers
        providers.typecast_synth(VOICE, tempo=tempo)(text, str(P["full"]))
        stamp.write_text(f"{tempo}|{text}", encoding="utf-8")
        P["tts"].unlink(missing_ok=True)
        print("TTS 1회(박창수):", P["full"])
    if not P["tts"].exists():
        f = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02"
        mid = "silenceremove=stop_periods=-1:stop_duration=0.1:stop_threshold=-45dB:stop_silence=0.07"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(P["full"]), "-af", f"{f},areverse,{f},areverse,{mid}", "-c:a", "libmp3lame",
                        "-q:a", "2", str(P["tts"])], check=True, stdin=subprocess.DEVNULL)
    asr = asr_cache(P["tts"])
    heard = "".join(s["text"] for s in asr)
    from tools.calcopy.narr_video import speech_segments
    from tools.calcopy.hybrid.common import nchar as nchar_ko
    dur = speech_segments(str(P["tts"]))[1]
    n = nchar_ko(text)
    print(f"나레 {dur:.2f}초 · {n}자 · {n / dur:.2f}자/초(벤치 8.32)")
    print("받아쓰기 대조:", round(SequenceMatcher(None, _flat(text), _flat(heard)).ratio(), 3), "\n  들린 글:", heard)


def _flat(s):
    import re
    return re.sub(r"[\s,.!?~'\"·…ㅋ]", "", s or "")


def asr_cache(mp3: Path) -> list[dict]:
    """스피치매틱스 받아쓰기 → narr_video.tts_transcript 캐시 꼴({md5, model, segments[start,end,text]})."""
    cache = mp3.with_name(mp3.name + ".asr.json")
    md5 = hashlib.md5(mp3.read_bytes()).hexdigest()
    if cache.exists():
        c = _j(cache)
        if c.get("md5") == md5:
            return c["segments"]
    from tools.calcopy.engine import asr_local
    r = asr_local.transcribe(str(mp3), engine="speechmatics")
    seg = [{"start": s["start"], "end": s["end"], "text": s["text"]} for s in r.get("segments") or [] if s.get("text")]
    if not seg:
        raise SystemExit("받아쓰기 빈 답 — 멈춤")
    _w(cache, {"md5": md5, "model": r.get("engine"), "note": r.get("note"), "segments": seg})
    print("받아쓰기:", r.get("engine"), r.get("note") or "")
    return seg


def _plan(P):
    return {"tteutgi": str(TTEUTGI), "frames": [{"frame": str(P["hook"]), "t_end": None}, {"frame": str(P["body"]), "t_end": None}],
            "script": str(P["script"]), "tts": str(P["tts"]), "materials": str(P["w"] / "재료_시각.json"), "out": str(P["out"]),
            "bgm": BGM, "bgm_ratio": BGM_RATIO, "lufs": LUFS, "chunk": CHUNK}


def plan(piece: str) -> dict:
    """컷 계획표 — 컷마다 시각·그 동안의 자막·줄(A 썰/B 체험). 재료.json shots 는 이 순번대로 채운다."""
    from tools.calcopy import narr_video as nv
    P = paths(piece); S = _j(P["script"])
    asr_cache(P["tts"])
    T = nv.plan_times(_plan(P), S)
    seg_of = [l.get("seg", "A") for l in S["final"]["lines"]]
    rows = []
    for k, (a, b) in enumerate(T["shots"]):
        caps = [s for s in T["steps"] if s["t0"] < b - 1e-6 and s["t1"] > a + 1e-6]
        li = caps[0]["sent"] if caps else 0
        rows.append({"shot": k, "t0": round(a, 2), "t1": round(b, 2), "dur": round(b - a, 2), "line": li, "seg": seg_of[li],
                     "caption": " / ".join(dict.fromkeys(c["text"] for c in caps)), "hook_card": a < T["hook_end"] - 1e-6})
    first = {}
    for s in T["steps"]:
        first.setdefault(s["sent"], s["t0"])
    out = {"dur": round(T["dur"], 2), "hook_end": round(T["hook_end"], 2), "line_t0": first, "shots": rows}
    _w(P["w"] / "계획.json", out)
    for r in rows:
        print(f"#{r['shot']:02d} {r['t0']:6.2f}~{r['t1']:6.2f} ({r['dur']:.2f}) 줄{r['line']} {r['seg']} {'[훅]' if r['hook_card'] else ''} {r['caption']}")
    print(f"컷 {len(rows)} · 길이 {out['dur']}초 · 훅 끝 {out['hook_end']}초 → 재료.json shots {len(rows)}개 필요")
    return out


def render(piece: str):
    from tools.calcopy import narr_video as nv
    import inspect
    P = paths(piece)
    pl = plan(piece)
    M = _j(P["mat"])
    for x in M.get("sfx") or []:   # line = 그 줄 첫 자막 시각(판단 한 곳 = plan 의 line_t0)
        if "line" in x:
            x["t"] = round(pl["line_t0"][int(x["line"])] + float(x.get("dt", 0)), 3)
    _w(P["w"] / "재료_시각.json", M)
    _orig = nv.shot_clip

    def _wide(*a, **k):   # 썰템홈샷 v2 와 같게: 그림 칸 = 창 전체(가로 984 둥근 카드·cover), 자막은 그림 위 아래쪽
        b = inspect.signature(_orig).bind(*a, **k); b.apply_defaults(); g = b.arguments
        if not g["full"]:
            g["box"] = [48, 0, 984, g["win"]["h"]]; g["min_y"] = 0; g["anchor"] = True; g["fit"] = "cover"
        return _orig(*b.args, **b.kwargs)
    nv.shot_clip = _wide
    try:
        fin = nv.build(_plan(P))
    finally:
        nv.shot_clip = _orig
    from tools.calcopy.engine import ad_mark   # 모든 렌더 오른쪽 위 '광고'(사장님 10-22, 주인 한 곳)
    ad_mark.apply_inplace(Path(fin))
    print("final", fin)


def checks(piece: str) -> dict:
    from tools.calcopy import bench_distance as BD
    from tools.calcopy.engine import ad_mark
    P = paths(piece); S = _j(P["script"])
    fin = P["out"] / "final.mp4"
    au = _j(P["out"] / "audio.json")
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(fin)],
                               capture_output=True, text=True).stdout.strip())
    bd = BD.check("banggu", P["script"], P["mat"])
    heard = "".join(s["text"] for s in asr_cache(P["tts"]))
    asr_ratio = round(SequenceMatcher(None, _flat(" ".join(_lines(S))), _flat(heard)).ratio(), 3)
    sheet = P["out"] / "final_sheet_1s.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(fin), "-vf", "fps=1,scale=216:384,tile=8x5", "-frames:v", "1", str(sheet)], check=True)
    text_all = " ".join(_lines(S))
    import re
    r = {"길이": [round(dur, 2), LENGTH[0] <= dur <= LENGTH[1]],
         "LUFS": [au["final"]["I"], abs(au["final"]["I"] - LUFS) <= 0.5],
         "최고점": [au["final"]["TP"], au["final"]["TP"] <= -0.5],
         "방구석 표절": [bd["fails"] or "없음", bd["ok"]],
         "같은 소재 벤치 편(나란히 볼 것)": [[n["title"] for n in bd["same_topic"]], True],
         "나레 받아쓰기 대조": [asr_ratio, asr_ratio >= 0.9],
         "금액 없음": [re.findall(r"\d[\d,]*\s*(?:원|만원)", text_all) or "없음", not re.search(r"\d[\d,]*\s*(?:원|만원)", text_all)],
         "뒤 체험 줄 있음": [sum(l.get("seg") == "B" for l in S["final"]["lines"]), any(l.get("seg") == "B" for l in S["final"]["lines"])],
         "광고 표시": [ad_mark.MARK in ad_mark._probe(fin)[2], ad_mark.MARK in ad_mark._probe(fin)[2]],
         "시트": [str(sheet), True]}
    _w(P["out"] / "자동검사.json", r)
    ok = all(v[1] for v in r.values())
    for k, v in r.items():
        print(("○" if v[1] else "✗"), k, v[0])
    print("자동 검사", "통과" if ok else "실패", "— 사람 눈 확인 전")
    return r


if __name__ == "__main__":
    step, piece = sys.argv[1], sys.argv[2]
    for s in (["frames", "tts", "plan", "render", "checks"] if step == "all" else [step]):
        globals()[s](piece)
