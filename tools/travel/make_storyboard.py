"""여행 숏폼 한 편의 콘티 — 대본 줄마다 [공식 사진(Veo 클립 자리)] + [손님 사진 장면 + 예능 자막] + 말 자막(자막팩).

    py tools/travel/make_storyboard.py <state.json> <reviews.json> <formats.json> <꼴 이름> <출력폴더>

영상은 아직 안 만든다(대본·사진·자막을 먼저 사장님께 보인다). 판단은 전부 모듈 함수:
줄 계획 = 이 파일 plan_lines(오푸스 1회, 검사 포함) / 사진 = travel_scene.scene_photos / 손님 말 = photo_quotes /
예능 자막 = travel_build.variety_lines / 장면 = travel_scene.make_scene / 말 자막 = travel_scene.narration_caption_png.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shopping_shorts import travel_build as tb  # noqa: E402
from shopping_shorts import travel_scene as ts  # noqa: E402

_PLAN_PROMPT = (
    "여행 숏폼 대본 %d줄이다. 줄마다 화면을 계획한다. 우리는 직접 가 본 사람이 아니라 실제 투숙객 후기·사진으로 소개한다.\n\n"
    "대본:\n%s\n\n공식 사진(번호: 설명):\n%s\n\n후기 분석 항목(번호: 범주 · 내용 · 후기 수):\n%s\n\n"
    "줄마다:\n"
    "- official: 그 줄 말과 가장 맞는 공식 사진 번호(Veo 영상 클립이 된다). 줄끼리 겹치지 않게.\n"
    "- keys: 그 줄 주제를 찍은 손님 사진 후기를 찾을 핵심어 2~4개(후기 본문에 실제로 쓰일 말. 예: 짬뽕, 해물짬뽕).\n"
    "- topic: 손님 사진에 또렷하게 보여야 하는 것(예: '룸서비스 짬뽕 그릇', '로비 체크인 대기 줄').\n"
    "- insight: 그 줄 근거가 된 후기 분석 항목 번호(없으면 0).\n"
    "- style: 장면 틀 하나 — %s. 줄끼리 다양하게(같은 틀 연속 금지).\n"
    "- title: 장면 위 손글씨 제목(2~9자, 재치 있게. 지어낸 사실 금지).\n"
    "- emph: 말 자막에서 노란 상자로 강조할 단어(그 줄에 글자 그대로 있는 2~6자).\n"
    "- kind: 'guest'(손님 사진 장면) 또는 마지막 유도 줄이면 'guidebook'(꿀팁노트 미리보기).\n"
    "JSON: {\"lines\": [{\"n\": 1, \"official\": 1, \"keys\": [], \"topic\": \"\", \"insight\": 0, \"style\": \"\", \"title\": \"\", \"emph\": \"\", \"kind\": \"guest\"}]}")


def _insight_items(detail):
    out = []
    for cat, items in (detail.get("review_insights") or {}).items():
        if cat.startswith("_"):
            continue
        for x in items or []:
            out.append(dict(x, cat=cat))
    return out


def plan_lines(lines, judged, items, reviews):
    """줄마다 화면 계획(오푸스 1회) + 검사: 강조어는 그 줄에 글자 그대로 / 핵심어는 사진 후기 3개 이상 / 틀은 있는 것."""
    off = "\n".join("%d: %s" % (j["no"], j.get("desc_ko", "")) for j in judged)
    ins = "\n".join("%d: %s · %s · %s명" % (i + 1, x["cat"], x["item"], x.get("count", "?")) for i, x in enumerate(items))
    body = "\n".join("%d) %s" % (i + 1, t) for i, t in enumerate(lines))
    got = tb.claude_call([], _PLAN_PROMPT % (len(lines), body, off, ins, " / ".join(ts.STYLES)), model="opus")
    plan = sorted(got.get("lines") or [], key=lambda x: int(x.get("n", 0)))
    problems = []
    for i, p in enumerate(plan):
        t = lines[i]
        if p.get("emph") and p["emph"] not in t:
            problems.append("%d줄 강조어 '%s'가 줄에 없음 → 뺌" % (i + 1, p["emph"]))
            p["emph"] = ""
        if p.get("style") not in ts.STYLES:
            p["style"] = list(ts.STYLES)[i % len(ts.STYLES)]
        if p.get("kind") == "guest":
            n = sum(1 for r in reviews if r.get("images") and any(k in r.get("content", "") for k in p.get("keys") or []))
            p["photo_reviews"] = n
            if n < 3:
                problems.append("%d줄 핵심어 %s 사진 후기 %d개뿐" % (i + 1, p.get("keys"), n))
    return plan, problems


def build(state_path, reviews_path, formats_path, fmt, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    st = json.loads(Path(state_path).read_text(encoding="utf-8"))
    reviews = json.loads(Path(reviews_path).read_text(encoding="utf-8"))
    ver = json.loads(Path(formats_path).read_text(encoding="utf-8"))[fmt]["version"]
    lines, detail, judged = ver["lines"], st["detail"], st["judged"]
    items = _insight_items(detail)
    plan_f = out / "plan.json"
    if plan_f.exists():
        plan, problems = json.loads(plan_f.read_text(encoding="utf-8"))
    else:
        plan, problems = plan_lines(lines, judged, items, reviews)
        plan_f.write_text(json.dumps([plan, problems], ensure_ascii=False, indent=1), encoding="utf-8")
    print("계획 문제:", problems or "없음", flush=True)

    # 예능 자막 — 줄마다 근거 항목 하나(원문 구절 그대로 검사는 variety_lines 가 한다)
    ins_idx = [int(p.get("insight") or 0) for p in plan]
    vitems = [items[k - 1] for k in ins_idx if 0 < k <= len(items)]
    var_f = out / "variety.json"
    if var_f.exists():
        vs = json.loads(var_f.read_text(encoding="utf-8"))
    else:
        vs = tb.variety_lines(vitems) if vitems else []
        var_f.write_text(json.dumps(vs, ensure_ascii=False, indent=1), encoding="utf-8")
    by_item = {v["item"]["item"] if isinstance(v.get("item"), dict) else v.get("item"): v for v in vs}

    shots = []
    for i, (t, p) in enumerate(zip(lines, plan)):
        print("%d줄 %s" % (i + 1, t), flush=True)
        jd = next((j for j in judged if j["no"] == int(p.get("official") or 0)), judged[0])
        # 한 줄 = 공식 사진 클립(앞 절반 자막) → 손님 사진 장면(뒤 절반 자막, 맨 아래 띠 — 사진·예능 자막을 덮지 않게)
        from shopping_shorts.video_assemble import simple_caption_split
        ch = simple_caption_split(t, 14)
        half = (len(ch) + 1) // 2
        ta, tb_ = " ".join(ch[:half]), " ".join(ch[half:]) or " ".join(ch)
        em = p.get("emph", "")
        cap = ts.narration_caption_png(ta, out / ("cap_%02d.png" % i), emph=em if em in ta else "")
        cap_b = ts.narration_caption_png(tb_, out / ("capb_%02d.png" % i), emph=em if em in tb_ else "", y_ratio=0.915, scale=0.62)
        a = _overlay(jd["path"], cap, out / ("a_%02d.jpg" % i))
        shot = {"n": i + 1, "line": t, "plan": p, "official": jd, "a": a.name}
        if p.get("kind") == "guidebook":
            pages = sorted(Path(state_path).parent.glob("sl_*.png"))[:4] or sorted(Path(state_path).parent.glob("sl*.png"))[:4]
            sc = ts.make_scene("스크랩북", [{"path": str(x)} for x in pages], p.get("title") or "꿀팁노트", ["", "", "", ""],
                               out / ("b_%02d.jpg" % i), source="후기 4,226개로 정리", seed=i)
        else:
            sel_f = out / ("photos_%02d.json" % i)
            if sel_f.exists():
                sel = json.loads(sel_f.read_text(encoding="utf-8"))
            else:
                sel = ts.scene_photos(reviews, p["keys"], p["topic"], out / "work", want=4)
                sel_f.write_text(json.dumps(sel, ensure_ascii=False, indent=1), encoding="utf-8")
            if not sel:
                # 손님이 찍지 않는 순간(체크인 줄·번호표 — 실측 2026-10-20 0장)은 공식 사진 위에 후기 말풍선으로 —
                # 핵심어가 많이 겹치는 후기 3개, 공감 많은 순
                kw = p.get("keys") or []
                rv = sorted((r for r in reviews if any(k in r.get("content", "") for k in kw)),
                            key=lambda r: (-sum(k in r.get("content", "") for k in kw), -(r.get("likes") or 0)))[:3]
                sel = [{"path": jd["path"], "review": r} for r in rv]
                p["style"] = "후기 말풍선"
                shot["fallback"] = "손님 사진에 '%s'이(가) 보이는 사진이 없어 공식 사진 + 후기 말풍선" % p["topic"]
            quotes = ts.photo_quotes([s["review"] for s in sel], p["keys"], p["topic"])
            k = ins_idx[i]
            v = by_item.get(items[k - 1]["item"]) if 0 < k <= len(items) else None
            sc = ts.make_scene(p["style"], sel, p.get("title", ""), quotes, out / ("b_%02d.jpg" % i),
                               seed=i, variety=v)
            shot.update(quotes=quotes, variety=v, guests=[s["path"] for s in sel])
        b = _overlay(sc, cap_b, out / ("b_%02d.jpg" % i))
        shot["b"] = b.name
        shots.append(shot)
    (out / "shots.json").write_text(json.dumps(shots, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    page = _html(shots, fmt, problems, out)
    print("완료", page)
    return page


def _overlay(base, cap_png, out_path, y_shift=0):
    """사진(공식 사진은 9:16 으로 채워 자르기) 위에 말 자막을 얹는다. y_shift: 장면 아래 예능 자막과 겹치지 않게 말 자막을 올린다."""
    from PIL import Image
    im = ts._cover(Image.open(base).convert("RGB"), 1080, 1920).convert("RGBA")
    cap = Image.open(cap_png)
    if y_shift:
        moved = Image.new("RGBA", cap.size, (0, 0, 0, 0))
        moved.alpha_composite(cap, (0, y_shift)) if y_shift > 0 else moved.alpha_composite(cap.crop((0, -y_shift, 1080, 1920)), (0, 0))
        cap = moved
    im.alpha_composite(cap)
    im.convert("RGB").save(out_path, quality=90)
    return Path(out_path)


def _html(shots, fmt, problems, out):
    e = html.escape
    rows = []
    for s in shots:
        p = s["plan"]
        v = s.get("variety") or {}
        b = ('<img src="%s">' % s["b"]) if s.get("b") else '<div class="miss">%s</div>' % e(s.get("miss", ""))
        q = " · ".join("“%s”" % e(x) for x in s.get("quotes") or [] if x)
        rows.append(
            '<section><div class="n">%d</div><div class="line">%s</div>'
            '<div class="meta">강조 <b>%s</b> · 틀 %s · 손글씨 제목 “%s”%s</div>'
            '<div class="pair"><figure><img src="%s"><figcaption>① 공식 사진 → Veo 영상 클립<br><small>%s</small></figcaption></figure>'
            '<figure>%s<figcaption>② 손님 사진 장면 %s<br><small>%s</small></figcaption></figure></div></section>'
            % (s["n"], e(s["line"]), e(p.get("emph", "")), e(p.get("style", "")), e(p.get("title", "")),
               (' · 예능 자막 “%s” %s' % (e(v.get("punch", "")), e(v.get("react", "")))) if v else "",
               s["a"], e(s["official"].get("desc_ko", "")), b,
               (("(%s명이 같은 말)" % v.get("count")) if v.get("count") else "") + (" · " + e(s["fallback"]) if s.get("fallback") else ""), q))
    doc = """<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>여행 숏폼 콘티</title><style>
:root{--bg:#f6f3ee;--ink:#1d1b18;--sub:#6b655c;--card:#fff;--acc:#ffd400}
@media (prefers-color-scheme:dark){:root{--bg:#171512;--ink:#f1ece4;--sub:#a59d91;--card:#221f1b}}
body{margin:0;background:var(--bg);color:var(--ink);font-family:'Pretendard','Apple SD Gothic Neo','Malgun Gothic',sans-serif}
header{padding:28px 16px 8px;max-width:980px;margin:auto}h1{margin:0 0 6px;font-size:26px}header p{margin:4px 0;color:var(--sub)}
section{max-width:980px;margin:18px auto;padding:18px 16px;background:var(--card);border-radius:18px;position:relative}
.n{position:absolute;left:-6px;top:-10px;background:var(--acc);color:#000;font-weight:900;border-radius:50%%;width:38px;height:38px;display:grid;place-items:center}
.line{font-size:21px;font-weight:800;line-height:1.45;margin:0 0 6px 22px}.meta{color:var(--sub);font-size:14px;margin:0 0 12px 22px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:14px}figure{margin:0}img{width:100%%;border-radius:12px;display:block}
figcaption{font-size:13px;color:var(--sub);margin-top:6px;line-height:1.5}.miss{aspect-ratio:9/16;display:grid;place-items:center;border:2px dashed #c66;border-radius:12px;color:#c66;padding:12px;text-align:center}
.warn{color:#c33}
@media (max-width:600px){.pair{grid-template-columns:1fr 1fr;gap:8px}.line{font-size:17px}}
</style><header><h1>네스트호텔 · %s 숏폼 콘티</h1>
<p>줄마다 ① 공식 사진(나중에 Veo로 움직이는 영상) → ② 실제 투숙객 사진 장면. 말 자막 = 우리 자막팩 '예능 텐션'(노란 상자 = 강조 단어), 장면 아래 = 예능 자막(손님 원문 그대로 + 편집자 한마디).</p>
<p>%s</p></header>%s</html>""" % (e(fmt), ('<span class="warn">계획 검사: ' + e(" / ".join(problems)) + "</span>") if problems else "계획 검사 통과", "".join(rows))
    f = out / "storyboard.html"
    f.write_text(doc, encoding="utf-8")
    return f


if __name__ == "__main__":
    build(*sys.argv[1:6])
