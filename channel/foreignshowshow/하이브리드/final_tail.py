# -*- coding: utf-8 -*-
"""샥탬 하이브리드 손 단계 final_tail (관제 097, 2026-10-28 — 19·20편) — hybrid.py join 결과를 납품 꼴로:
  ① 소리를 영상 길이에 맞춤(짧으면 apad 무음, 길면 자름 — 98 #174 ①·#177 ⑦ join 영상>소리)
  ② 말 끝(나레 −45dB 마지막 칸) 뒤부터 영상 끝 0.1초 앞까지 afade(배경음악이 마지막 프레임에서 뚝 끊기지 않게 — 98 #178·#179,
     17·18편 끝 −15dB 뚝 끊김 지적) · 끝 여운 ≥0.6초 확인
  ③ alimiter 로 TP ≤ −1.2 · LUFS −14 근처(−14.6~−13.5) · 광고 표식(comment) 유지 → finalize.seal

    PYTHONUTF8=1 py channel/foreignshowshow/하이브리드/final_tail.py <hybrid/final.mp4> <나레 narr_placed.wav> <앞 자른 초> <대본.json>
  → 같은 자리 final.mp4 를 고쳐 쓰고 봉인(옛 판은 final_join.mp4 로 남김)
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.engine import ad_mark, finalize  # noqa: E402

RENDERER = "tools/calcopy/shark/hybrid.py + channel/foreignshowshow/하이브리드/final_tail.py(소리=영상 길이·끝 페이드·TP)"


def vdur(p: Path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True).stdout.strip())


def speech_end(narr: Path) -> float:
    """나레 트랙 10ms RMS 가 −45dB 넘는 마지막 칸 끝(받아쓰기 낱말 끝은 늦게 잡힌다 — 98 #178 ②)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(narr), "-ac", "1", "-ar", "48000", "-f", "f32le", "-"], capture_output=True).stdout
    a = np.frombuffer(raw, np.float32)
    n = 480
    r = [20 * np.log10(np.sqrt(np.mean(a[i:i + n] ** 2)) + 1e-12) for i in range(0, len(a) - n, n)]
    return (max(i for i, v in enumerate(r) if v > -45) + 1) * 0.01


def meas(p: Path):
    e = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(p), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1]), float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)[-1])


def main():
    final, narr, cut, script = Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
    src = final.with_name("final_join.mp4")
    shutil.copy2(final, src)
    vd = vdur(src)
    se = round(cut + speech_end(narr), 3)
    tail = vd - se
    assert tail >= 0.6, f"끝 여운 {tail:.3f} < 0.6"
    st = se + 0.05
    fd = round(vd - st - 0.10, 3)          # 마지막 0.1초는 완전 무음(끝 0.1초 RMS < −60dB)
    I0, tp0 = meas(src)
    gain, res = 0.0, None
    for lim in (0.84, 0.80, 0.76, 0.72, 0.68):
        af = (f"apad,atrim=0:{vd:.3f},asetpts=N/SR/TB,afade=t=out:st={st:.3f}:d={fd:.3f},volume={gain:.2f}dB,"
              f"alimiter=limit={lim}:attack=3:release=40:level=false,aresample=48000")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-map", "0:v", "-map", "0:a", "-c:v", "copy", "-af", af,
                        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "1", "-metadata", f"comment={ad_mark.MARK}",
                        "-movflags", "+faststart", str(final)], check=True, stdin=subprocess.DEVNULL)
        I, tp = meas(final)
        res = {"limit": lim, "gain": gain, "I": I, "TP": tp}
        print(f"limit {lim} gain {gain:+.2f} → I {I} TP {tp} (join I {I0} TP {tp0}) · 영상 {vd:.3f} · 말 끝 {se:.3f}(여운 {tail:.3f}) · 페이드 {st:.3f}+{fd}")
        if I < -14.6:
            gain = round(gain + (-14.0 - I), 2)
        if tp <= -1.2 and -14.6 <= I <= -13.5:
            break
    r = finalize.seal(final, RENDERER, script)
    print("seal:", json.dumps({"speech_end": se, "tail": round(tail, 3), **res}, ensure_ascii=False), json.dumps(r, ensure_ascii=False)[:300])


if __name__ == "__main__":
    main()
