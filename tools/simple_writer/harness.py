# -*- coding: utf-8 -*-
"""단순 필자 하네스 — 지시는 짧게, 가드는 꼭 필요한 셋만 (2026-09-21 사장님: "규칙이 길다고 좋은 게 아니고
가드가 세다고 좋은 게 아니다 / 꼭 필요한 지시와 가드만").

대본 1편 = 모델 1회(가드에 걸리면 +1회, 그 이상은 안 돈다). 길이 가드는 없다.
  실측 근거(2026-09-21 draft_census, 고객 후보 1,639편): 재작성 사유의 70%가 '말 밀도' 하나였고,
  그렇게 돌리고도 절반 넘게 가드 탈락인 채로 나갔다 — 센 가드는 호출만 늘렸다.

가드 셋(전부 코드, 모델 호출 0회):
  ① 첫 줄이 씨앗의 첫 문장인가(훅이 통째로 빠지는 일이 실제로 났다)
  ② 씨앗을 통째로 베꼈나(첫 줄 빼고 6어절 연속 일치가 30% 이상)
  ③ 재료에 없는 숫자가 나왔나(씨앗의 "3만원·수천만 조회"가 그대로 따라온 일이 실제로 났다)

쓰는 법(이 PC — Vertex는 gcloud ADC로 붙는다):
    py tools/simple_writer/harness.py --works 7f7d2393eb0b,667ffd60408e --models gemini-3.6-flash,gemini-3.1-flash-lite
재료는 서버에서 읽기 전용으로 받아온다(tools/simple_writer/dump_materials.py).
"""
import argparse
import html
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
KEY = "C:/Users/TheRose/crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem"
PROJECT = "project-74eaf695-8229-44a1-876"
PRICE = {"gemini-3.6-flash": (0.75, 3.75), "gemini-3.7-flash": (0.75, 3.75), "gemini-3.5-flash": (1.5, 9.0),
         "gemini-3.1-flash-lite": (0.25, 1.5), "gemini-2.5-pro": (1.25, 10.0)}


def _host():
    out = subprocess.run(["nslookup", "shoppingshorts.duckdns.org"], capture_output=True, text=True, errors="replace").stdout
    ips = re.findall(r"Address(?:es)?:\s*([0-9.]+)", out)
    return ips[-1] if ips else "3.35.251.172"


def fetch_materials(works, cid=0):
    host = _host()
    subprocess.run(["scp", "-o", "ConnectTimeout=10", "-i", KEY, os.path.join(HERE, "dump_materials.py"),
                    "ubuntu@%s:/home/ubuntu/patchcheck/dump_materials.py" % host], check=True, capture_output=True)
    r = subprocess.run(["ssh", "-o", "ConnectTimeout=10", "-i", KEY, "ubuntu@%s" % host,
                        "cd /home/ubuntu/lotto-stock-wiki && python3 /home/ubuntu/patchcheck/dump_materials.py --works %s --cid %d 2>/dev/null"
                        % (",".join(works), cid)], capture_output=True)
    txt = r.stdout.decode("utf-8", "replace")
    return json.loads(txt[txt.index("@@JSON@@") + 8:])


def build_prompt(m):
    rows = []
    for vid, cuts in m["videos"].items():
        rows.append("[재료 %s]" % vid)
        rows += ["  - %.1f초 | %s%s" % (c["secs"], c["desc"], ("  <말: %s>" % c["say"]) if c["say"] else "") for c in cuts]
    brief = open(os.path.join(HERE, "brief.txt"), encoding="utf-8").read().strip()
    return "%s\n\n[씨앗]\n%s\n\n[재료 — 영상 %d편]\n%s" % (brief, m["seed_text"], len(m["videos"]), "\n".join(rows))


def _nz(t):
    return re.sub(r"[^\w가-힣]", "", t or "")


def _words(t):
    return re.sub(r"[^\w가-힣\s]", " ", t or "").split()


def _grams(ws, n=6):
    return {" ".join(ws[i:i + n]) for i in range(max(0, len(ws) - n + 1))}


def copy_rate(lines, seed):
    """씨앗을 글자 그대로 옮긴 비율. 첫 문장(훅)은 그대로가 설계라 **글자로** 덜어낸다 — 줄로 덜면 한 줄짜리가 0%가 된다."""
    body = _words(" ".join(lines))
    hook = _words((lines[0] if len(lines) >= 3 else "") or "")
    body = body[len(hook):] if hook and body[:len(hook)] == hook else body
    og, sg = _grams(body), _grams(_words(seed))
    return 100.0 * len(og & sg) / max(1, len(og))


def guards(lines, m):
    """꼭 필요한 셋만. 반환: 어긋난 점 문장 목록."""
    bad = []
    if not lines:
        return ["대본이 비었다"]
    seed = m["seed_text"]
    if not _nz(seed).startswith(_nz(lines[0])[:12]):
        bad.append("첫 줄이 씨앗의 첫 문장이 아니다 — 씨앗 첫 문장을 글자 그대로 첫 줄에 써라")
    # ★한 줄짜리(줄을 안 나눈 덩어리)를 '첫 줄 빼고' 재면 0%가 나와 통째 복사가 통과한다
    #   (2026-09-21 실측: 무료 필자 10건 중 3건). 줄을 못 나눈 것부터 실패로 본다.
    if len(lines) < 3:
        bad.append("줄을 나누지 않았다(%d줄) — 한 줄에 한 칸씩 나눠 써라" % len(lines))
    copy = copy_rate(lines, seed)
    if copy >= 30:
        bad.append("씨앗 문장을 %.0f%% 그대로 옮겼다 — 말버릇만 남기고 나머지는 재료를 보고 새로 써라" % copy)
    mat = " ".join(c["desc"] + " " + c["say"] for cs in m["videos"].values() for c in cs)
    nums = [n for n in re.findall(r"\d+(?:[.,]\d+)?", " ".join(lines[1:])) if n not in mat]
    if nums:
        bad.append("재료에 없는 숫자가 나왔다(%s) — 재료 화면·말에 없는 수치는 빼라" % ", ".join(sorted(set(nums))[:5]))
    return bad


def write_once(client, model, prompt):
    for attempt in range(5):
        try:
            s = time.time()
            r = client.models.generate_content(model=model, contents=prompt)
            u = r.usage_metadata
            lines = [l.strip() for l in (r.text or "").strip().split("\n") if l.strip()]
            return lines, {"sec": time.time() - s, "in": u.prompt_token_count or 0,
                           "out": (u.candidates_token_count or 0) + (getattr(u, "thoughts_token_count", 0) or 0)}
        except Exception as e:      # noqa: BLE001
            if "429" in str(e) and attempt < 4:
                time.sleep(15)
                continue
            return [], {"sec": 0, "in": 0, "out": 0, "error": str(e)[:120]}


def run_one(client, model, m):
    prompt = build_prompt(m)
    lines, u = write_once(client, model, prompt)
    calls, first_bad = 1, guards(lines, m)
    bad = first_bad
    if first_bad:
        l2, u2 = write_once(client, model, prompt + "\n\n[고칠 점] 앞서 쓴 대본이 이렇게 어긋났다:\n- " + "\n- ".join(first_bad))
        calls += 1
        u = {k: u.get(k, 0) + u2.get(k, 0) for k in ("sec", "in", "out")}
        b2 = guards(l2, m)
        if l2 and len(b2) <= len(first_bad):
            lines, bad = l2, b2
    pi, po = PRICE.get(model, (0, 0))
    sg = _grams(_words(m["seed_text"]))
    return {"lines": lines, "calls": calls, "first_bad": first_bad, "bad": bad, "sec": u["sec"],
            "cost": u["in"] * pi / 1e6 + u["out"] * po / 1e6, "prompt_chars": len(prompt),
            "copy": copy_rate(lines, m["seed_text"]), "sg": sg}


def mark(line, sg):
    ws = line.split(); norm = [re.sub(r"[^\w가-힣]", "", w) for w in ws]; hit = [False] * len(ws)
    for i in range(len(ws) - 5):
        if " ".join(norm[i:i + 6]) in sg:
            for k in range(i, i + 6):
                hit[k] = True
    out, i = [], 0
    while i < len(ws):
        j = i
        while j < len(ws) and hit[j] == hit[i]:
            j += 1
        seg = html.escape(" ".join(ws[i:j])); out.append("<mark>%s</mark>" % seg if hit[i] else seg); i = j
    return " ".join(out)


CSS = """:root{--bg:#f6f4ef;--card:#fff;--ink:#1c1b19;--sub:#6b675f;--line:#e2ded4;--seed:#efe9da;--mark:#ffe08a;--ok:#1f6f5c;--bad:#8a1c0c}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:18px/1.8 "Pretendard","Malgun Gothic",sans-serif}
header,main{max-width:1500px;margin:0 auto;padding:0 20px}header{padding-top:28px}h1{font-size:28px;margin:0 0 6px}header p{margin:4px 0;color:var(--sub)}
table{border-collapse:collapse;width:100%;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;margin:14px 0}
th,td{padding:11px 14px;text-align:left;border-bottom:1px solid var(--line)}th{background:#ece7da;font-size:15px}
pre{white-space:pre-wrap;background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 18px;font:15px/1.7 "Malgun Gothic",monospace;margin:8px 0}
section{margin-top:38px}h2{font-size:23px;margin:0;border-left:6px solid var(--ink);padding-left:12px}.kind{color:var(--sub);margin:4px 0 12px 18px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;border-top:6px solid var(--ok)}
.card.fail{border-top-color:var(--bad)}.card h3{margin:0 0 8px;font-size:17px}.card p{margin:0 0 9px}.seed{background:var(--seed);grid-column:1/-1;border-top-color:#b9b3a4}
mark{background:var(--mark);padding:0 2px;border-radius:3px}small{color:var(--sub);font-weight:400}
.meta{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px;padding-top:10px;border-top:1px dashed var(--line);font-size:14px;color:var(--sub)}
.meta span{background:#f1eee6;border-radius:999px;padding:2px 10px}.meta .bad{background:#ffd9d2;color:var(--bad);font-weight:700}.meta .ok{background:#dff3ea;color:var(--ok);font-weight:700}
main{padding-bottom:60px}"""


def render(mats, models, results, out_path):
    rows = ""
    for model in models:
        rs = [results[(m["work"], model)] for m in mats if (m["work"], model) in results]
        n = max(1, len(rs))
        rows += "<tr><td>%s</td><td>%d편</td><td>%d편</td><td>%d편</td><td>%.2f회</td><td>%.0f초</td><td>%.1f%%</td><td>$%.4f</td></tr>" % (
            html.escape(model), len(rs), sum(1 for r in rs if not r["first_bad"]), sum(1 for r in rs if not r["bad"]),
            sum(r["calls"] for r in rs) / n, sorted(r["sec"] for r in rs)[len(rs) // 2] if rs else 0,
            sum(r["copy"] for r in rs) / n, sum(r["cost"] for r in rs) / n)
    secs = ""
    for m in mats:
        cards = '<div class="card seed"><h3>씨앗 원문 <small>%s</small></h3><p>%s</p></div>' % (html.escape(m.get("seed_vid") or ""), html.escape(m["seed_text"]))
        for model in models:
            r = results.get((m["work"], model))
            if not r:
                continue
            body = "".join("<p>%s</p>" % (html.escape(l) if k == 0 else mark(l, r["sg"])) for k, l in enumerate(r["lines"]))
            tags = ('<span class="ok">가드 통과</span>' if not r["bad"] else "".join('<span class="bad">⚠ %s</span>' % html.escape(b.split(" — ")[0]) for b in r["bad"]))
            if r["first_bad"] and not r["bad"]:
                tags += "<span>1회 다시 씀: %s</span>" % html.escape(" / ".join(b.split(" — ")[0] for b in r["first_bad"]))
            cards += '<div class="card %s"><h3>%s</h3>%s<div class="meta">%s<span>모델 %d회</span><span>%.0f초</span><span>$%.4f</span><span>베낌 %.1f%%</span><span>%d줄</span></div></div>' % (
                "fail" if r["bad"] else "", html.escape(model), body, tags, r["calls"], r["sec"], r["cost"], r["copy"], len(r["lines"]))
        secs += '<section><h2>%s</h2><div class="kind">작업 %s · 재료 영상 %d편 · 컷 %d개 · 프롬프트 %s자</div><div class="grid">%s</div></section>' % (
            html.escape(m.get("title") or m["work"]), m["work"], len(m["videos"]), sum(len(c) for c in m["videos"].values()),
            format(results[(m["work"], models[0])]["prompt_chars"], ","), cards)
    brief = html.escape(open(os.path.join(HERE, "brief.txt"), encoding="utf-8").read().strip())
    page = ("<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>단순 필자 하네스</title><style>%s</style></head><body><header><h1>단순 필자 하네스 — 지시 5줄 · 가드 4개</h1>"
            "<p>대본 1편 = 모델 1회(가드에 걸리면 1회만 다시). 길이 가드 없음. 재료 = 라이브 프로그램이 읽는 것과 같은 실제 재료.</p>"
            "<table><tr><th>모델</th><th>대본</th><th>첫 시도에 가드 통과</th><th>최종 가드 통과</th><th>편당 모델 호출</th><th>걸린 시간(중간값)</th><th>씨앗 베낌 평균</th><th>편당 비용</th></tr>%s</table>"
            "<p>가드 = ①첫 줄이 씨앗 첫 문장 ②줄을 나눴나 ③씨앗 통째 베낌 30%% 미만 ④재료에 없는 숫자 없음. <mark>노란 형광</mark> = 씨앗과 6어절 넘게 같은 곳.</p>"
            "<h3 style='margin:18px 0 0'>모델에게 주는 지시 전문</h3><pre>%s</pre></header><main>%s</main></body></html>") % (CSS, rows, brief, secs)
    open(out_path, "w", encoding="utf-8", newline="\n").write(page)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--works", required=True)
    ap.add_argument("--models", default="gemini-3.6-flash,gemini-3.1-flash-lite")
    ap.add_argument("--cid", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(HERE, "..", "..", "..", "..", "out", "단순필자_하네스.html"))
    a = ap.parse_args()
    from google import genai
    client = genai.Client(vertexai=True, project=PROJECT, location="global")
    models = [x.strip() for x in a.models.split(",") if x.strip()]
    mats = fetch_materials([w.strip() for w in a.works.split(",") if w.strip()], a.cid)
    for m in mats:
        if m.get("error"):
            print("재료 실패 %s: %s" % (m["work"], m["error"]))
    mats = [m for m in mats if not m.get("error") and len(m.get("seed_text") or "") >= 40 and m.get("videos")]
    results = {}
    for m in mats:
        for model in models:
            r = run_one(client, model, m)
            results[(m["work"], model)] = r
            print("%s %-22s 호출 %d · %4.0f초 · 베낌 %5.1f%% · %s" % (m["work"], model, r["calls"], r["sec"], r["copy"],
                                                                 "통과" if not r["bad"] else "⚠ " + " | ".join(b.split(" — ")[0] for b in r["bad"])))
    out = os.path.abspath(a.out)
    render(mats, models, results, out)
    print("HTML:", out)


if __name__ == "__main__":
    main()
