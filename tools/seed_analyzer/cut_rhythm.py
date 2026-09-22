# -*- coding: utf-8 -*-
"""컷 리듬 측정 — 영상(유튜브 ID·URL·로컬 mp4)의 장면 전환을 ffmpeg로 검출해 컷 길이 분포를 잰다 (2026-09-22).

사장님: "짧은 건 너무 정신없고 / 다른 썰 채널들도 조사해 봐". 히트작과 우리 완성본을 **같은 자**로 재는 도구.
  py tools/seed_analyzer/cut_rhythm.py --ids 1EJB0irk2Lw,azDE6caCwjU --names 이븐쇼핑,활용정점 --out docs/x.json
  py tools/seed_analyzer/cut_rhythm.py --files a.mp4,b.mp4
지표: 길이·컷 수·컷 중앙·첫 컷·2초+ 홀드 수·최장 홀드·0.5초 미만 조각 수·앞 5초 컷 수(훅·미끼 속도).
"""
import argparse, json, os, re, subprocess, sys, statistics, tempfile

THRESH = 0.3    # ffmpeg scene 점수 문턱 — 이븐쇼핑 3편·우리 8편 실측에 쓴 값과 같다


def probe_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def cut_times(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-vf", "select=gt(scene\\,%s),showinfo" % THRESH,
                        "-an", "-f", "null", "-"], capture_output=True, text=True)
    return [float(x) for x in re.findall(r"pts_time:([0-9.]+)", r.stderr)]


def measure(path):
    dur = probe_duration(path)
    ts = cut_times(path)
    d = [round(b - a, 2) for a, b in zip([0.0] + ts, ts + [dur])]
    d = [x for x in d if x > 0.04]
    if not d:
        return None
    return {"duration": round(dur, 1), "cuts": len(d), "median": statistics.median(d), "first": d[0],
            "holds2": sum(1 for x in d if x >= 2), "holds3": sum(1 for x in d if x >= 3), "max": max(d),
            "frag": sum(1 for x in d if x < 0.5), "first5s_cuts": sum(1 for t in ts if t <= 5.0), "lens": d}


def download(vid, workdir):
    url = vid if vid.startswith("http") else "https://www.youtube.com/shorts/%s" % vid
    out = os.path.join(workdir, "%s.%%(ext)s" % re.sub(r"[^A-Za-z0-9_-]", "_", vid)[-20:])
    subprocess.run(["yt-dlp", "-q", "--no-warnings", "-f", "bv*[height<=720]+ba/b[height<=720]", "-o", out, url],
                   capture_output=True, text=True)
    base = out.replace(".%(ext)s", "")
    for ext in ("mp4", "webm", "mkv"):
        if os.path.exists(base + "." + ext):
            return base + "." + ext
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="")
    ap.add_argument("--names", default="")
    ap.add_argument("--files", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    ids = [x.strip() for x in a.ids.split(",") if x.strip()]
    names = [x.strip() for x in a.names.split(",") if x.strip()]
    files = [x.strip() for x in a.files.split(",") if x.strip()]
    work = tempfile.mkdtemp(prefix="cutrhythm_")
    rows = []
    for i, vid in enumerate(ids):
        p = download(vid, work)
        name = names[i] if i < len(names) else vid
        if not p:
            print("  %s 다운로드 실패" % name); continue
        m = measure(p)
        if m: rows.append(dict(m, name=name, id=vid))
    for f in files:
        m = measure(f)
        if m: rows.append(dict(m, name=os.path.basename(f), id=f))
    print("%-14s %5s %4s %6s %5s %5s %5s %5s %5s %6s" % ("이름", "길이", "컷수", "컷중앙", "첫컷", "2초+", "3초+", "최장", "조각", "앞5초컷"))
    for r in rows:
        print("%-14s %5.0f %4d %6.1f %5.1f %5d %5d %5.1f %5d %6d" % (r["name"][:12], r["duration"], r["cuts"], r["median"], r["first"],
                                                             r["holds2"], r["holds3"], r["max"], r["frag"], r["first5s_cuts"]))
    if rows:
        print("합계 %d편: 컷 중앙의 중앙 %.1f · 첫 컷 중앙 %.1f · 3초+ 홀드 편당 중앙 %s · 최장 홀드 중앙 %.1f" % (
            len(rows), statistics.median([r["median"] for r in rows]), statistics.median([r["first"] for r in rows]),
            statistics.median([r["holds3"] for r in rows]), statistics.median([r["max"] for r in rows])))
    if a.out:
        json.dump(rows, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
