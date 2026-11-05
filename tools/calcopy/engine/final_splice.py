# -*- coding: utf-8 -*-
"""완성본 구간 끼우기(관제 304, 사장님 11-02 '해당 구간에서 잘못된 거 그 부분만') — 바뀐 프레임이 든 키프레임 묶음만 다시 굽고 나머지는 스트림 복사로 그대로 둔다.
  판단 주인 = 이 파일 하나: 어디부터 어디까지 다시 굽나(gop_ranges) · 끼운 파일이 믿을 만한가(check). render_bench.render 는 부르기만 한다.
  바깥 프레임은 비트 하나 안 바뀐다 · 소리는 옛 완성본 스트림 복사(다시 굽지 않는다) · 길이(프레임 수)가 다르면 실패 = 부른 쪽이 완성본만 통째로 다시 굽는다."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

FPS = 30


class SpliceFail(RuntimeError):
    """끼운 결과를 믿을 수 없다 — 옛 완성본은 그대로다."""


def _cap(cmd: list) -> subprocess.CompletedProcess:
    return subprocess.run([str(c) for c in cmd], capture_output=True, stdin=subprocess.DEVNULL)


def keyframes(f: Path) -> tuple[list[int], int]:
    """(키프레임 번호 목록(표시 순서), 전체 프레임 수)."""
    r = _cap(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts,flags", "-of", "csv=p=0", f])
    rows = []
    for x in r.stdout.decode("ascii", "replace").split():
        p = x.split(",")
        if len(p) >= 2 and p[0].lstrip("-").isdigit():
            rows.append((int(p[0]), "K" in p[1]))
    rows.sort()
    return [i for i, (_, k) in enumerate(rows) if k], len(rows)


def gop_ranges(keys: list[int], n: int, ranges: list) -> list[list[int]]:
    """(판단 주인 — 어디까지 다시 굽나) 바뀐 프레임 구간 → 그 구간을 품는 키프레임 묶음 [a,b)(겹치거나 맞닿으면 합친다). 복사로 이어 붙일 수 있는 자리는 키프레임뿐이다."""
    out: list[list[int]] = []
    for lo, hi in sorted([max(0, int(a)), min(n, int(b))] for a, b in ranges if int(b) > int(a)):
        a = max((k for k in keys if k <= lo), default=0)
        b = min((k for k in keys if k >= hi), default=n)
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def _first_pts(ts: Path) -> float:
    r = _cap(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts_time", "-read_intervals", "%+#1", "-of", "csv=p=0", ts])
    try:
        return float(r.stdout.decode("ascii", "replace").split()[0].strip(","))
    except (IndexError, ValueError):
        raise SpliceFail(f"첫 시각을 못 읽음: {ts}") from None


def _ts(video: Path, dst: Path, at: float) -> Path:
    """구운 묶음 → 갈아 끼울 조각의 첫 시각(at, B프레임 지연까지 포함)에 맞춘 MPEG-TS(복사)."""
    r = _cap(["ffmpeg", "-y", "-v", "error", "-i", video, "-map", "0:v", "-c", "copy", "-bsf:v", "h264_mp4toannexb", "-output_ts_offset", f"{at:.6f}",
              "-muxdelay", "0", "-muxpreload", "0", "-f", "mpegts", dst])
    if r.returncode:
        raise SpliceFail("TS 변환 실패: " + r.stderr.decode("utf-8", "replace")[-300:])
    return dst


def _split(final: Path, at: list[int], work: Path) -> list[Path]:
    """옛 완성본 영상 스트림을 키프레임 at 에서 나눈 조각들(복사 — 다시 굽지 않는다, 시각은 원래 자리 그대로)."""
    pat = work / "seg_%04d.ts"
    r = _cap(["ffmpeg", "-y", "-v", "error", "-i", final, "-map", "0:v", "-c", "copy", "-bsf:v", "h264_mp4toannexb", "-f", "segment", "-segment_format", "mpegts",
              "-muxdelay", "0", "-muxpreload", "0", *(["-segment_frames", ",".join(map(str, at))] if at else []), pat])
    if r.returncode:
        raise SpliceFail("옛 완성본 나누기 실패: " + r.stderr.decode("utf-8", "replace")[-300:])
    return sorted(work.glob("seg_*.ts"))


def frame_hashes(f: Path) -> list[str]:
    """프레임마다 디코드 결과 md5(인코딩이 아니라 그림을 잰다)."""
    r = _cap(["ffmpeg", "-v", "error", "-i", f, "-map", "0:v", "-f", "framemd5", "-"])
    if r.returncode:
        raise SpliceFail("디코드 실패: " + r.stderr.decode("utf-8", "replace")[-300:])
    return [x.split(",")[-1].strip() for x in r.stdout.decode("ascii", "replace").splitlines() if x and not x.startswith("#")]


def audio_md5(f: Path) -> str:
    """소리 스트림 패킷 그대로의 md5(복사가 맞나 재는 자)."""
    r = _cap(["ffmpeg", "-v", "error", "-i", f, "-map", "0:a", "-c", "copy", "-f", "md5", "-"])
    return r.stdout.decode("ascii", "replace").strip().replace("MD5=", "")


def check(old: Path, new: Path, chunks: list, n: int) -> dict:
    """(판단 주인 — 끼운 파일이 믿을 만한가) 프레임 수 · 시간 간격 · 다시 구운 묶음 밖 프레임 md5 · 소리 패킷 md5 · 디코드 오류. 하나라도 어긋나면 SpliceFail."""
    a, b = frame_hashes(old), frame_hashes(new)
    if len(a) != n or len(b) != n:
        raise SpliceFail(f"프레임 수 옛 {len(a)} · 새 {len(b)} · 계획 {n}")
    inside = {i for s, e in chunks for i in range(s, e)}
    bad = [i for i in range(n) if i not in inside and a[i] != b[i]]
    if bad:
        raise SpliceFail(f"다시 굽지 않은 프레임 {len(bad)}개가 달라졌다(첫 {bad[0]})")
    if audio_md5(old) != audio_md5(new):
        raise SpliceFail("소리 스트림이 달라졌다")
    r = _cap(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts,dts,duration", "-of", "csv=p=0", new])
    pts = sorted(int(x.split(",")[0]) for x in r.stdout.decode("ascii", "replace").split() if x.split(",")[0].lstrip("-").isdigit())
    gaps = {q - p for p, q in zip(pts, pts[1:])}
    if len(gaps) > 1:
        raise SpliceFail(f"프레임 간격이 고르지 않다 {sorted(gaps)[:6]}")
    return {"frames": n, "kept": n - len(inside), "redone": len(inside)}


def spec(f: Path) -> str:
    """이어 붙여도 되는 규격 — 복사로 이으면 스트림 머리는 옛 파일 것 하나뿐이라 코덱·프로파일·크기·B프레임이 같아야 한다."""
    r = _cap(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,profile,width,height,pix_fmt,has_b_frames,level", "-of", "csv=p=0", f])
    return r.stdout.decode("ascii", "replace").strip()


def splice(final: Path, chunks: list, make_chunk, work: Path, log=print) -> dict:
    """chunks = gop_ranges 결과 · make_chunk(a, b, 파일) = 그 묶음을 mp4 로 굽는다(같은 인코더). 옛 영상 스트림을 키프레임에서 나눠 묶음 자리만 갈아 끼우고 소리는 옛 파일 복사.
    검사를 통과해야 final 을 바꾼다 — 실패하면 SpliceFail 이고 final 은 그대로."""
    final, work = Path(final), Path(work)
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    keys, n = keyframes(final)
    missing = [x for c in chunks for x in c if x not in keys and x != n]
    if missing:
        raise SpliceFail(f"묶음 경계가 키프레임이 아니다: {missing}")
    at = sorted({x for c in chunks for x in c if 0 < x < n})
    segs = _split(final, at, work)
    edges = [0, *at, n]
    if len(segs) != len(edges) - 1:
        raise SpliceFail(f"나눈 조각 {len(segs)}개 ≠ 경계 {len(edges) - 1}칸")
    head = {a: b for a, b in chunks}
    body = work / "all.ts"
    with open(body, "wb") as w:
        for seg, a in zip(segs, edges):
            src = seg
            if a in head:
                mp4 = work / f"chunk_{a}.mp4"
                make_chunk(a, head[a], mp4)
                if spec(mp4) != spec(final):
                    raise SpliceFail(f"묶음 규격이 다르다: {spec(mp4)} ≠ {spec(final)}")
                src = _ts(mp4, work / f"chunk_{a}.ts", _first_pts(seg))
            with open(src, "rb") as r:
                shutil.copyfileobj(r, w)
    out = work / "out.mp4"
    r = _cap(["ffmpeg", "-y", "-v", "error", "-i", body, "-i", final, "-map", "0:v", "-map", "1:a?", "-c", "copy",
              "-map_metadata", "1", "-movflags", "+faststart", out])
    if r.returncode:
        raise SpliceFail("합치기 실패: " + r.stderr.decode("utf-8", "replace")[-300:])
    rep = check(final, out, chunks, n)
    shutil.move(str(out), str(final))
    shutil.rmtree(work, ignore_errors=True)
    log(f"[구간 교체] 묶음 {chunks} · 다시 구움 {rep['redone']}/{n} 프레임 · 복사 {rep['kept']}")
    return rep
