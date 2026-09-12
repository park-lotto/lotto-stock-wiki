"""cand_meta.json → 분류 카탈로그(JSON + Markdown). 분류는 제목·설명 키워드 규칙 + 라이선스 문구 규칙."""
import json, re, sys, os

meta = json.load(open("cand_meta.json", encoding="utf-8"))
rows = [d for d in meta if d.get("links")]

def cat_of(t, desc):
    s = (t + " " + desc[:400]).lower()
    if re.search(r"효과음|sound effect|sfx", s): return "효과음"
    if re.search(r"트랜지션|transition|화면전환", s): return "전환"
    if re.search(r"자막|subtitle|caption|text anim|타이핑|mogrt", s): return "자막템플릿"
    if re.search(r"밈|짤|meme|troll|reaction", s): return "밈·짤"
    if re.search(r"lut|색보정|color", s): return "LUT·색보정"
    if re.search(r"화살표|arrow|도형|shape|스티커|sticker|frame|테두리|프레임|highlight|marker|check|loading|twinkle|sparkl|bubble|말풍선|icon|아이콘|paper|liquid|splash|border", s): return "도형·스티커·프레임"
    if re.search(r"예능|웃음|빵터|깜짝|효과", s): return "예능효과"
    if re.search(r"구독|subscribe|like|알람", s): return "구독버튼"
    return "기타소스"

def fmt_of(t, desc):
    s = (t + " " + desc[:600]).lower()
    f = []
    if re.search(r"mov|alpha|알파|투명", s): f.append("MOV알파")
    if re.search(r"\bpng\b", s): f.append("PNG")
    if re.search(r"green ?screen|그린스크린|크로마", s): f.append("mp4그린")
    if re.search(r"mogrt|모션그래픽|프리셋|preset|prproj|프리미어", s): f.append("프리미어전용")
    if re.search(r"에펙|after effects|\.aep|\.ffx", s): f.append("AE")
    if re.search(r"다빈치|davinci", s): f.append("DaVinci")
    if re.search(r"파이널컷|final ?cut|fcp", s): f.append("FCP")
    if re.search(r"효과음|sound|mp3|wav", s): f.append("음원")
    if re.search(r"\blut", s): f.append("LUT")
    return f or ["미확인"]

def lic_of(d):
    L = " ".join(d.get("lic_lines") or []) + " " + (d.get("desc") or "")[:800]
    if re.search(r"비상업적 용도로 이용하는 개인에 한해|비상업적 개인|상업용으로만 사용하지|상업적인 이용은 주의|개인용도는", L):
        return "비상업만(상업은 구매/주의)"
    if re.search(r"저작권 표기 없이 상업적|출처 표기 의무 없음|누구나 자유롭게|상업적 사용도 가능|상업적인 용도를 포함|자유롭게 사용가능|사용상의 조건없고|상업적 이용가능, 폰트도 동일|개인용이나 상업용으로", L):
        return "상업OK·표기불요"
    if re.search(r"출처 ?표기(후|만|와)|출처를 남겨|출처표기", L):
        return "상업OK·출처표기"
    if re.search(r"저작권 걱정|저작권에 걸리지 않|저작권 없는|copyright free", L, re.I):
        return "저작권무료(주장)"
    if re.search(r"재배포", L):
        return "재배포금지만 명시"
    return "미확인"

def direct_usable(fmts):
    return any(f in ("MOV알파", "PNG", "mp4그린", "음원") for f in fmts)

out = []
for d in rows:
    desc = d.get("desc") or ""
    c = cat_of(d["title"], desc); f = fmt_of(d["title"], desc); l = lic_of(d)
    out.append({"id": d["id"], "url": d["url"], "title": d["title"], "channel": d["channel"], "views": d.get("views") or 0,
                "upload": d.get("upload"), "category": c, "formats": f, "license": l,
                "direct_usable": direct_usable(f), "links": d["links"][:4], "lic_lines": d.get("lic_lines") or []})
out.sort(key=lambda x: (x["category"], -x["views"]))
json.dump(out, open("catalog.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# Markdown
by = {}
for r in out: by.setdefault(r["category"], []).append(r)
md = ["# 유튜브 무료 효과팩 수집 카탈로그 (2026-09-13, 1차)", "",
      f"수집: yt-dlp 검색 15개 검색어 → 고유 영상 354편 → 팩 배포 후보 178편 중 **다운로드 링크 확인 {len(out)}편**.",
      "라이선스는 **설명란 문구 그대로** 분류한 것이며 법적 확인이 아니다. 실제 사용 전 각 링크의 안내문을 다시 읽는다.",
      "", "| 분류 | 건수 | 직접사용 가능(MOV/PNG/음원) |", "|---|---|---|"]
for c, L in by.items(): md.append(f"| {c} | {len(L)} | {sum(1 for r in L if r['direct_usable'])} |")
md += ["", "직접사용 = 우리 ffmpeg 렌더러에 그대로 얹을 수 있는 형식. 프리미어전용(mogrt·prproj)·AE·DaVinci·FCP는 그 프로그램에서만 쓰거나 캡컷 내보내기 경로로 돌려야 한다.", ""]
for c, L in by.items():
    md += [f"## {c} ({len(L)})", "", "| 조회수 | 제목 | 채널 | 형식 | 라이선스 | 링크 |", "|---|---|---|---|---|---|"]
    for r in L:
        links = " / ".join(f"[{i+1}]({u})" for i, u in enumerate(r["links"][:3]))
        md.append(f"| {r['views']:,} | [{r['title'][:48]}]({r['url']}) | {r['channel']} | {', '.join(r['formats'])} | {r['license']} | {links} |")
    md.append("")
open("catalog.md", "w", encoding="utf-8").write("\n".join(md))
print("catalog rows", len(out))
for c, L in by.items(): print(f"  {c}: {len(L)} (직접 {sum(1 for r in L if r['direct_usable'])})")
from collections import Counter
print(Counter(r["license"] for r in out))
