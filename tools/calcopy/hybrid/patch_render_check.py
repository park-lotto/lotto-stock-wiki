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
    for i, (a, b) in enumerate((("0x224488", "0xdd8822"), ("0x118844", "0xcc2266"))):
        sh("ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"gradients=s=720x1280:r=30:c0={a}:c1={b}:speed=0.05:d=20", "-f", "lavfi", "-i", f"sine=f={500 + i * 200}:d=20",
           "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", src / f"s{i}.mp4")
    d = W / "doc" / style
    d.mkdir(parents=True)
    words = [f"시험 자막 {i + 1}번 줄이에요" for i in range(n_lines)]
    S = {"slug": "patch_check", "title": "구간 교체 시험", "title_lines": ["구간 교체", "시험"], "source_label": "시험", "cps_target": 7.0, "voice": {"voice_id": "tc_test"},
         "lines": [{"id": f"N{i + 1}", "kind": "tts", "tts": words[i] + ".", "caps": [words[i]]} for i in range(n_lines)]}
    M = {"cand_dir": str(src), "cuts": {f"N{i + 1}": [{"src": f"s{i % 2}.mp4", "ss": 1.0 + (i * 3) % 14, "crop": [0, 0, 720, 1280], "no_snap": True}] for i in range(n_lines)}}
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


def change(W: Path, style: str, how: str, cut: int) -> str:
    p = W / "doc" / style / "재료.json"
    M = json.loads(p.read_text(encoding="utf-8"))
    line = f"N{cut + 1}"
    c = M["cuts"][line][0]
    if how == "blur":       # 렌더 뒤 찾은 로고를 가리는 칸(그 컷 구간에만)
        a = float(c["ss"]) - 0.2
        M.setdefault("blur", {}).setdefault(c["src"], []).append([60, 200, 300, 200, round(a, 3), round(a + LINE_SEC + 0.4, 3)])
    else:                   # 같은 길이의 다른 장면
        c["ss"] = round(float(c["ss"]) + 5.0, 3)
    p.write_text(json.dumps(M, ensure_ascii=False), encoding="utf-8")
    return f"{line} {how}"


def judge(first: Path, part: Path, full: Path, ranges: list, chunks: list) -> dict:
    """구간 교체 = 전체 렌더? 걸린 것은 bad 에."""
    n = PC.frames_of(first)
    h0, h1 = FS.frame_hashes(first), FS.frame_hashes(part)
    inside = {i for a, b in chunks for i in range(a, b)}
    outside = [i for i in range(len(h0)) if i not in inside]
    same_out = sum(1 for i in outside if h0[i] == h1[i])
    changed_frames = {i for a, b in ranges for i in range(a, b)}
    moved_in = sum(1 for i in changed_frames if h0[i] != h1[i])
    p_full = PC.frame_psnr(part, full)
    p_first = PC.frame_psnr(part, first)
    aud = PC.audio_diff(part, full)
    r = {"frames": [n, PC.frames_of(part), PC.frames_of(full)], "dur": [FS._cap(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", x]).stdout.decode().strip() for x in (first, part, full)],
         "outside_frames": len(outside), "outside_same_md5": same_out, "changed_frames": len(changed_frames), "changed_differ_from_first": moved_in,
         "psnr_vs_full_min": round(min(p_full), 2), "psnr_vs_full_in_range_min": round(min(p_full[i] for i in changed_frames), 2) if changed_frames else None,
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


def run_check(base: Path, style: str, how: str, cut: int, n_lines: int = 4) -> dict:
    stub_voice()
    lean_encoder()
    timed()
    W0 = base / "w0"
    make_episode(W0, style, n_lines)
    t = {}
    t["첫 렌더"], info0, logs0 = _render(W0, style)
    first = base / "first.mp4"
    shutil.copy2(W0 / style / "render" / "final.mp4", first)
    what = change(W0, style, how, cut)
    keep = base / "w0_copy"
    shutil.copytree(W0, keep, copy_function=shutil.copy2)     # 같은 절대 경로에서 두 번 돌리려고 — 첫 렌더 뒤 상태를 보관했다가 전체 렌더 전에 되돌린다
    t["구간 교체"], infoP, logsP = _render(W0, style)
    stages = {"구간 교체": dict(STAGES)}
    part = base / "part.mp4"
    shutil.copy2(W0 / style / "render" / "final.mp4", part)
    if not infoP.get("patched"):
        raise SystemExit("구간 교체가 안 돌았다:\n" + "\n".join(str(x) for x in logsP[-12:]))
    keys, n = FS.keyframes(first)
    ranges = infoP["patched"]["frames"]
    chunks = FS.gop_ranges(keys, n, ranges)
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
    ap.add_argument("--change", default="blur", choices=("blur", "move"))
    ap.add_argument("--cut", type=int, default=2)
    ap.add_argument("--lines", type=int, default=4)
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    base = Path(a.folder)
    shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True)
    rep = run_check(base, a.style, a.change, a.cut, a.lines)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    if not a.keep:
        shutil.rmtree(base, ignore_errors=True)
    return 1 if rep["bad"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
