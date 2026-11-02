"""벤치마킹 결과물 검사(관제 304) — 실제 회원 설치본 + 묶음 + 짧은 실제 영상으로 뜯기→틀→프리셋을 재현한다(계산 대조 아님).

  py tools/claude_portal/benchmark_check.py --video <mp4> [--install <설치 폴더>] [--pack <benchmark_pack.zip>] [--work <임시 폴더>]

하는 일: ①설치본 엔진을 하드링크로 복제(설치본은 건드리지 않는다) ②묶음에서 없는 파일만 풀기(회원 PC 와 같은 판단)
③설치본 파이썬으로 bench_member 실행(회원 PC 환경값, 판독 = 줄 폴더에 고정 답) ④나온 frame.json·manifest 검사.
rc=0 이면 그 설치본에서 묶음이 돈다. 서버·키를 쓰지 않는다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANSWERS = ROOT / "installer" / "common" / "engine_traces" / "benchmark" / "answers_Ks5kYYKAUlQ.json"


def clone(src: Path, dst: Path) -> None:
    """하드링크 복제 — 디스크를 안 쓰고, 복제본에 파일을 더해도 설치본은 그대로다."""
    for d, _, files in os.walk(src):
        rel = Path(d).relative_to(src)
        if "__pycache__" in rel.parts or "node_modules" in rel.parts:
            continue
        (dst / rel).mkdir(parents=True, exist_ok=True)
        for f in files:
            os.link(Path(d) / f, dst / rel / f)


def unpack(zip_path: Path, root: Path) -> list[str]:
    written = []
    with zipfile.ZipFile(zip_path) as z:
        for n in z.namelist():
            if not (root / n).exists():
                (root / n).parent.mkdir(parents=True, exist_ok=True)
                (root / n).write_bytes(z.read(n))
                written.append(n)
    return written


def reply(req: dict, A: dict) -> dict:
    tag, labels = req["tag"], [p["text"] for p in req["parts"] if p["kind"] == "text"]
    if tag.startswith("ocr"):
        return {"items": [{"label": lab.split(" (")[0], "lines": A["ocr_all"]} for lab in labels]}
    if tag.startswith("title"):
        return {"items": [{"label": lab, "lines": A["title_bands"][i] if i < len(A["title_bands"]) else []} for i, lab in enumerate(labels)]}
    if tag == "frame_ocr":
        return A["frame_ocr"]
    if tag == "asr":
        m = re.search(r"([\d.]+)~([\d.]+) \| [^|]* \| [^|]* \| (.+)", "\n".join(labels))
        return {"speakers": [{"id": "S1", "gender": "unknown", "voice": "unknown"}], "ambient": "", "sfx": [], "voice_tone": "",
                "segments": [{"start": float(m[1]), "end": float(m[2]), "speaker": "S1", "lang": "ko", "kind": "narration", "text": m[3]}] if m else [],
                "bgm": {"present": False, "mood": [], "start": 0, "fade_out": False}}
    if tag == "bench_kind":
        return {"source_kind": A["source_kind"]}
    return {}


def answerer(q: Path, A: dict, stop: threading.Event, log: list) -> None:
    while not stop.is_set():
        for d in list(q.glob("*")):
            r = d / "request.json"
            if r.exists() and not (d / "answer.json").exists() and not (d / "done").exists():
                req = json.loads(r.read_text(encoding="utf-8"))
                log.append(req["tag"])
                tmp = d / "a.tmp"
                tmp.write_text(json.dumps(reply(req, A), ensure_ascii=False), encoding="utf-8")
                tmp.replace(d / "answer.json")
        time.sleep(0.3)


def verdict(out: Path, r: dict) -> list[str]:
    bad = []
    if not r.get("ok"):
        return [f"실행 실패: {r}"]
    pdir = out / "channel" / r["slug"] / "preset" / r["presets"][0]["style"]
    F = json.loads((pdir / "frame.json").read_text(encoding="utf-8"))
    M = json.loads((pdir / "manifest.json").read_text(encoding="utf-8"))
    kinds = {f"{L.get('kind')}:{L.get('role')}" for L in F.get("layers") or []}
    for want in ("bg:None", "video:None", "text:title"):
        if want not in kinds:
            bad.append(f"틀에 {want} 층이 없다: {sorted(kinds)}")
    if F.get("canvas") != [1080, 1920]:
        bad.append(f"캔버스가 다르다: {F.get('canvas')}")
    if M.get("source_kind") != "고객제품":
        bad.append(f"소재 유형이 저장되지 않았다: {M.get('source_kind')}")
    for s in M.get("sources") or []:
        if not s["tteutgi"].startswith(f"channel/{r['slug']}/뜯기/") or not (out / s["tteutgi"]).is_file():
            bad.append(f"뜯기 경로가 틀렸다: {s['tteutgi']}")
    left = [p.name for p in (out / "channel" / r["slug"] / "뜯기").rglob("*") if p.is_file() and p.name != "뜯기.json"]
    if left:
        bad.append(f"벤치 화면 조각이 남았다: {left[:3]}")
    return bad


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, action="append")
    ap.add_argument("--install", default=str(Path(os.environ.get("LOCALAPPDATA", "")) / "Shortem"))
    ap.add_argument("--pack", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--answers", default=str(ANSWERS))
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args(argv)
    inst, work = Path(a.install), Path(a.work)
    shutil.rmtree(work, ignore_errors=True)
    engine, q, out = work / "engine", work / "q", work / "out"
    q.mkdir(parents=True)
    clone(inst / "engine", engine)
    written = unpack(Path(a.pack), engine)
    print(f"설치본 {json.loads((inst / 'app_version.json').read_text())['version']} · 묶음에서 새로 푼 파일 {len(written)}개: {[Path(w).name for w in written]}")
    tools = inst / "tools"
    env = {"PATH": os.pathsep.join([str(tools / "ffmpeg"), str(tools / "ffmpeg" / "bin"), str(tools / "yt-dlp"), os.environ.get("SystemRoot", "") + "\\System32"]),
           "SystemRoot": os.environ.get("SystemRoot", ""), "TEMP": str(work), "TMP": str(work), "USERPROFILE": os.environ.get("USERPROFILE", ""), "LOCALAPPDATA": os.environ.get("LOCALAPPDATA", ""),
           "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "CALCOPY_GEMINI_BACKEND": "client", "CALCOPY_CUSTOMER_MODE": "1", "SHORTEM_LLM_QUEUE": str(q),
           "CALCOPY_DATA_DIR": str(work / "data"), "CHANNEL_FIND_CACHE": str(work / "cache"), "YTDLP_PROXY_SLOTS": "0"}
    wd = inst / "models" / "whisper"
    if wd.exists():
        env["SHORTEM_WHISPER_DIR"] = str(wd)
    stop, asked = threading.Event(), []
    th = threading.Thread(target=answerer, args=(q, json.loads(Path(a.answers).read_text(encoding="utf-8")), stop, asked), daemon=True)
    th.start()
    t0 = time.time()
    cmd = [str(tools / "python" / "python.exe"), str(engine / "tools/calcopy/engine/bench_member.py"), "--out", str(out), "--name", "검사"]
    for v in a.video:
        cmd += ["--video", v]
    p = subprocess.run(cmd, cwd=engine, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    stop.set()
    print(f"rc={p.returncode} · {round(time.time() - t0)}초 · 판독 요청 {asked}")
    last = (p.stdout.strip().split("\n") or [""])[-1]
    try:
        r = json.loads(last)
    except ValueError:
        r = {"ok": False, "why": last[:300], "stderr": p.stderr[-800:]}
    print("결과:", json.dumps(r, ensure_ascii=False)[:600])
    bad = verdict(out, r)
    for b in bad:
        print("★", b)
    print("검사: " + ("통과" if not bad else f"{len(bad)}건 빨강"))
    if not a.keep:
        shutil.rmtree(work, ignore_errors=True)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
