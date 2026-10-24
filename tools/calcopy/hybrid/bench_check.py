# -*- coding: utf-8 -*-
"""벤치 판(renderer=bench) 렌더 뒤 자동 검사 — 판 설정의 길이·음량·창 + 배치 대조 + 0초 얼굴 (관제 097, 2026-10-19).

    PYTHONUTF8=1 py tools/calcopy/hybrid/bench_check.py <판> <doc_dir> <work_dir>

잰다: ① 길이 = 판 설정 length 안 · 완성본 화면 = 시간표 끝 ±1프레임 ② 음량 = loudness.lufs ±0.5, 최고점 ≤ tp+0.5
③ 0초·첫 줄 구간 연예인 얼굴(thumb.face_check, 창 = frame.window) ④ 배치 = placement.check_place(본보기 벤치 편과 칸별 등장·강조 비율)
⑤ 컷 조각 프레임 = 시간표 계획(모자라면 뒤 컷이 앞당겨져 화면·소리가 어긋난다) ⑥ 화면 멈춤 = 창 안 같은 그림 FREEZE_SEC 이상 0건 ⑦ 컷 끝 번쩍임 = 조각 처음·끝 0.2초 안 장면 경계 0건(render_bench.snap_ss 가 나레 컷은 미리 피한다)
   (10-23 사장님 "뒤에 멈추거나 중간중간 튀는 게 있다 / 재발 안 되게": 05·08·09·11 이 원본 끝을 넘는 컷으로 끝 0.9~1.7초 멈춤 — 그때 검사 6줄은 전부 통과였다)
결과 = <doc>/자동검사.json. 벤치와 나란히 보는 시트는 compare_sheet.py(눈 확인용).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.hybrid.common import FPS, jload, jsave, lufs, run  # noqa: E402


def vdur(p) -> float:
    return float(run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration", "-of", "csv=p=0", p]).stdout.strip().split(",")[0] or 0)   # 98 #73


FREEZE_SEC = 0.3      # 창 안 같은 그림이 이만큼 이어지면 멈춤(벤치 컷 중앙 약 1초 · 실제 촬영 영상은 프레임마다 잡음이 있어 0이 안 나온다)


def part_frames(R: Path, T: dict) -> list:
    """컷 조각마다 (번호, 줄, 원본@초, 계획, 실제) — 계획과 다른 것만."""
    from tools.calcopy.hybrid.render_bench import count_frames
    bad = []
    for k, c in enumerate(T["cuts"]):
        p = R / "parts" / f"c{k:02d}.mp4"
        got = count_frames(p) if p.exists() else 0
        if got != c.get("frames"):
            bad.append((k, c["line"], f"{c['src']}@{c.get('ss')}", c.get("frames"), got))
    return bad


def part_slivers(R: Path, T: dict, src_dir: Path | None = None) -> list:
    """컷 처음·끝 0.2초 안에 원본 장면 경계가 있는 것(이웃 샷이 몇 프레임 끼어 번쩍임) — (번호, 줄, 원본@초, 경계 초(컷 기준)).
    경계 판정 = render_bench.shot_starts(원본) 한 곳(나레 컷 snap_ss 와 같은 판정 — 조각을 따로 재면 문턱이 달라 어긋났다, 10-24)."""
    from tools.calcopy.hybrid.render_bench import IMG_EXT, SLIVER_SEC, shot_starts, slivers
    bad = []
    for k, c in enumerate(T["cuts"]):
        src = Path(src_dir) / c["src"] if src_dir else None
        if not src or not src.exists() or src.suffix.lower() in IMG_EXT:
            continue
        a = float(c.get("ss") or 0.0)
        sv = slivers(shot_starts(src), a, a + (c.get("frames") or 0) / FPS, SLIVER_SEC)
        if sv:
            bad.append((k, c["line"], f"{c['src']}@{a}", [round(x - a, 3) for x in sv]))
    return bad


def thumb_stamped(video: Path, doc: Path) -> tuple[bool | None, str]:
    """썸네일.json 이 있으면 완성본 0·1프레임 = 고른 카드 그림인가(회색 평균 차 < 12 — 광고 표시·압축 차 허용), 2프레임은 카드가 아닌가."""
    import subprocess
    import numpy as np
    from PIL import Image
    sp = Path(doc) / "썸네일.json"
    if not sp.exists():
        return None, "썸네일.json 없음(검사 안 함)"
    pk = jload(sp).get("pick")
    jpg = Path(doc) / "thumb" / f"{pk}.jpg"
    ref = np.asarray(Image.open(jpg).convert("L").resize((108, 192)), dtype=np.int16)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", r"select=lt(n\,3),scale=108:192,format=gray", "-vsync", "0",
                          "-f", "rawvideo", "-"], capture_output=True, stdin=subprocess.DEVNULL).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, 192, 108).astype(np.int16)
    d = [round(float(np.abs(f - ref).mean()), 1) for f in fr]
    ok = len(d) == 3 and d[0] < 12 and d[1] < 12 and d[2] >= 12
    return ok, f"안 {pk} · 프레임 0·1·2 차 {d}"


def freezes(video: Path, win, min_sec: float = FREEZE_SEC) -> list:
    """창 안(win = x,y,w,h) 그림이 그대로인 구간 [(시작초, 끝초)] — 프레임 차(108폭 회색 평균) < 0.05 가 min_sec 이상."""
    import numpy as np
    x, y, w, h = win
    sw, sh = 108, max(8, round(108 * h / w))
    import subprocess
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"crop={w}:{h}:{x}:{y},scale={sw}:{sh},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True, stdin=subprocess.DEVNULL, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, sh, sw).astype(np.int16)
    same = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2)) < 0.05
    out, i, need = [], 0, round(min_sec * FPS)
    while i < len(same):
        if same[i]:
            j = i
            while j < len(same) and same[j]:
                j += 1
            if j - i + 1 >= need:
                out.append((round(i / FPS, 2), round((j + 1) / FPS, 2)))
            i = j
        else:
            i += 1
    return out


def check(style_name: str, doc: Path, work: Path, log=print) -> dict:
    from tools.calcopy.hybrid import styles as ST, thumb
    st = ST.load(style_name)
    R = Path(work) / "render"
    final = R / "final.mp4"
    T = jload(R / "timeline.json")
    tab = jload(R / "자막표.json")
    d = vdur(final)
    I, tp = lufs(final)
    L, LD = st["loudness"], st["length"]
    x, y, w, h = st["frame"]["window"]
    first = T["lines"][next(iter(T["lines"]))]
    face = thumb.face_check(final, (x, y, w, h), tuple(first), log=log)
    short = part_frames(R, T)
    fz = freezes(final, (x, y, w, h))
    tok, tmsg = thumb_stamped(final, doc)
    sl = part_slivers(R, T, Path(jload(Path(doc) / '재료.json')['cand_dir']))
    rows = [("길이", LD["min"] - 0.5 <= d <= LD["max"] + 0.5, f"{d:.2f}초 (판 {LD['min']}~{LD['max']})"),
            ("화면=시간표", abs(d - T["end"]) <= 1 / FPS + 0.01, f"{d:.3f} vs {T['end']}"),
            ("음량", abs(I - L["lufs"]) <= 0.5, f"{I} LUFS (목표 {L['lufs']})"),
            ("최고점", tp <= L["tp"] + 0.5, f"{tp} dBFS (≤ {L['tp']}+0.5)"),
            ("0초·첫 줄 얼굴", face["ok"], " ".join(f"{f['t']}s:{'○' if f['ok'] else f['why']}" for f in face["frames"])),
            ("컷 조각 프레임 = 계획", not short, "전부 같음" if not short else str(short)),
            ("화면 멈춤 없음", not fz, "0건" if not fz else " ".join(f"{a}~{b}s" for a, b in fz)),
            ("컷 끝 번쩍임 없음(0.2초 안 장면 경계)", not sl, "0건" if not sl else str(sl)),
            ("썸네일 맨 앞 2프레임", tok is not False, tmsg),
            ("배치(본보기 벤치 편 대조)", tab["check"]["ok"], f"본보기 {tab['check']['reference']} · 칸 최대 차 {tab['check']['worst_slot_diff']}")]
    ok = all(r[1] for r in rows)
    rep = {"style": style_name, "ok": ok, "rows": [{"what": a, "ok": b, "value": c} for a, b, c in rows], "placement": tab["check"], "log": tab.get("log")}
    jsave(Path(doc) / "자동검사.json", rep)
    for a, b, c in rows:
        log(f"  {'○' if b else '×'} {a}: {c}")
    return {"ok": ok, "report": str(Path(doc) / "자동검사.json")}


if __name__ == "__main__":
    r = check(sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]))
    sys.exit(0 if r["ok"] else 1)
