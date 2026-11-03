"""장면 필재 음성에서 문장 몇 개만 새 합성본으로 갈아 끼운다(장면 전체 재합성 X → 나머지 대사 시각 보존).

쓰기: py splice_tts.py <작업.json>
작업.json = {"full": public/full 폴더, "align": 정렬 폴더, "snip": 새 합성 폴더(fNN.mp3 + _fNN_00.mp3.align.json),
             "backup": 백업 폴더, "ops": {"12": [[a, b, "f12", "fit"], ...], ...}}
  op = [자를 시작, 자를 끝, 조각 이름 또는 null(무음), "fit" | "shift", (선택) 뒤에 붙일 쉼 초]
   fit   = 새 조각이 자리보다 짧으면 무음으로 채워 장면 길이·뒤 시각 그대로(길면 shift 로 바뀐다고 알린다)
   shift = 새 조각 길이만큼 뒤가 밀린다
  a == b 이면 그 자리에 끼워 넣기(앞에 0.35초 쉼).
결과: full/sNN.mp3 교체, 정렬은 _sNN_00.mp3.align.json 하나로 합쳐 교체(원본 조각은 backup 으로),
      warp.json = 장면별 [옛 시각, 새 시각] 꺾은선(조각 tsx·하이퍼프레임 시각 옮길 때 쓴다).
조각 앞뒤 무음은 첫 글자-0.04초 / 끝 글자+0.10초로 잘라 쓴다. 소리 크기는 원래 자리의 RMS 에 맞춘다.
"""
import glob, json, os, shutil, subprocess, sys
import numpy as np

SR = 44100


def load(p):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.float32).copy()


def save(x, p):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-", "-c:a", "libmp3lame", "-b:a", "192k", p],
                   input=x.astype(np.float32).tobytes(), check=True)


def chars(files):
    out, off = [], 0.0
    for k, p in enumerate(files):
        d = json.load(open(p, encoding="utf-8"))
        if k: out.append([chr(10), off, off])  # 합성 조각(500자) 경계 = 문단 경계
        for c, s, e in zip(d["characters"], d["character_start_times_seconds"], d["character_end_times_seconds"]):
            out.append([c, s + off, e + off])
        off += d["character_end_times_seconds"][-1]
    return out


def rms(x):
    x = x[np.abs(x) > 1e-3]
    return float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0


def main():
    cfg = json.load(open(sys.argv[1], encoding="utf-8"))
    os.makedirs(cfg["backup"], exist_ok=True)
    warp = {}
    for sid, ops in cfg["ops"].items():
        i = int(sid)
        src = os.path.join(cfg["full"], f"s{i:02d}.mp3")
        afiles = sorted(glob.glob(os.path.join(cfg["align"], f"_s{i:02d}_*.mp3.align.json")))
        bk = os.path.join(cfg["backup"], f"s{i:02d}.mp3")
        if not os.path.exists(bk):  # 두 번 돌려도 원본에서 다시 만든다
            shutil.copy(src, bk)
            for p in afiles: shutil.copy(p, os.path.join(cfg["backup"], os.path.basename(p)))
        x = load(bk)
        ch = chars(sorted(glob.glob(os.path.join(cfg["backup"], f"_s{i:02d}_*.mp3.align.json"))))
        segs, nch, cur, knots, t_new = [], [], 0.0, [[0.0, 0.0]], 0.0
        for op in sorted(ops, key=lambda o: o[0]):
            a, b, name, mode = op[:4]; pad = op[4] if len(op) > 4 else 0.0
            # 앞부분 그대로
            segs.append(x[int(cur * SR):int(a * SR)]); nch += [[c, s - cur + t_new, e - cur + t_new] for c, s, e in ch if cur <= s < a]
            t_new += a - cur
            knots.append([a, t_new])
            if a == b and name:
                gap = np.zeros(int(0.35 * SR), np.float32); segs.append(gap); t_new += 0.35
            if name:
                y = load(os.path.join(cfg["snip"], name + ".mp3"))
                sc = chars(sorted(glob.glob(os.path.join(cfg["snip"], f"_{name}_*.mp3.align.json"))))
                s0 = max(0.0, next(s for c, s, e in sc if c.strip()) - 0.04)
                s1 = min(len(y) / SR, max(e for c, s, e in sc) + 0.10)
                y = y[int(s0 * SR):int(s1 * SR)]
                ref = rms(x[int(a * SR):int(b * SR)]) if b > a else rms(x[int(max(0, a - 3) * SR):int(a * SR)])
                if ref and rms(y): y = y * (ref / rms(y))
                NL = chr(10)  # 자막이 앞뒤 문장과 붙지 않게 줄 끊기
                nch += [[NL, t_new, t_new]] + [[c, s - s0 + t_new, e - s0 + t_new] for c, s, e in sc]
                nch += [[NL, t_new + len(y) / SR, t_new + len(y) / SR]]
                if pad: y = np.concatenate([y, np.zeros(int(pad * SR), np.float32)])
            else:
                y = np.zeros(0, np.float32)
            L = len(y) / SR
            if mode == "fit" and L <= (b - a):
                y = np.concatenate([y, np.zeros(int((b - a) * SR) - len(y), np.float32)]); L = b - a
            elif mode == "fit":
                print(f"  s{i:02d} {a}-{b}: 새 조각 {L:.2f}s > 자리 {b-a:.2f}s → 뒤가 {L-(b-a):+.2f}s 밀림")
            segs.append(y); t_new += L; cur = b
            knots.append([b, t_new])
        segs.append(x[int(cur * SR):]); nch += [[c, s - cur + t_new, e - cur + t_new] for c, s, e in ch if s >= cur]
        knots.append([len(x) / SR, t_new + len(x) / SR - cur])
        out = np.concatenate(segs)
        save(out, src)
        for p in afiles: os.remove(p)
        json.dump({"characters": [c for c, _, _ in nch], "character_start_times_seconds": [round(s, 3) for _, s, _ in nch],
                   "character_end_times_seconds": [round(e, 3) for _, _, e in nch]},
                  open(os.path.join(cfg["align"], f"_s{i:02d}_00.mp3.align.json"), "w", encoding="utf-8"), ensure_ascii=False)
        warp[sid] = [[round(o, 3), round(n, 3)] for o, n in knots]
        print(f"s{i:02d}: {len(x)/SR:.2f}s → {len(out)/SR:.2f}s  꺾은선 {warp[sid]}")
    wp = os.path.join(cfg["full"], "..", "warp1030.json")
    old = json.load(open(wp, encoding="utf-8")) if os.path.exists(wp) else {}
    old.update(warp); json.dump(old, open(wp, "w", encoding="utf-8"), indent=1)


main()
