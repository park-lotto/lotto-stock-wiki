"""카드 충실도 검사 — 제미나이 카드에 적힌 숫자 기준·예시 상품이 강사가 실제로 말한 것인지 유튜브 자막과 대조한다.
자막: yt-dlp 한국어 자동자막(vtt) → subs/<id>.txt. 카드의 filters_and_thresholds 속 숫자, examples 의 item 을 자막에서 찾는다.
(화면에만 보이고 말하지 않은 것은 자막에 없을 수 있다 — '말로 확인됨' 비율이지 거짓 판정이 아니다.)
출력 fidelity.json"""
import glob, json, os, re, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); SUB = os.path.join(HERE, "subs"); os.makedirs(SUB, exist_ok=True)
def subs(vid):
    txt = os.path.join(SUB, vid + ".txt")
    if os.path.exists(txt): return open(txt, encoding="utf-8").read()
    subprocess.run(["py", "-m", "yt_dlp", "--skip-download", "--write-auto-subs", "--write-subs", "--sub-langs", "ko", "--sub-format", "vtt",
                    "-o", os.path.join(SUB, "%(id)s.%(ext)s"), f"https://www.youtube.com/watch?v={vid}"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    vtts = glob.glob(os.path.join(SUB, vid + "*.vtt"))
    if not vtts: return ""
    lines = []
    for l in open(vtts[0], encoding="utf-8"):
        l = re.sub(r"<[^>]+>", "", l).strip()
        if l and "-->" not in l and not l.startswith(("WEBVTT", "Kind:", "Language:")) and (not lines or lines[-1] != l): lines.append(l)
    t = " ".join(lines); open(txt, "w", encoding="utf-8").write(t); return t
NUMW = {"천": "000", "만": "0000"}
def norm(s): return re.sub(r"[\s,]", "", s)
def nums(s):   # "월 검색량 1만 이상" → ['1만'] ; 숫자+단위 덩어리
    return re.findall(r"\d+(?:\.\d+)?\s*(?:만|천|억|%|개|원|회|위|일|주|명)?", s)
def main():
    res, tot = {}, {"num": [0, 0], "ex": [0, 0]}
    for f in sorted(glob.glob(os.path.join(HERE, "cards", "*.json"))):
        c = json.load(open(f, encoding="utf-8"))
        if not c.get("is_lecture"): continue
        vid = c["_video"]["id"]; t = norm(subs(vid))
        if not t: res[vid] = {"subs": False}; continue
        num_ok = num_n = ex_ok = ex_n = 0; miss = []
        for m in c.get("methods", []):
            for th in m.get("filters_and_thresholds") or []:
                for n in nums(th):
                    n2 = norm(n); num_n += 1
                    core = re.match(r"[\d.]+", n2).group()
                    if n2 in t or (len(core) >= 2 and core in t): num_ok += 1
                    else: miss.append(th[:50])
            for e in m.get("examples") or []:
                it = norm(str(e.get("item") or ""))[:6]
                if len(it) >= 2:
                    ex_n += 1
                    if it in t: ex_ok += 1
                    else: miss.append("예:" + str(e.get("item"))[:30])
        res[vid] = {"subs": True, "title": c["_video"]["title"][:40], "num": [num_ok, num_n], "ex": [ex_ok, ex_n], "miss": miss[:8]}
        tot["num"][0] += num_ok; tot["num"][1] += num_n; tot["ex"][0] += ex_ok; tot["ex"][1] += ex_n
        print(f"{vid} 숫자 {num_ok}/{num_n} 예시 {ex_ok}/{ex_n} | {c['_video']['title'][:30]}", flush=True)
    json.dump({"total": tot, "videos": res}, open(os.path.join(HERE, "fidelity.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("자막 없음", sum(1 for v in res.values() if not v["subs"]), "/", len(res))
    print("숫자 기준 자막 확인", tot["num"], "예시 상품 자막 확인", tot["ex"])

if __name__ == "__main__":
    main()
