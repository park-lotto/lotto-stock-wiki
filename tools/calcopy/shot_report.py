# -*- coding: utf-8 -*-
"""shot_kinds.json → 컷 종류 집계 + 컷별 가운데 프레임 시트(자막+그림이 같이 보이게).
사용: PYTHONUTF8=1 py shot_report.py <shot_kinds.json> <mp4 폴더> [시트 만들 영상 id …]
종류 판정(움직임 = 이웃 프레임 차이 중앙값, p90 = 같은 값의 90%점):
  멈춘 사진     : 중앙 < 0.3
  사진+느린 확대 : 0.3 ≤ 중앙 < 3.5 이고 p90 ≤ 중앙×1.3  (차이가 처음부터 끝까지 고르다 = 일정한 확대·이동)
  영상          : 그 밖
★'사진+느린 확대'는 느리게 움직이는 실제 영상과 섞일 수 있다 — 시트를 눈으로 대조할 것."""
import json, os, subprocess, sys, collections as co, statistics as st

rows = json.load(open(sys.argv[1], encoding="utf-8")); d = sys.argv[2]


def kind(r):
    if r["shot"] == 0:
        return "훅 카드"
    if r["motion"] < 0.3:
        return "멈춘 사진"
    if r["motion"] < 3.5 and r["motion_p90"] <= r["motion"] * 1.3:
        return "사진+느린 확대"
    return "영상"


by = co.defaultdict(list)
for r in rows:
    r["kind"] = kind(r); by[r["vid"]].append(r)
tot = co.Counter(); sec = co.Counter()
for vid, rs in by.items():
    c = co.Counter(r["kind"] for r in rs)
    for r in rs:
        tot[r["kind"]] += 1; sec[r["kind"]] += r["sec"]
    print(vid, dict(c))
body = [r for r in rows if r["shot"] > 0]
print("\n전체 컷:", dict(tot)); print("초 합계:", {k: round(v, 1) for k, v in sec.items()})
print("컷 길이 중앙(종류별):", {k: st.median([r["sec"] for r in body if r["kind"] == k]) for k in tot if k != "훅 카드"})
box = co.Counter((r["w"], r["h"], r["box_x"][0], r["box_y"][0]) for r in body)
print("그림 상자 (w,h,x,y) 빈도:", box.most_common(6))
print("등장: 컷 직후 0~1프레임에 자리 잡은 컷", sum(1 for r in body if r["settle_frames"] <= 1), "/", len(body))
for vid in sys.argv[3:]:
    rs = by[vid]; parts = []
    for r in rs:
        out = os.path.join(os.path.dirname(sys.argv[1]), f"_s_{vid}_{r['shot']:02d}.jpg")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(r["t0"] + r["sec"] * 0.6), "-i", os.path.join(d, vid + ".mp4"), "-frames:v", "1",
                        "-vf", "crop=1080:1260:0:300,scale=360:420", out], check=True)
        parts.append(out)
    ins = sum((["-i", p] for p in parts), [])
    cols = 6; n = len(parts)
    lay = "|".join(f"{(i % cols) * 360}_{(i // cols) * 420}" for i in range(n))
    sheet = os.path.join(os.path.dirname(sys.argv[1]), f"shots_{vid}.jpg")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", f"xstack=inputs={n}:layout={lay}:fill=black", "-frames:v", "1", "-update", "1", sheet], check=True)
    for p in parts:
        os.remove(p)
    print("시트", sheet, " ".join(f"#{r['shot']}:{r['kind']}" for r in rs))
