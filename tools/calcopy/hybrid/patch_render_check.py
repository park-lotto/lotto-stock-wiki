# -*- coding: utf-8 -*-
"""구간 교체 결과물 대조(관제 304 · 0순위-C 결과물 검사) — 합성 영상으로 편 하나를 진짜 render() 로 만들고, 컷 그림 하나를 바꿔 구간 교체와 전체 렌더를 프레임·소리로 맞댄다.

  순서  ① 첫 렌더  ② 복사본 두 벌에 같은 변경(흐림 칸 또는 시작 초)  ③ 구간 교체  ④ 전체 렌더(SHORTEM_FULL_RENDER=1)  ⑤ 대조
  대조  프레임 수 · 구간 밖 프레임(첫 완성본과 md5 같은가) · 교체 구간(전체 렌더와 PSNR) · 소리(첫 완성본과 패킷 md5, 전체 렌더와 표본 차) · 시간
  자기 시험  대조가 어긋남을 잡나 — 교체 구간은 첫 완성본과 달라야 한다(같으면 아무것도 안 바꾼 것 = 이 도구가 아무것도 안 잰 것).
  돈 0: 목소리는 사인파로 대신하고(tts_by_line 등만 가짜) 나머지는 진짜 렌더 함수. 시험 입력 = 그림은 gradients(글자·얼굴 없음).

    PYTHONUTF8=1 py tools/calcopy/hybrid/patch_render_check.py <빈 폴더> [--style 키치잇판] [--change blur|move] [--cut 2] [--keep]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.calcopy.engine import final_splice as FS  # noqa: E402
from tools.calcopy.hybrid import partial_render_check as PC  # noqa: E402
from tools.calcopy.hybrid import render_bench as RB  # noqa: E402
from tools.calcopy.hybrid import render_itssum as RI  # noqa: E402

LINE_SEC = 2.0
VMAKE_SEC = 1.0      # 가짜 VMake 가 걸리는 초


def sh(*cmd):
    subprocess.run([str(c) for c in cmd], check=True, stdin=subprocess.DEVNULL, capture_output=True)


def stub_voice():
    """돈 드는 합성만 사인파로 — 나머지는 진짜 길."""
    def tbl(S, R, log=print):
        return R / "narr_full.mp3", None

    def sent(S, full, R, log=print, align=None, spread=None):
        out = []
        for i, l in enumerate(S["lines"]):
            w = R / f"s_{l['id']}.wav"
            if not w.exists():
                sh("ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=f={300 + 80 * i}:d={LINE_SEC}", "-ar", "48000", "-ac", "1", w)
            out.append({"id": l["id"], "dur": LINE_SEC, "raw": [i * LINE_SEC, (i + 1) * LINE_SEC], "tempo": 1.0, "wav": str(w)})
        return out, {"max": 1.0}, []
    RB.tts_by_line = tbl
    RI.make_sentences = sent
    RB._voice_gate_text = lambda S: None
    RB._voice_bad_audio = lambda S, sent, R, log=print: []
    RB.fit_voice = lambda S, st, sent, align, log=print: sent


def lean_encoder(threads: int = 2):
    """시험은 인코더 스레드를 줄인다(메모리 — x264 는 스레드마다 큰 버퍼, 커밋 여유 1.6GB PC 에서 malloc 실패 실측). 화질 인자는 그대로라 대조에 영향 없다."""
    from shopping_shorts import video_assemble as va
    from tools.calcopy.engine import ad_mark, encoder
    from tools.calcopy.hybrid import thumb
    real = encoder.venc

    def thin(crf=16, preset="veryfast"):
        v = real(crf, preset)
        return v + ["-threads", str(threads)] if "libx264" in v else v
    for m in (RB, ad_mark, thumb):
        m.venc = thin
    va._FFMPEG_THREADS = threads


def make_episode(W: Path, style: str, n_lines: int = 4) -> str:
    """작은 합성 편 — 원본 2개(소리 있음) · 나레 줄 n_lines · 줄마다 컷 하나."""
    src = W / "src"
    src.mkdir(parents=True)
    for i, (a, b) in enumerate((("0x224488", "0xdd8822"), ("0x118844", "0xcc2266"))):      # 컷끼리 원본 구간이 겹치지 않게(ss 간격 2.4초) — 흐림 칸이 다른 컷에 번지지 않는다
        sh("ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"gradients=s=720x1280:r=30:c0={a}:c1={b}:speed=0.05:d=34", "-f", "lavfi", "-i", f"sine=f={500 + i * 200}:d=34",
           "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", src / f"s{i}.mp4")
    d = W / "doc" / style
    d.mkdir(parents=True)
    words = [f"시험 자막 {i + 1}번 줄이에요" for i in range(n_lines)]
    S = {"slug": "patch_check", "title": "구간 교체 시험", "title_lines": ["구간 교체", "시험"], "source_label": "시험", "cps_target": 7.0, "voice": {"voice_id": "tc_test"},
         "lines": [{"id": f"N{i + 1}", "kind": "tts", "tts": words[i] + ".", "caps": [words[i]]} for i in range(n_lines)]}
    M = {"cand_dir": str(src), "cuts": {f"N{i + 1}": [{"src": f"s{i % 2}.mp4", "ss": round(1.0 + i * 2.4, 3), "crop": [0, 0, 720, 1280], "no_snap": True}] for i in range(n_lines)}}
    (d / "대본.json").write_text(json.dumps(S, ensure_ascii=False), encoding="utf-8")
    (d / "재료.json").write_text(json.dumps(M, ensure_ascii=False), encoding="utf-8")
    return str(d)


STAGES = {}


def timed():
    """단계별 걸린 초(시간 근거) — 진짜 함수를 감싸 재기만 한다."""
    from tools.calcopy.engine import final_splice, finalize
    from tools.calcopy.hybrid import quality_gate  # noqa: F401 — 측정 대상 아님, 메모리 측정 일정하게
    for mod, name in ((RB, "timeline_gates"), (RB, "render_window"), (RB, "window_transitions"), (RB, "render_base"), (RB, "burn_captions"), (RB, "audio"), (RB, "patch_final"),
                      (final_splice, "check"), (finalize, "seal")):
        real = getattr(mod, name)

        def wrap(*a, _real=real, _n=name, **k):
            t = time.time()
            try:
                return _real(*a, **k)
            finally:
                STAGES[_n] = round(STAGES.get(_n, 0) + time.time() - t, 2)
        setattr(mod, name, wrap)


def _render(W: Path, style: str, full: bool = False) -> tuple[float, dict, list]:
    env = {"SHORTEM_WAIVE_GATE": "1", **({RB.FULL_ENV: "1"} if full else {})}
    old = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    logs: list = []
    STAGES.clear()
    t0 = time.time()
    try:
        info = RB.render(style, W / "doc" / style, W / style, log=logs.append)
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return round(time.time() - t0, 2), info, logs


def fake_vmake(fail: bool):
    """가짜 VMake(돈 0) — 칸을 칠해 돌려준다. 뒤 프로세스는 스레드로. 호출 수를 센다."""
    from tools.calcopy import vmake_clean as VC
    calls = []

    def member_clean(files, key, log=print, tier=VC.TIER):
        calls.append([Path(f).name for f in files])
        time.sleep(VMAKE_SEC)
        if fail:
            raise RuntimeError("시험: VMake 실패")
        for f in map(Path, files):
            t = f.with_name(f.stem + "_v" + f.suffix)
            sh("ffmpeg", "-y", "-v", "error", "-i", f, "-vf", "drawbox=x=60:y=200:w=300:h=200:c=0x336699:t=fill", "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-threads", "2", "-pix_fmt", "yuv420p", t)
            VC.swap_in(f, t)
        return {"cleaned": [Path(f).name for f in files], "calls": 1, "fail": {}}

    def spawn(d):
        threading.Thread(target=VC.bg_run, args=(d,), daemon=True).start()
        return 1
    VC.member_clean, VC._spawn_bg, VC.member_key, VC.key_source, VC.free_ok = member_clean, spawn, (lambda: "k:s"), (lambda: "member"), (lambda: False)
    os.environ.pop("SHORTEM_NO_PAID", None)
    return calls


def vmake_round(W: Path, style: str, cut: int, fail: bool) -> dict:
    """첫 렌더(임시 흐림) 뒤 — 지시서가 하는 순서 그대로: 뒤로 보냄 → (기다리지 않고 렌더가 끝났다) → 받기 → 흐림 빼기."""
    from tools.calcopy import vmake_clean as VC
    from tools.calcopy.hybrid import rules as RU
    calls = fake_vmake(fail)
    p = W / "doc" / style / "재료.json"
    M = json.loads(p.read_text(encoding="utf-8"))
    c = M["cuts"][f"N{cut + 1}"][0]
    span = {c["src"]: [[round(float(c["ss"]) - 0.2, 3), round(float(c["ss"]) + LINE_SEC + 0.2, 3)]]}
    t0 = time.time()
    assert VC.bg_start(W / "src", span, "vmake"), "뒤로 못 보냄"
    waited = round(time.time() - t0, 3)
    r = VC.bg_take(W / "src", 60)
    if r.get("done"):
        RU.blur_minus_spans(M, r["done"])
        p.write_text(json.dumps(M, ensure_ascii=False), encoding="utf-8")
    return {"start_sec": waited, "state": r["state"], "done": r["done"], "calls": len(calls), "error": r.get("error")}


def change(W: Path, style: str, how: str, cut: int) -> str:
    p = W / "doc" / style / "재료.json"
    M = json.loads(p.read_text(encoding="utf-8"))
    line = f"N{cut + 1}"
    c = M["cuts"][line][0]
    if how == "tempblur":     # 첫 렌더 전 — 임시 흐림(관문 ④ 가 넣는 칸 자리)
        a = float(c["ss"]) - 0.2
        M.setdefault("blur", {}).setdefault(c["src"], []).append([60, 200, 300, 200, round(a, 3), round(a + LINE_SEC + 0.4, 3)])
    elif how == "blur":       # 렌더 뒤 찾은 로고를 가리는 칸(그 컷 구간에만)
        a = float(c["ss"]) - 0.2
        M.setdefault("blur", {}).setdefault(c["src"], []).append([60, 200, 300, 200, round(a, 3), round(a + LINE_SEC + 0.4, 3)])
    else:                   # 같은 길이의 다른 장면
        c["ss"] = round(float(c["ss"]) + 5.0, 3)
    p.write_text(json.dumps(M, ensure_ascii=False), encoding="utf-8")
    return f"{line} {how}"


def psnr_frames(a: Path, b: Path, w: int = 270, h: int = 480) -> list[float]:
    """프레임마다 PSNR — partial_render_check.frame_psnr 와 같은 자(작은 회색)를 스트림으로(한 편 전체를 메모리에 올리지 않는다, 커밋 여유 1.5GB 에서 MemoryError 실측)."""
    import numpy as np
    pipes = [subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(x), "-vf", f"scale={w}:{h},format=gray", "-f", "rawvideo", "-"], stdout=subprocess.PIPE, stdin=subprocess.DEVNULL) for x in (a, b)]
    out = []
    while True:
        x, y = (p.stdout.read(w * h) for p in pipes)
        if len(x) < w * h or len(y) < w * h:
            break
        m = float(((np.frombuffer(x, np.uint8).astype(np.int16) - np.frombuffer(y, np.uint8).astype(np.int16)) ** 2).mean())
        out.append(99.0 if m < 1e-9 else float(10 * np.log10(255 ** 2 / m)))
    for p in pipes:
        p.stdout.close()
        p.wait()
    return out


def judge(first: Path, part: Path, full: Path, ranges: list, chunks: list) -> dict:
    """구간 교체 = 전체 렌더? 걸린 것은 bad 에."""
    n = PC.frames_of(first)
    h0, h1 = FS.frame_hashes(first), FS.frame_hashes(part)
    inside = {i for a, b in chunks for i in range(a, b)}
    outside = [i for i in range(len(h0)) if i not in inside]
    same_out = sum(1 for i in outside if h0[i] == h1[i])
    changed_frames = {i for a, b in ranges for i in range(a, b)}
    moved_in = sum(1 for i in changed_frames if h0[i] != h1[i])
    p_full = psnr_frames(part, full)
    r_low = [i for i, x in enumerate(p_full) if x < PC.PSNR_SAME]
    p_first = psnr_frames(part, first)
    aud = PC.audio_diff(part, full)
    r = {"frames": [n, PC.frames_of(part), PC.frames_of(full)], "dur": [FS._cap(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", x]).stdout.decode().strip() for x in (first, part, full)],
         "outside_frames": len(outside), "outside_same_md5": same_out, "changed_frames": len(changed_frames), "changed_differ_from_first": moved_in,
         "psnr_vs_full_min": round(min(p_full), 2), "psnr_low_frames": r_low[:60], "psnr_vs_full_in_range_min": round(min(p_full[i] for i in changed_frames), 2) if changed_frames else None,
         "psnr_vs_first_in_range_min": round(min(p_first[i] for i in changed_frames), 2) if changed_frames else None,
         "audio_packets_same_as_first": FS.audio_md5(first) == FS.audio_md5(part), "audio_vs_full": aud}
    bad = []
    if len(set(r["frames"])) != 1:
        bad.append(f"프레임 수 {r['frames']}")
    if same_out != len(outside):
        bad.append(f"구간 밖 프레임 {len(outside) - same_out}개가 첫 완성본과 다르다")
    if r["psnr_vs_full_min"] < PC.PSNR_SAME:
        bad.append(f"전체 렌더와 PSNR 최저 {r['psnr_vs_full_min']} < {PC.PSNR_SAME}")
    if not r["audio_packets_same_as_first"]:
        bad.append("소리 패킷이 첫 완성본과 다르다")
    if abs(aud["lag_samples"]) > 0 or aud["max_diff"] > PC.AUDIO_MAX:
        bad.append(f"전체 렌더와 소리 차이 {aud}")
    if changed_frames and moved_in == 0:
        bad.append("자기 시험 실패: 교체 구간이 첫 완성본과 같다(아무것도 안 바뀜)")
    r["bad"] = bad
    return r


def run_check(base: Path, style: str, how: str, cut: int, n_lines: int = 4, thumb: bool = False, trouble: str = "") -> dict:
    """trouble = 'scenes'(자막 칸 저장소를 비운다 → 바탕 전체로) · 'splice'(끼우기가 실패한다 → 완성본만 통째로). 어느 쪽이든 결과는 같아야 한다."""
    stub_voice()
    lean_encoder()
    timed()
    W0 = base / "w0"
    make_episode(W0, style, n_lines)
    if how.startswith("vmake"):
        change(W0, style, "tempblur", cut)
    if thumb:
        (W0 / "doc" / style / "썸네일.json").write_text(json.dumps({"options": [{"id": "A", "axis": "물건근접", "part": cut, "t": 0.5, "text": [{"lines": ["시험 카드"], "xy": [500, 300], "px": 120}]}]}, ensure_ascii=False), encoding="utf-8")
    t = {}
    t["첫 렌더"], info0, logs0 = _render(W0, style)
    first = base / "first.mp4"
    shutil.copy2(W0 / style / "render" / "final.mp4", first)
    vm = None
    if how.startswith("vmake"):
        vm = vmake_round(W0, style, cut, how == "vmake_fail")
        what = f"가짜 VMake {vm}"
        if how == "vmake_fail":      # 흐림 판으로 완성 — 렌더할 일이 없다: 파일·길이·재료 그대로
            same = FS.frame_hashes(first) == FS.frame_hashes(W0 / style / "render" / "final.mp4")
            return {"changed": what, "sec": t, "source_unchanged": not (W0 / "src" / "s0_orig.mp4").exists() and not (W0 / "src" / "s1_orig.mp4").exists(),
                    "final_unchanged": same, "bad": [] if same and vm["calls"] == 1 and vm["error"] else ["실패했는데 뭔가 바뀌었거나 호출이 1번이 아니다"]}
    else:
        what = change(W0, style, how, cut)
    keep = base / "w0_copy"
    shutil.copytree(W0, keep, copy_function=shutil.copy2)     # 같은 절대 경로에서 두 번 돌리려고 — 첫 렌더 뒤 상태를 보관했다가 전체 렌더 전에 되돌린다
    real_check = FS.check
    if trouble == "scenes":
        shutil.rmtree(W0 / style / "render" / "scene_cache")
    if trouble == "splice":
        def broken(*a, **k):
            raise FS.SpliceFail("시험: 끼운 파일 불신")
        FS.check = broken
    t["구간 교체"], infoP, logsP = _render(W0, style)
    FS.check = real_check
    stages = {"구간 교체": dict(STAGES)}
    part = base / "part.mp4"
    shutil.copy2(W0 / style / "render" / "final.mp4", part)
    if not infoP.get("patched"):
        raise SystemExit("구간 교체가 안 돌았다:\n" + "\n".join(str(x) for x in logsP[-12:]))
    keys, n = FS.keyframes(first)
    ranges = infoP["patched"]["frames"]
    chunks = FS.gop_ranges(keys, n, ranges) if infoP["patched"]["spliced"] else [[0, n]]     # 끼우기 실패 = 통째로 다시 구웠으니 '구간 밖 같음' 은 잴 수 없다
    shutil.rmtree(W0)
    shutil.move(str(keep), str(W0))
    t["전체 렌더"], infoF, logsF = _render(W0, style, full=True)
    stages["전체 렌더"] = dict(STAGES)
    full = base / "full.mp4"
    shutil.copy2(W0 / style / "render" / "final.mp4", full)
    rep = {"changed": what, "sec": t, "stages": stages, "patched": infoP["patched"], "chunks": chunks, "keyframes": keys, **judge(first, part, full, ranges, chunks),
           "log": [x for x in logsP if "구간 교체" in str(x) or "부분 렌더" in str(x)]}
    rep["saved_pct"] = round((1 - t["구간 교체"] / t["전체 렌더"]) * 100, 1)
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--style", default="키치잇판")
    ap.add_argument("--change", default="blur", choices=("blur", "move", "vmake", "vmake_fail"))
    ap.add_argument("--cut", type=int, default=2)
    ap.add_argument("--lines", type=int, default=4)
    ap.add_argument("--thumb", action="store_true", help="바뀐 컷을 고른 썸네일 카드도 있는 편")
    ap.add_argument("--trouble", default="", choices=("", "scenes", "splice"))
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    base = Path(a.folder)
    shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True)
    rep = run_check(base, a.style, a.change, a.cut, a.lines, a.thumb, a.trouble)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    if not a.keep:
        shutil.rmtree(base, ignore_errors=True)
    return 1 if rep["bad"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
