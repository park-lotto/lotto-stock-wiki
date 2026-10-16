# -*- coding: utf-8 -*-
"""핫템리포트 꼴 소리 — 나레 사이 '원음 리액션 구간' + 원음 바탕(덕킹) (관제 097, 2026-10-16).

원본 OE-11wb7vdY: 나레 0~5.0 → 원음 리액션 5.0~10.4("Oh, I love it!"·"아!!!"·웃음) → 나레 10.4~12.5 →
원음 12.5~20.0("JARVIS, close helmet."·기계음·"It's so cool!") → 나레 20.0~32.1 → 원음 32.3~34.0.
나레가 멈춘 구간은 원음이 덕킹 없이 그대로 들린다(뜯기 2판 audio.composition: 원음 깔림 True·덕킹 3.93dB).

narr_video.py 는 고치지 않는다(주인 다름). 두 단계로 감싼다:
  1) gap_tts(tts, 문장들, gaps) — 타입캐스트 한 파일(한 번 합성)을 문장 경계 쉼에서 갈라 그 자리에 무음 gap 초를 끼운다
     → narr_gapped.wav. narr_video 에 이 파일을 tts 로 넘기면 자막·컷 시각이 무음을 건너뛰어 잡힌다(time_steps = silencedetect).
  2) add_source_bed(final.mp4, timeline.json, 재료.json, narr_gapped.wav, volume, duck_db) — narr_video 가 만든 완성본(나레+BGM)
     위에 원음 한 줄을 깐다. 원음 한 줄·덕킹은 shopping_shorts.video_assemble.source_audio_bed(mix=False) 하나를 부른다
     (렌더·캡컷과 같은 함수 — 판단 두 벌 금지). 나레가 없는 gap 구간은 덕킹이 안 걸려 원음이 그대로 난다.
결과물 검사: measure(final) — 구간별 LUFS·RMS(dB)를 표로(원본과 같은 자로 잰다).

    PYTHONUTF8=1 py tools/calcopy/hottem_audio.py gap <tts> <대본.json> <out.wav> --gaps "0:5.0,1:6.5,end:1.5"
    PYTHONUTF8=1 py tools/calcopy/hottem_audio.py bed <final.mp4> <timeline.json> <재료.json> <narr_gapped.wav> <out.mp4> [--volume 0.9 --duck-db 8]
    PYTHONUTF8=1 py tools/calcopy/hottem_audio.py measure <mp4> --spans "0:5,5:10.4,…"
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shopping_shorts import video_assemble as va  # noqa: E402

SR = va.NARR_SR


def _dur(p) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True).stdout.strip())


def _silences(audio, noise="-38dB", d=0.12) -> list[tuple[float, float]]:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(audio), "-af", f"silencedetect=noise={noise}:d={d}", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r)]
    return list(zip(st, en))


def sentence_breaks(audio, sentences: list[str]) -> list[float]:
    """문장 k 끝의 쉼 가운데 시각(k=0..n-2). 글자 수 비례 예상 시각에 가장 가까운 쉼(0.12초 이상)을 고른다.
    같은 쉼을 두 번 고르면 실패로 멈춘다(조용히 어긋나지 않게)."""
    dur = _dur(audio)
    sil = [(a, b) for a, b in _silences(audio) if a > 0.05 and b < dur - 0.05]
    lens = [len(s.replace(" ", "")) for s in sentences]
    tot = sum(lens)
    out, used, c = [], set(), 0
    for k in range(len(sentences) - 1):
        c += lens[k]
        exp = dur * c / tot
        j = min(range(len(sil)), key=lambda i: abs((sil[i][0] + sil[i][1]) / 2 - exp))
        if j in used:
            raise SystemExit(f"문장 {k} 끝 쉼을 못 가름(예상 {exp:.2f}초, 이미 쓴 쉼) — 쉼 목록 {sil}")
        used.add(j)
        out.append(round((sil[j][0] + sil[j][1]) / 2, 3))
    return out


def gap_tts(tts, sentences: list[str], gaps: dict, out_wav) -> dict:
    """gaps = {문장번호(그 문장 뒤): 초, 'end': 초}. 반환 = {"breaks": [...], "inserted": [(원래 시각, 새 시작, 길이)], "dur"}."""
    br = sentence_breaks(tts, sentences)
    cuts = sorted((br[int(k)], float(v)) for k, v in gaps.items() if k != "end")
    ins, fc, labels, t0, shift = [], [], [], 0.0, 0.0
    for i, (t, g) in enumerate(cuts):
        fc.append(f"[0:a]atrim={t0:.3f}:{t:.3f},asetpts=N/SR/TB,aresample={SR},aformat=channel_layouts=mono[p{i}]")
        fc.append(f"anullsrc=r={SR}:cl=mono,atrim=0:{g:.3f}[g{i}]")
        labels += [f"[p{i}]", f"[g{i}]"]
        ins.append((t, round(t + shift, 3), g))
        shift += g
        t0 = t
    fc.append(f"[0:a]atrim={t0:.3f},asetpts=N/SR/TB,aresample={SR},aformat=channel_layouts=mono[pz]")
    labels.append("[pz]")
    if gaps.get("end"):
        fc.append(f"anullsrc=r={SR}:cl=mono,atrim=0:{float(gaps['end']):.3f}[ge]")
        labels.append("[ge]")
    fc.append("".join(labels) + f"concat=n={len(labels)}:v=0:a=1[a]")
    va._run_ffmpeg(["ffmpeg", "-y", "-i", str(tts), "-filter_complex", ";".join(fc), "-map", "[a]", "-c:a", "pcm_s16le", "-ar", str(SR), str(out_wav)])
    return {"breaks": br, "inserted": ins, "dur": round(_dur(out_wav), 3), "src_dur": round(_dur(tts), 3)}


def cut_plan_from(timeline: dict, M: dict) -> tuple[list, dict, list]:
    """narr_video timeline.json(shots=[(a,b)]) + 재료.json → source_audio_track 의 (cut_plan, source_video_paths, beat_frames).
    칸 하나(idx 0)에 컷마다 소스 [ss, ss+길이] 를 배속 1로 — narr_video.shot_clip 이 화면에 쓴 바로 그 구간."""
    base = Path(M["cand_dir"])
    clips, paths, tot = [], {}, 0
    for k, (a, b) in enumerate(timeline["shots"]):
        sh = M["shots"][k]
        nfr = int(round(b * 30)) - int(round(a * 30))
        vid = f"s{k}"
        paths[vid] = str(base / sh["src"])
        mute = sh.get("kind") == "짤" or sh.get("mute")
        clips.append({"video_id": vid if not mute else "__mute__", "start": float(sh.get("ss", 0)), "c_src": (b - a), "play_out": (b - a), "cfr": nfr})
        tot += nfr
    return [{"idx": 0, "clips": clips}], paths, [(0, tot)]


def add_source_bed(final_mp4, timeline_json, materials_json, narr_wav, out_mp4, volume=0.9, duck_db=8.0, work=None) -> dict:
    T = json.loads(Path(timeline_json).read_text(encoding="utf-8"))
    M = json.loads(Path(materials_json).read_text(encoding="utf-8"))
    work = Path(work or Path(out_mp4).with_suffix("")).resolve()
    work.mkdir(parents=True, exist_ok=True)
    plan, paths, frames = cut_plan_from(T, M)
    ducked = va.source_audio_bed(plan, paths, frames, str(narr_wav), {"volume": volume, "duck_db": duck_db}, work, mix=False)
    # ★채널 배치는 완성본을 따른다 — narr_video 완성본은 모노(나레 mp3)라 stereo 로 올리면 채널마다 -3dB(mix_narration_bed 와 같은 함정)
    lay = "stereo" if va._audio_channels(final_mp4) >= 2 else "mono"
    fc = (f"[0:a]aresample=48000,aformat=channel_layouts={lay}[m];[1:a]aresample=48000,aformat=channel_layouts={lay}[s];"
          "[m][s]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.89:level=false[a]")
    va._run_ffmpeg(["ffmpeg", "-y", "-i", str(final_mp4), "-i", str(ducked), "-filter_complex", fc, "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(out_mp4)])
    return {"ducked": str(ducked), "out": str(out_mp4), "volume": volume, "duck_db": duck_db}


def measure(media, spans: list[tuple[float, float]]) -> list[dict]:
    """구간별 소리 크기 — ebur128 통합 LUFS + RMS dB(astats). 원본과 우리 완성본을 같은 자로 잰다."""
    out = []
    for a, b in spans:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(media), "-vn",
                            "-af", "ebur128=peak=true,astats=measure_overall=RMS_level:measure_perchannel=none", "-f", "null", "-"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
        I = re.findall(r"I:\s+(-?[\d.]+) LUFS", r)
        rms = re.findall(r"RMS level dB:\s+(-?[\d.inf]+)", r)
        out.append({"span": [a, b], "lufs_I": float(I[-1]) if I else None, "rms_db": rms[-1] if rms else None})
    return out


def _spans(s: str) -> list[tuple[float, float]]:
    return [tuple(map(float, x.split(":"))) for x in s.split(",") if x.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gap"); g.add_argument("tts"); g.add_argument("script"); g.add_argument("out"); g.add_argument("--gaps", required=True)
    b = sub.add_parser("bed"); [b.add_argument(x) for x in ("final", "timeline", "materials", "narr", "out")]
    b.add_argument("--volume", type=float, default=0.9); b.add_argument("--duck-db", type=float, default=8.0)
    m = sub.add_parser("measure"); m.add_argument("media"); m.add_argument("--spans", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "gap":
        S = json.loads(Path(a.script).read_text(encoding="utf-8"))
        sents = [l["text"] for l in S["final"]["lines"]]
        gaps = {k: float(v) for k, v in (x.split(":") for x in a.gaps.split(","))}
        res = gap_tts(a.tts, sents, gaps, a.out)
    elif a.cmd == "bed":
        res = add_source_bed(a.final, a.timeline, a.materials, a.narr, a.out, a.volume, a.duck_db)
    else:
        res = measure(a.media, _spans(a.spans))
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
