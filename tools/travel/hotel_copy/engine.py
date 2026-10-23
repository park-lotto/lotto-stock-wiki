"""숙소 쇼츠 카피 엔진 — 잘된 원본 한 편의 틀 그대로, 숙소만 바꿔 만든다. 지침서: 지침서.md

    py tools/travel/hotel_copy/engine.py new <이름> --ref <원본id> --hotel "<숙소명>" --official URL --trip URL --yeogi URL --agoda URL
         [--insights 후기분석.json] [--brand @계정] [--bgm 곡.mp3]
    py tools/travel/hotel_copy/engine.py run <이름>      # 멈춘 단계부터 순서대로. ⏸ 에서 멈춘다
    py tools/travel/hotel_copy/engine.py ok <이름>       # ⏸ 확인했다 → 다음으로
    py tools/travel/hotel_copy/engine.py status <이름>

단계(순서 고정): ref → collect → sort → facts → script → ⏸대본 확인 → voice → shots → ⏸사진 확인 → clips → render → check → deliver
  (clips = ep.json 에서 'live'(움직임 영어 한 줄)를 단 컷만 AI 영상(Veo) — 불·김·물처럼 살아 있는 몇 컷만. 없으면 그냥 통과)
  (voice 가 shots 앞 — 실제 말 길이를 알아야 줄마다 컷 수를 원본 컷 길이에 맞출 수 있다. 실측: 원본 컷 수를 그대로 쓰니 2.31초 컷)
작업 폴더 = ~/숏템자료/여행/hotel_copy/<이름>/ (사진·소리·영상은 git 에 넣지 않는다)
"""
import argparse
import json
import math
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
STEPS = ["ref", "collect", "sort", "facts", "script", "script_ok", "voice", "shots", "shots_ok", "clips", "render", "check", "deliver"]
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
        f["detail"] = {k: d.get(k) for k in ("name", "grade", "address", "price_from", "rating", "review_count", "facilities", "story_facts")}
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
    rules = "\n".join("- " + x for x in ref.get("script_rules") or [])      # 원본마다 다른 규칙은 refs/<id>.json 이 주인
    return ("잘된 숙소 쇼츠 원본 대본의 틀을 그대로 두고 숙소만 바꿔 쓴다. 원본 이야기 순서: %s. 역할·어미·말 길이를 원본과 같게.\n\n"
            "원본 줄:\n%s\n\n숙소 자료(이 안에 있는 사실만 쓴다. 숫자는 이 자료에 글자 그대로 있는 것만):\n%s\n\n"
            "실제로 있는 사진(종류: 설명) — shot_hints 는 이 목록에 있는 장면으로만 쓴다(없는 장면을 바라면 엉뚱한 사진이 걸린다):\n%s\n\n"
            "이 원본의 규칙:\n%s\n\n공통 규칙: 줄마다 원본 글자 수 ±20%% / "
            "자막 조각은 원본처럼 1~2어절 뜻 덩어리(9자 이하), 이으면 문장과 같아야 한다 / "
            "shot_hints 는 그 컷에 보일 사진을 2~4단어로(예: '로비', '실내 수영장', '바비큐장', '침실'), 그 줄 말과 맞게 / "
            "shot_at = shot_hints 마다 '이 사진이 뜨는 자막 조각 번호'(0부터, 첫 값 0, 커지는 순서, 개수 = shot_hints 수) — 말과 장면이 맞게 "
            "(예: '식혜에' 조각에서 식혜 사진, '촌이랑 캉스라'에서 강아지 사진). 한 사진이 1.5초를 넘지 않게 조각 2~3개마다 바꾼다 / "
            "facts = 그 줄의 근거를 숙소 자료에서 글자 그대로 옮긴 짧은 말 목록(지어낸 줄은 빈 목록) / "
            "point = '잉'(궁금하게 만드는 줄, answer_at = 답이 나오는 줄 번호 0부터) · '와우'(새 사실로 놀라게 하는 줄) · 없으면 빈칸 / "
            "썸네일: %s, hint = 썸네일 사진(%s 류)\n%s\n"
            "JSON: {\"lines\": [{\"role\": \"\", \"text\": \"\", \"chunks\": [\"\"], \"shot_hints\": [\"\"], \"shot_at\": [0], \"facts\": [\"\"], \"point\": \"\", \"answer_at\": null}], \"thumb\": {\"small\": \"\", \"big\": \"\", \"hint\": \"\"}}"
            % (ref.get("story", ""), roles, facts["text"][:9000], inventory, rules, ref.get("thumb_rule", ""), ref.get("thumb_hint", ""),
               ("\n앞 판에서 걸린 것(고쳐라):\n- " + "\n- ".join(fix)) if fix else ""))


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


def _pick_live(ep, k):
    """(판단 주인) 어느 컷을 AI 영상으로 살릴까 — 불·김·물·연기처럼 사진 속에서 저절로 움직이는 것만 k컷까지(사장님 2026-10-23
    '불 피우는 거나 움직임이 있는 생동감 넘치는 것 몇 개만 중간에'). 첫 컷(썸네일 이음)은 뺀다. 이미 live 를 단 컷이 있으면 손대지 않는다."""
    from shopping_shorts import travel_build as tb
    shots = [sh for l in ep["lines"] for sh in l["shots"]]
    if not k or any(sh.get("live") for sh in shots):
        return []
    rows = "\n".join("%d. [%d줄] %s / %s" % (i, li, sh.get("desc", ""), sh.get("hint", ""))
                     for i, (li, sh) in enumerate((li, sh) for li, l in enumerate(ep["lines"]) for sh in l["shots"]) if i)
    got = tb.claude_call([], (
        "숙소 쇼츠 사진 컷 목록이다. 이 중 최대 %d컷을 4초짜리 AI 영상으로 살린다.\n"
        "고르는 기준: 사진 안에 저절로 움직이는 것이 실제로 있는 컷만 — 불꽃·숯불·김·연기·흐르는 물·물보라·찰랑이는 수면. "
        "사람·동물·방·건물만 있는 컷은 고르지 마라(AI 가 사람을 움직이면 어색하다). "
        "난로 유리문·화덕 안쪽처럼 작게 갇힌 불도 고르지 마라(실측 2번: 사우나 난로 불은 4초 내내 거의 안 움직였다) — 탁 트인 화로대·모닥불·캠프파이어는 된다.해당이 없으면 적게 골라도 된다. 줄이 겹치지 않게 흩어 고른다.\n"
        "live = 움직임 영어 한 줄(사진에 있는 것만 움직이고 새 물건·사람을 만들지 않는다, 카메라는 아주 천천히 다가가기). "
        "live_desc = 사진 내용 영어 한 줄.\n예: live 'Orange flames flicker behind the glass door of the wood stove; warm light flickers on the walls; the camera slowly moves forward.'\n\n"
        "컷:\n%s\n\nJSON: {\"pick\": [{\"i\": 0, \"live\": \"\", \"live_desc\": \"\"}]}" % (k, rows)))
    out = []
    for p in (got.get("pick") or [])[:k]:
        i = p.get("i")
        if isinstance(i, int) and 0 < i < len(shots) and p.get("live"):
            shots[i]["live"], shots[i]["live_desc"] = p["live"], p.get("live_desc") or shots[i].get("desc", "")
            out.append(shots[i].get("hint") or Path(shots[i]["file"]).stem)
    return out


def _fit_shot_at(line, words, speed, d, n, max_cut, min_cut=0.0):
    """대본이 준 shot_at(자막 조각 번호 = 그 말에서 사진이 바뀜)을 지키며 컷 수·최장·최단 컷을 맞춘다.
    가장 긴 컷을 가운데 조각에서 한 번 더 나누고(그 컷 힌트의 '다른 각도'), 너무 짧은 컷은 이웃과 합친다
    (실측 2026-10-23 숨은계곡: 조각 '바베큐에' 하나짜리 컷 0.37초 — 원본 최단 0.7초).
    shot_at 이 없거나 틀렸으면 지우고 False(어절 고르게 나누기로)."""
    at, hints, ch = line.get("shot_at"), line["shot_hints"], line["chunks"]
    if not (isinstance(at, list) and len(at) == len(hints) and at and at[0] == 0
            and all(a < b for a, b in zip(at, at[1:])) and at[-1] < len(ch)):
        line.pop("shot_at", None)
        return False
    cs, k = [], 0
    for c in ch:                                       # 조각 시작 시각(어절 시각에서)
        cs.append(words[k]["start"] / speed)
        k += len(c.split())
    end = lambda j: cs[at[j + 1]] if j + 1 < len(at) else d
    while True:
        segs = [(cs[a], end(j), j) for j, a in enumerate(at)]
        a0, b0, j = max(segs, key=lambda s: s[1] - s[0])
        if len(at) >= n and b0 - a0 <= max_cut:
            break
        lo, hi = at[j], at[j + 1] if j + 1 < len(at) else len(ch)
        if hi - lo < 2:                                 # 조각 하나짜리 컷은 더 못 나눈다 — 검사(check)가 길면 잡는다
            break
        mid = min(range(lo + 1, hi), key=lambda q: abs(cs[q] - (a0 + b0) / 2))
        at.insert(j + 1, mid)
        hints.insert(j + 1, hints[j] + " 다른 각도")
    while len(at) > 1:                                  # 짧은 컷 = 앞 컷이나 뒤 컷과 합친다(합친 길이가 짧은 쪽, 최장 안 넘을 때만)
        short = [j for j in range(len(at)) if end(j) - cs[at[j]] < min_cut]
        if not short:
            break
        j = short[0]
        opts = []
        if j > 0:                                       # 이 컷 사진을 빼고 앞 컷을 늘린다
            opts.append((end(j) - cs[at[j - 1]], j))
        if j + 1 < len(at):                             # 뒤 컷 사진을 빼고 이 컷을 늘린다
            opts.append((end(j + 1) - cs[at[j]], j + 1))
        opts = [o for o in opts if o[0] <= max_cut]
        if not opts:
            break
        k = min(opts)[1]
        del at[k], hints[k]
    return True


def s_shots(job, st):
    from tools.travel.hotel_copy import photos
    from tools.travel.hotel_copy import render, check
    ep = load(job / "ep.json")
    ph = load(job / "photos.json")
    m = render.ref_spec(ep["ref"])["measured"]
    target, longest = m["cut_target_s"], max(m["cut_s"])
    for x, line in zip(load(job / "voice.json"), ep["lines"]):      # 줄 길이 ÷ 원본 컷 길이 = 컷 수(모자라면 같은 힌트 다른 각도)
        d = x["dur"] / ep["speed"]
        # 원본 최장 컷을 넘지 않게도 센다(실측: 1.78초 줄에 round(1.48)=1컷 → 원본 최장 1.5초 넘김)
        n = max(len(line["shot_hints"]), round(d / target), math.ceil(d / (longest * 1.1)))
        # 실제 어절 시각으로 잘라 보고 최장 컷이 검사 기준(check.CUT_MAX_K)을 넘으면 한 컷 더(실측: 객실 줄 1.11/1.73 — 어절 경계가 가운데에 없었다)
        starts = [w["start"] / ep["speed"] for w in x["words"]]
        while n < len(starts):
            st_ = render.cut_points(starts, d, n, target)
            if max(b - a for a, b in zip(st_, st_[1:] + [d])) <= longest * check.CUT_MAX_K:
                break
            n += 1
        if _fit_shot_at(line, x["words"], ep["speed"], d, n, longest * check.CUT_MAX_K, min(m["cut_s"]) * check.CUT_MIN_K):
            continue
        while len(line["shot_hints"]) < n:
            line["shot_hints"].insert(-1, line["shot_hints"][-2 if len(line["shot_hints"]) > 1 else 0] + " 다른 각도")
    ref = render.ref_spec(ep["ref"])
    th = photos.pick_vision(ph, ep["lines"], ep["thumb"].get("hint") or ref["thumb_hint"], job,
                            thumb_kinds=ref.get("thumb_kinds"), end_is_thumb=ref.get("end_same_as_thumb", True))
    ep["thumb"].update(th)
    live = _pick_live(ep, ref.get("live_max", 0))
    save(job / "ep.json", ep)
    labels = photos.sheet(ep, job / "shots.jpg")
    if live:
        return "컷 %d개 고름(shots.jpg) · AI 영상 후보 %d컷(%s) — %s" % (len(labels) - 1, len(live), ", ".join(live), ", ".join(labels))
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
    # 읽는 말 = 숫자를 읽기말로(주인 narration_naturalize.normalize_reading — 사장님 2026-10-23 "4개를 사개라고 읽는다").
    # 자막은 대본 글자 그대로 둔다: 어절마다 따로 바꿔, 받아 온 시각을 다시 대본 어절에 묶는다('4개라' → '네 개라' = 2어절 → 1어절)
    from shopping_shorts.narration_naturalize import normalize_reading
    said = [[normalize_reading(w)[0] for w in l.split()] for l in lines]
    save(job / "lines.json", [" ".join(s) for s in said])
    for f in job.glob("tts_*"):
        f.unlink()
    # 한 번에 이어서 합성한다 — 문장마다 따로 만들어 붙이면 문장마다 억양이 처음부터 다시 시작해 '조각을 붙인 것' 같다(사장님 2026-10-23).
    # 줄 나누기는 받아 온 어절 시각으로: 다음 줄 첫 어절 시작에서 자른다(잘라도 이으면 원래 소리 그대로)
    allm = job / "tts_all.mp3"
    if config.ELEVENLABS_API_KEY:
        tts.synthesize_tts(" ".join(" ".join(s) for s in said), str(allm), voice_id=MINA["voice_id"], voice_settings=MINA["voice_settings"],
                           model_id=MINA["model_id"], speed=1.0)
    else:
        _server_tts(job)
    audio_post.finish_line_audio(str(allm), tempo=MINA["tempo"], silence_trim="mid")
    D = float(va._probe_duration(str(allm)))
    words = tt.rescale(tt.words_from_mp3(str(allm)), D, removed=tt.load_removed(str(allm)))
    if not words:
        raise RuntimeError("단어 시각 없음(일레븐 정렬 사이드카 없음)")
    per = [len(p.split()) for s in said for p in s]                     # 대본 어절 하나가 읽는 말 몇 어절인가
    if sum(per) != len(words):
        raise RuntimeError("어절 수가 다르다: 읽는 말 %d / 받아 온 소리 %d" % (sum(per), len(words)))
    tw, k = [], 0                                                       # 읽는 말 시각 → 대본 어절 시각(글자는 대본 것)
    for w, c in zip((w for l in lines for w in l.split()), per):
        tw.append(dict(words[k], word=w, end=words[k + c - 1].get("end")))
        k += c
    words = tw
    counts = [len(l.split()) for l in lines]
    firsts, k = [], 0
    for c in counts:
        firsts.append(k)
        k += c
    bounds = [0.0] + [words[i]["start"] for i in firsts[1:]] + [D]
    out, tot = [], 0.0
    for i, line in enumerate(lines):
        s0, s1 = bounds[i], bounds[i + 1]
        piece = job / ("tts_%d.wav" % i)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(allm), "-ss", "%.4f" % s0, "-to", "%.4f" % s1,
                        "-ar", "44100", "-ac", "1", str(piece)], check=True)
        ws = [dict(w, start=w["start"] - s0, end=(w["end"] - s0) if w.get("end") is not None else None)
              for w in words[firsts[i]:firsts[i] + counts[i]]]
        out.append({"line": line, "mp3": piece.name, "dur": round(s1 - s0, 3), "words": ws})
        tot += s1 - s0
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
        "tts.synthesize_tts(' '.join(L),D+'/tts_all.mp3',voice_id=%r,model_id=%r,speed=1.0,voice_settings=%r)\n"
        % (MINA["voice_id"], MINA["model_id"], MINA["voice_settings"]), encoding="utf-8")
    ssh = ["ssh", "-i", key, "-o", "StrictHostKeyChecking=no", "ubuntu@" + ip]
    subprocess.run(ssh + ["rm -rf /tmp/hotel_copy_tts; mkdir -p /tmp/hotel_copy_tts"], check=True)
    subprocess.run(["scp", "-i", key, "-q", str(job / "lines.json"), str(srv), "ubuntu@%s:/tmp/hotel_copy_tts/" % ip], check=True)
    subprocess.run(ssh + ["cd /home/ubuntu/lotto-stock-wiki && PY=$(ls venv/bin/python .venv/bin/python 2>/dev/null | head -1); set -a; "
                          "[ -f /etc/shopping-shorts.env ] && . /etc/shopping-shorts.env 2>/dev/null; set +a; ${PY:-python3} /tmp/hotel_copy_tts/srv_tts.py"], check=True)
    subprocess.run(["scp", "-i", key, "-q", "ubuntu@%s:/tmp/hotel_copy_tts/tts_*" % ip, str(job) + "/"], check=True)


def s_clips(job, st):
    """'live'(움직임 영어 한 줄)를 단 컷만 Veo 4초 영상으로(사장님 2026-10-23 '불 피우는 거나 움직임이 있는 생동감 넘치는 것 몇 개만 중간에').
    시작 화면 = 렌더와 같은 세로 자르기(render.crop) — 영상 첫 장면이 그 컷 사진 그대로다. 이미 만든 건 다시 안 만든다(돈)."""
    import concurrent.futures as cf
    import cv2
    from shopping_shorts import ai_scene
    from tools.travel.hotel_copy import render
    ep = load(job / "ep.json")
    (job / "clips").mkdir(exist_ok=True)
    # 같은 사진·같은 자르기면 만든 것 그대로(shots 를 다시 돌려도 돈 안 듦). 움직임 글은 _pick_live 가 돌 때마다 조금씩 달라
    # 비교에 넣지 않는다(실측: 넣었더니 같은 계곡 사진을 또 만들었다) — 다른 움직임을 원하면 clips/live_<사진>.mp4 를 지운다
    key = lambda sh: {"cx": sh.get("cx", 0.5)}
    for sh in (s for l in ep["lines"] for s in l["shots"] if s.get("live") and not s.get("clip")):
        out = job / "clips" / ("live_%s.mp4" % Path(sh["file"]).stem)
        old = load(out.with_suffix(".json")) or {}
        if out.exists() and old.get("cx") == key(sh)["cx"]:
            sh["clip"], sh["live"] = str(out), old.get("live", sh["live"])
    todo = [sh for l in ep["lines"] for sh in l["shots"] if sh.get("live") and not (sh.get("clip") and Path(sh["clip"]).exists())]

    def one(k_sh):
        k, sh = k_sh
        png = job / "clips" / ("start_%s.png" % Path(sh["file"]).stem)
        cv2.imencode(".png", render.crop(sh["file"], sh.get("cx", 0.5), (720, 1280)))[1].tofile(str(png))
        out = job / "clips" / ("live_%s.mp4" % Path(sh["file"]).stem)
        prompt = ai_scene.build_travel_prompt("other", sh.get("live_desc", "A real photo of a countryside guesthouse."), 4, motion=sh["live"])
        ai_scene.generate(png, prompt, 4, out)
        save(out.with_suffix(".json"), dict(key(sh), live=sh["live"]))
        return sh, str(out)
    with cf.ThreadPoolExecutor(4) as ex:
        for sh, out in ex.map(one, enumerate(todo)):
            sh["clip"] = out
    save(job / "ep.json", ep)
    n = sum(1 for l in ep["lines"] for sh in l["shots"] if sh.get("clip"))
    return "AI 영상 컷 %d개 새로 만듦 · 전체 %d개" % (len(todo), n)


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


RUN = {"ref": s_ref, "collect": s_collect, "sort": s_sort, "facts": s_facts, "script": s_script, "shots": s_shots, "clips": s_clips,
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
