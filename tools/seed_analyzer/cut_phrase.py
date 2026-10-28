# -*- coding: utf-8 -*-
"""컷 경계가 **어떤 구절 자리**에 오는가 — 히트작의 장면 전환 시각을 자동자막 낱말 시각에 맞춰 센다 (2026-09-23 사장님
"매칭 길이는 이븐쇼핑·노바 내용으로 어떤 구절로 끊어야 하는지 조사가 된 건가").
  py tools/seed_analyzer/cut_phrase.py --ids a,b,c --names x,y,z --out docs/x.json
자리 분류(컷 시각 ±0.25초 안의 낱말 경계 기준):
  문장시작  = 직전 낱말이 종결(~다/~요/~거/~데/~고/~며/…) 또는 신호어 직전
  신호어앞  = 컷 직후 낱말이 심지어·게다가·이게 말도·근데 진짜·충격…
  연결어미뒤 = 직전 낱말이 ~는데/~서/~고/~며/~면/~니까
  낱말중간  = 위 어느 것도 아님(말 도중 컷)
"""
import argparse, json, os, re, subprocess, sys, tempfile, statistics, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cut_rhythm import download, cut_times, probe_duration

SIG = re.compile(r"^(심지어|게다가|거기다|이게|진짜|근데|충격|대박|무엇보다)")
END = re.compile(r"(다|요|거|죠|음|임|함|버림|는데|다고|라고|라는데)[.!?…]*$")
CONN = re.compile(r"(는데|서|고|며|면|니까|다가|더니|지만|라서)[,]*$")


def words_with_time(vid, workdir):
    """yt-dlp 자동자막(vtt) → [(t, word)] — vtt의 <t> 태그 낱말 시각을 쓴다."""
    url = vid if vid.startswith("http") else "https://www.youtube.com/shorts/%s" % vid
    base = os.path.join(workdir, "sub_" + re.sub(r"[^A-Za-z0-9_-]", "_", vid)[-16:])
    subprocess.run(["yt-dlp", "-q", "--no-warnings", "--skip-download", "--write-auto-sub", "--sub-lang", "ko", "--sub-format", "vtt", "-o", base, url],
                   capture_output=True, text=True)
    f = next((os.path.join(workdir, x) for x in os.listdir(workdir) if x.startswith(os.path.basename(base)) and x.endswith(".vtt")), None)
    if not f:
        return []
    t = open(f, encoding="utf-8").read()
    out = []
    for m in re.finditer(r"<(\d\d):(\d\d):(\d\d\.\d+)><c>([^<]+)</c>", t):
        sec = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        w = m.group(4).strip()
        if w and (not out or out[-1][1] != w or sec - out[-1][0] > 0.3):
            out.append((sec, w))
    # 첫 낱말(태그 없이 줄 머리에 오는 것)은 cue 시작 시각으로 보완
    for m in re.finditer(r"(\d\d):(\d\d):(\d\d\.\d+) --> [^\n]+\n(?:[^\n<]*\n)?([^<\n]+?)<", t):
        sec = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        w = m.group(4).strip()
        if w:
            out.append((sec, w))
    return sorted(set(out))


SIG_END = re.compile(r"(포인트는|안 ?되는게|안 ?되는 게|심지어|게다가|거기다|충격적인 건|대박인 건)[.,]*$")


def classify(cut_t, words):
    before = [w for w in words if w[0] < cut_t - 0.05]          # 컷보다 **앞에서 시작한** 낱말만
    after = [w for w in words if w[0] >= cut_t - 0.05]
    if not before or not after:
        return "자막없음"
    prev_w = before[-1][1]
    next_w = after[0][1]
    # 컷 직후 낱말이 컷 시각에서 0.25초 넘게 늦으면 = 말 도중(앞 낱말이 아직 발음 중)
    gap = after[0][0] - cut_t
    if SIG.match(next_w):
        return "신호어앞"
    if SIG_END.search(prev_w):
        return "신호어뒤"
    if gap > 0.35:
        return "낱말중간"
    if END.search(prev_w):
        return "문장끝뒤"
    if CONN.search(prev_w):
        return "연결어미뒤"
    return "낱말사이"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", required=True); ap.add_argument("--names", default=""); ap.add_argument("--out", default="")
    a = ap.parse_args()
    ids = [x.strip() for x in a.ids.split(",") if x.strip()]
    names = [x.strip() for x in a.names.split(",") if x.strip()]
    work = tempfile.mkdtemp(prefix="cutphrase_")
    total = collections.Counter(); rows = []
    for i, vid in enumerate(ids):
        name = names[i] if i < len(names) else vid
        words = words_with_time(vid, work)
        p = download(vid, work)
        if not p or not words:
            print("  %s: %s" % (name, "영상 실패" if not p else "자막 없음")); continue
        ts = cut_times(p)
        c = collections.Counter(classify(t, words) for t in ts)
        total.update(c)
        rows.append({"name": name, "id": vid, "cuts": len(ts), "kinds": dict(c)})
        print("%-14s 컷 %2d | %s" % (name[:12], len(ts), " · ".join("%s %d" % (k, v) for k, v in c.most_common())))
    n = sum(total.values()) or 1
    print("\n합계 컷 %d: %s" % (n, " · ".join("%s %d%%" % (k, 100 * v // n) for k, v in total.most_common())))
    if a.out:
        json.dump({"rows": rows, "total": dict(total)}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
