"""숙소 쇼츠 카피 엔진 — 잘된 원본 한 편의 틀 그대로, 숙소만 바꿔 만든다. 지침서: 지침서.md

    py tools/travel/hotel_copy/engine.py new <이름> --ref <원본id> --hotel "<숙소명>" --official URL --trip URL --yeogi URL --agoda URL
         [--insights 후기분석.json] [--brand @계정] [--bgm 곡.mp3]
    py tools/travel/hotel_copy/engine.py run <이름>      # 멈춘 단계부터 순서대로. ⏸ 에서 멈춘다
    py tools/travel/hotel_copy/engine.py ok <이름>       # ⏸ 확인했다 → 다음으로
    py tools/travel/hotel_copy/engine.py status <이름>

단계(순서 고정): ref → collect → sort → facts → script → ⏸대본 확인 → voice → shots → ⏸사진 확인 → render → check → deliver
  (voice 가 shots 앞 — 실제 말 길이를 알아야 줄마다 컷 수를 원본 컷 길이에 맞출 수 있다. 실측: 원본 컷 수를 그대로 쓰니 2.31초 컷)
작업 폴더 = ~/숏템자료/여행/hotel_copy/<이름>/ (사진·소리·영상은 git 에 넣지 않는다)
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
JOBS = Path.home() / "숏템자료/여행/hotel_copy"
DRIVE = Path("G:/내 드라이브")
STEPS = ["ref", "collect", "sort", "facts", "script", "script_ok", "voice", "shots", "shots_ok", "render", "check", "deliver"]
WAIT = {"script_ok": "대본을 확인하세요(script_brief.md·ep.json). 고칠 게 없으면 ok",
        "shots_ok": "사진을 확인하세요(shots.jpg). 바꿀 컷은 ep.json 의 file·cx 를 고치고 ok"}
MINA = {"voice_id": "aiUUgjHa4mpHf6UenZuf", "model_id": "eleven_v3", "voice_settings": {"stability": 0.55, "similarity_boost": 0.78, "style": 0.15}, "tempo": 1.35}


def jdir(name):
    return JOBS / name


def load(p, default=None):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def save(p, d):
    Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


# ── 단계 ────────────────────────────────────────────────────────────────────
def s_ref(job, st):
    """원본 틀 = refs/<id>.json(줄판독·실측). 없으면 원본을 받아 0.2초 자막 띠를 만들고 사람이 읽게 멈춘다."""
    spec = HERE / "refs" / (st["ref"] + ".json")
    if spec.exists():
        return "원본 틀 있음: %s" % spec.name
    subprocess.run(["yt-dlp", "-q", "-f", "bv*[height<=1920]+ba/b", "-o", str(job / "ref.%(ext)s"), "https://www.youtube.com/shorts/" + st["ref"]], check=True)
    raise Wait("원본 줄판독 필요 — 지침서 '1. 원본 읽기' 순서로 refs/%s.json 을 만든 뒤 run" % st["ref"])


def s_collect(job, st):
    from tools.travel.hotel_copy import sources
    d = job / "photos"
    d.mkdir(exist_ok=True)
    got, log = [], {}
    for site, url in st["urls"].items():
        if not url:
            continue
        try:
            items = sources.ADAPTERS[site](url, d)
            got += items
            log[site] = len(items)
        except Exception as e:                         # 한 사이트가 막혀도 나머지로 간다 — 단 이유를 남긴다
            log[site] = "실패: %s" % str(e)[:120]
    save(job / "collected.json", got)
    if not got:
        raise RuntimeError("사진을 한 장도 못 받았다: %s" % log)
    return "사이트별 %s · 합계 %d장" % (log, len(got))


def s_sort(job, st):
    from tools.travel.hotel_copy import photos
    got = load(job / "collected.json")
    merged = photos.merge_same(got)
    judged = photos.judge(merged, job)
    save(job / "photos.json", judged)
    by = {}
    for p in judged:
        by[p["kind"]] = by.get(p["kind"], 0) + 1
    return "같은 사진 합침 %d→%d · 판정 %d장 · 종류 %s" % (len(got), len(merged), len(judged), by)


def s_facts(job, st):
    """대본에 쓸 사실 — 여기어때 상세 + 후기 분석(있으면 그 파일, 없으면 기존 주인 함수로 만든다)."""
    from shopping_shorts import travel_source, travel_build as tb
    f = {"hotel": st["hotel"]}
    if st["urls"].get("yeogi"):
        d = travel_source.fetch(st["urls"]["yeogi"])
        f["detail"] = {k: d.get(k) for k in ("name", "grade", "address", "rating", "review_count", "facilities", "story_facts")}
    if st.get("insights"):
        f["insights"] = load(st["insights"])
    elif st["urls"].get("yeogi"):
        pid = travel_source.travel_site(st["urls"]["yeogi"])["id"]
        f["insights"] = tb.review_insights(travel_source.yeogi_reviews(pid))
    f["text"] = json.dumps(f, ensure_ascii=False)
    save(job / "facts.json", f)
    return "사실 자료 %d자" % len(f["text"])


def _script_prompt(ref, facts, fix=None, inventory=""):
    roles = "\n".join("%d. [%s] 규칙: %s / 원본: %s / 원본 자막 조각: %s / 원본 %d자 / 반드시 들어갈 말: %s / 사진 %d장(힌트 예: %s)"
                      % (i + 1, r["role"], r["rule"], r["ref"], " | ".join(r["chunks"]), r["chars"], ", ".join(r["must"]), r["shots"], r["shot_hint"])
                      for i, r in enumerate(ref["roles"]))
    return ("잘된 숙소 쇼츠 원본 대본의 틀을 그대로 두고 숙소만 바꿔 쓴다. 원본은 숙소를 걸어 들어가는 순서로 말한다"
            "(입구 → 안 시설 → '특히' 하이라이트 → '~지만' 반전 → 상황 권유). 역할·어미·말 길이를 원본과 같게.\n\n"
            "원본 줄:\n%s\n\n숙소 자료(이 안에 있는 사실만 쓴다. 숫자는 이 자료에 글자 그대로 있는 것만):\n%s\n\n"
            "실제로 있는 사진(종류: 설명) — shot_hints 는 이 목록에 있는 장면으로만 쓴다(없는 장면을 바라면 엉뚱한 사진이 걸린다):\n%s\n\n"
            "규칙: 줄마다 원본 글자 수 ±20%% / 하이라이트 줄에 이 숙소의 간판 시설 / "
            "훅 = 원본처럼 희소·권위 수식어('손꼽히는'·'상위 1%%'·'한국의 ○○'·후기·평점 같은 자료 근거) + 숙소 종류 — 위치 설명만으로 열지 않는다 / "
            "입구·안 시설 = 원본처럼 공간의 품격·분위기 꾸밈말(화려한·우아하게·탁 트인·통유리) — 편의점·치킨집 같은 생활 정보 나열 금지 / "
            "반전 = '~지만' 뒤에 문턱이 낮아지는 사실(원본: 5성급 안에 있지만 투숙 안 해도 이용) — 유료·불편 같은 단점을 새로 꺼내지 않는다 / "
            "후기에서 불만 수(count)가 칭찬보다 많은 것(예: 조식 '가격 대비 아쉽다' 60 > '맛있다' 48)은 자랑하지 않는다 / "
            "권유 = '<누가·어떤 순간> 싶다면 한 번쯤 ~볼 만하겠죠?' — 원본 길이(24자) 지키기 / "
            "자막 조각은 원본처럼 1~2어절 뜻 덩어리(9자 이하), 이으면 문장과 같아야 한다 / "
            "shot_hints 는 그 컷에 보일 사진을 2~4단어로(예: '로비', '실내 수영장', '드론 조감도 건물', '침대 창밖 바다'), 그 줄 말과 맞게 / "
            "썸네일: small = 작은 줄(숫자 있는 권위·희소, 8자 안팎), big = 큰 줄(숙소 종류 4~5자, 띄어쓰기 없이), hint = 썸네일·끝 컷 사진(드론 조감도 건물 류)\n%s\n"
            "JSON: {\"lines\": [{\"role\": \"\", \"text\": \"\", \"chunks\": [\"\"], \"shot_hints\": [\"\"]}], \"thumb\": {\"small\": \"\", \"big\": \"\", \"hint\": \"\"}}"
            % (roles, facts["text"][:9000], inventory, ("\n앞 판에서 걸린 것(고쳐라):\n- " + "\n- ".join(fix)) if fix else ""))


def s_script(job, st):
    from shopping_shorts import travel_build as tb
    from tools.travel.hotel_copy import render, check
    ref = render.ref_spec(st["ref"])
    facts = load(job / "facts.json")
    if (job / "ep.json").exists() and st.get("script_manual"):
        ep = load(job / "ep.json")
    else:
        ep, fix = None, None
        ph = sorted(load(job / "photos.json", []), key=lambda p: -p["wow"])
        inv = "\n".join("- %s: %s" % (p["kind"], p["desc"]) for p in ph if not p["has_text"])[:6000]
        for _ in range(3):
            got = tb.claude_call([], _script_prompt(ref, facts, fix, inv))
            ep = {"ref": st["ref"], "hotel": st["hotel"], "brand": st["brand"], "bgm": st.get("bgm"), "lines": got["lines"], "thumb": got["thumb"]}
            fix = check.script_issues(ep, ref, facts["text"])
            if not fix:
                break
        save(job / "ep.json", ep)
    issues = check.script_issues(ep, ref, facts["text"])
    brief = ["# 대본 — %s (원본 %s)" % (st["hotel"], st["ref"]), "", "| 역할 | 원본 | 이번 |", "|---|---|---|"]
    brief += ["| %s | %s | %s |" % (r["role"], r["ref"], l["text"]) for r, l in zip(ref["roles"], ep["lines"])]
    brief += ["", "썸네일: %s / %s" % (ep["thumb"]["small"], ep["thumb"]["big"]), "", "검사: " + ("통과" if not issues else "; ".join(issues)), ""]
    (job / "script_brief.md").write_text("\n".join(brief), encoding="utf-8")
    return "대본 %d줄 · 검사 %s" % (len(ep["lines"]), "통과" if not issues else "%d건: %s" % (len(issues), issues))


def s_shots(job, st):
    from tools.travel.hotel_copy import photos
    from tools.travel.hotel_copy import render
    ep = load(job / "ep.json")
    ph = load(job / "photos.json")
    target = render.ref_spec(ep["ref"])["measured"]["cut_target_s"]
    for x, line in zip(load(job / "voice.json"), ep["lines"]):      # 줄 길이 ÷ 원본 컷 길이 = 컷 수(모자라면 같은 힌트 다른 각도)
        n = max(len(line["shot_hints"]), round(x["dur"] / ep["speed"] / target))
        while len(line["shot_hints"]) < n:
            line["shot_hints"].insert(-1, line["shot_hints"][-2 if len(line["shot_hints"]) > 1 else 0] + " 다른 각도")
    th = photos.pick_vision(ph, ep["lines"], ep["thumb"].get("hint") or "드론 조감도 건물 외관", job)
    ep["thumb"].update(th)
    save(job / "ep.json", ep)
    labels = photos.sheet(ep, job / "shots.jpg")
    return "컷 %d개 고름(shots.jpg) — %s" % (len(labels) - 1, ", ".join(labels))


def s_voice(job, st):
    """미나(일레븐) — 이 PC 에 키가 없으면 서버에서 합성해 받아 온다(관제 239 실측 방식). 원본 말 속도에 맞춰 배속."""
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
    from shopping_shorts import config, tts, audio_post, tts_timestamps as tt, video_assemble as va
    from tools.travel.hotel_copy import render
    ep = load(job / "ep.json")
    ref = render.ref_spec(ep["ref"])
    lines = [l["text"] for l in ep["lines"]]
    save(job / "lines.json", lines)
    for f in job.glob("tts_*"):
        f.unlink()
    if config.ELEVENLABS_API_KEY:
        for i, line in enumerate(lines):
            tts.synthesize_tts(line, str(job / ("tts_%d.mp3" % i)), voice_id=MINA["voice_id"], voice_settings=MINA["voice_settings"],
                               model_id=MINA["model_id"], speed=1.0, previous_text=lines[i - 1] if i else None,
                               next_text=lines[i + 1] if i + 1 < len(lines) else None)
    else:
        _server_tts(job)
    out, tot = [], 0.0
    for i, line in enumerate(lines):
        mp3 = job / ("tts_%d.mp3" % i)
        audio_post.finish_line_audio(str(mp3), tempo=MINA["tempo"], silence_trim="mid")
        d = float(va._probe_duration(str(mp3)))
        words = tt.rescale(tt.words_from_mp3(str(mp3)), d, removed=tt.load_removed(str(mp3)))
        if not words:
            raise RuntimeError("%d줄 단어 시각 없음(일레븐 정렬 사이드카 없음)" % (i + 1))
        out.append({"line": line, "mp3": mp3.name, "dur": round(d, 3), "words": words})
        tot += d
    save(job / "voice.json", out)
    m = ref["measured"]
    want = m["chars"] / (m["total_s"] - m["thumb_s"] - 0.3)              # 원본 말 속도(자/초)
    have = sum(len(l.replace(" ", "")) for l in lines) / tot
    ep["speed"] = round(min(1.25, max(1.0, want / have)), 3)
    save(job / "ep.json", ep)
    return "음성 %.2f초 · 원본 속도 %.1f자/초 맞춤 배속 %.3f" % (tot, want, ep["speed"])


def _server_tts(job):
    import socket
    ip = socket.gethostbyname("shoppingshorts.duckdns.org")
    key = "C:/Users/TheRose/crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem"
    srv = job / "srv_tts.py"
    srv.write_text(
        "import json,sys\nsys.path.insert(0,'/home/ubuntu/lotto-stock-wiki')\nfrom shopping_shorts import tts\n"
        "D='/tmp/hotel_copy_tts'\nL=json.load(open(D+'/lines.json',encoding='utf-8'))\n"
        "for i,l in enumerate(L):\n    tts.synthesize_tts(l,D+'/tts_%%d.mp3'%%i,voice_id=%r,model_id=%r,speed=1.0,voice_settings=%r,"
        "previous_text=L[i-1] if i else None,next_text=L[i+1] if i+1<len(L) else None)\n"
        % (MINA["voice_id"], MINA["model_id"], MINA["voice_settings"]), encoding="utf-8")
    ssh = ["ssh", "-i", key, "-o", "StrictHostKeyChecking=no", "ubuntu@" + ip]
    subprocess.run(ssh + ["rm -rf /tmp/hotel_copy_tts; mkdir -p /tmp/hotel_copy_tts"], check=True)
    subprocess.run(["scp", "-i", key, "-q", str(job / "lines.json"), str(srv), "ubuntu@%s:/tmp/hotel_copy_tts/" % ip], check=True)
    subprocess.run(ssh + ["cd /home/ubuntu/lotto-stock-wiki && PY=$(ls venv/bin/python .venv/bin/python 2>/dev/null | head -1); set -a; "
                          "[ -f /etc/shopping-shorts.env ] && . /etc/shopping-shorts.env 2>/dev/null; set +a; ${PY:-python3} /tmp/hotel_copy_tts/srv_tts.py"], check=True)
    subprocess.run(["scp", "-i", key, "-q", "ubuntu@%s:/tmp/hotel_copy_tts/tts_*" % ip, str(job) + "/"], check=True)


def s_render(job, st):
    from tools.travel.hotel_copy import render
    return "완성 %s" % render.render(job)


def s_check(job, st):
    from tools.travel.hotel_copy import render, check
    ep = load(job / "ep.json")
    rep = check.video_report(job, ep, render.ref_spec(ep["ref"]))
    bad = [r["항목"] for r in rep["rows"] if r["통과"] is False]
    lines = ["%s: 우리 %s / 원본 %s %s" % (r["항목"], r["우리"], r["원본"], "" if r["통과"] is None else ("통과" if r["통과"] else "★미달")) for r in rep["rows"]]
    if bad:
        raise RuntimeError("검사 미달 %s\n%s" % (bad, "\n".join(lines)))
    return "\n".join(lines)


def s_deliver(job, st):
    st["version"] = st.get("version", 0) + 1
    name = "%s_%s틀_%d판.mp4" % (st["hotel"].replace(" ", ""), st["ref"], st["version"])
    dests = [Path.home() / "Desktop" / name]
    if DRIVE.exists():
        d = DRIVE / ("숙소쇼츠_" + st["hotel"].replace(" ", ""))
        d.mkdir(exist_ok=True)
        dests.append(d / name)
        shutil.copy(job / "script_brief.md", d / "대본.md")
    for p in dests:
        shutil.copy(job / "out.mp4", p)
    return "전달 %s" % [str(p) for p in dests]


class Wait(Exception):
    pass


RUN = {"ref": s_ref, "collect": s_collect, "sort": s_sort, "facts": s_facts, "script": s_script, "shots": s_shots,
       "voice": s_voice, "render": s_render, "check": s_check, "deliver": s_deliver}


def run(name, start=None):
    job = jdir(name)
    st = load(job / "state.json")
    i = STEPS.index(start) if start else STEPS.index(st["at"])
    while i < len(STEPS):
        step = STEPS[i]
        st["at"] = step
        save(job / "state.json", st)
        if step in WAIT:
            if not st.get("ok_" + step):
                print("⏸ %s — %s" % (step, WAIT[step]))
                return
            i += 1
            continue
        t0 = time.time()
        try:
            msg = RUN[step](job, st)
        except Wait as w:
            print("⏸ %s — %s" % (step, w))
            return
        st.setdefault("log", []).append({"step": step, "s": round(time.time() - t0, 1), "msg": msg})
        save(job / "state.json", st)
        print("[done] %s %.1f초 — %s" % (step, time.time() - t0, msg), flush=True)
        i += 1
    st["at"] = "deliver"
    save(job / "state.json", st)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)      # 어느 단계부터 다시 돌려도 키가 있게(실측: check 만 돌리면 no_groq_key)
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["new", "run", "ok", "status", "redo"])
    ap.add_argument("name")
    ap.add_argument("--ref")
    ap.add_argument("--hotel")
    ap.add_argument("--official")
    ap.add_argument("--trip")
    ap.add_argument("--yeogi")
    ap.add_argument("--agoda")
    ap.add_argument("--insights")
    ap.add_argument("--brand", default="@shortem.stay")
    ap.add_argument("--bgm")
    ap.add_argument("--step", help="redo: 이 단계부터 다시")
    a = ap.parse_args()
    job = jdir(a.name)
    if a.cmd == "new":
        job.mkdir(parents=True, exist_ok=True)
        save(job / "state.json", {"ref": a.ref, "hotel": a.hotel, "brand": a.brand, "bgm": a.bgm, "insights": a.insights, "at": "ref",
                                  "urls": {"official": a.official, "trip": a.trip, "yeogi": a.yeogi, "agoda": a.agoda}})
        print("만듦 %s" % job)
        run(a.name)
    elif a.cmd == "run":
        run(a.name)
    elif a.cmd == "ok":
        st = load(job / "state.json")
        st["ok_" + st["at"]] = True
        save(job / "state.json", st)
        run(a.name)
    elif a.cmd == "redo":
        st = load(job / "state.json")
        for k in [k for k in st if k.startswith("ok_") and STEPS.index(k[3:]) >= STEPS.index(a.step)]:
            st.pop(k)
        save(job / "state.json", st)
        run(a.name, a.step)
    else:
        st = load(job / "state.json")
        print("지금 단계: %s" % st["at"])
        for l in st.get("log", []):
            print(" - %s %.1f초 %s" % (l["step"], l["s"], str(l["msg"])[:200]))


if __name__ == "__main__":
    main()
