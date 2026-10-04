"""에펙 기본 글자 프리셋 견본(P001~)을 폴더별로 보여주는 페이지를 만든다 (관제 112).

입력: D:\\ae_fx_work\\presets\\P###.mp4 + presets_manifest.txt(build_presets.jsx 가 씀)
출력: D:\\숏템\\30_재료\\에펙효과견본\\프리셋\\index.html (+ mp4 복사)
영상은 화면에 들어올 때만 재생한다(300개를 한꺼번에 틀면 브라우저가 멈춘다).
사용: py tools/ae_fx/make_presets_page.py
"""
import datetime
import html
import shutil
import sys
from pathlib import Path

WORK = Path(r"D:\ae_fx_work")
DEST = Path(r"D:\숏템\30_재료\에펙효과견본\프리셋")
KO = {"3D Text": "3D 글자", "Animate In": "등장", "Animate Out": "퇴장", "Blurs": "흐림", "Curves and Spins": "곡선·회전",
      "Expressions": "수식", "Fill and Stroke": "색·테두리", "Graphical": "도형 결합", "Lights and Optical": "빛",
      "Mechanical": "기계적 움직임", "Miscellaneous": "기타", "Multi-Line": "여러 줄", "Number Counters": "숫자 카운터",
      "Organic": "자연스러운 움직임", "Paths": "경로 따라가기", "Rotation": "회전", "Scale": "크기", "Tracking": "자간"}
ORDER = ["Animate In", "Animate Out", "Blurs", "Scale", "Rotation", "Tracking", "Organic", "Mechanical", "Curves and Spins",
         "Multi-Line", "Miscellaneous", "Fill and Stroke", "Lights and Optical", "Graphical", "Number Counters", "Expressions",
         "3D Text", "Paths"]

PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>에펙 글자 프리셋 견본</title>
<style>
:root{{--bg:#101114;--card:#1a1c21;--line:#2b2e36;--ink:#f2f3f5;--sub:#9aa0ab;--warn:#ffb14a}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 "Pretendard","Malgun Gothic",sans-serif}}
header{{padding:28px 24px 8px;max-width:1700px;margin:0 auto}}h1{{margin:0 0 6px;font-size:26px}}header p{{margin:0;color:var(--sub)}}
nav{{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 24px;display:flex;gap:8px;flex-wrap:wrap;z-index:5}}
nav a{{color:var(--ink);text-decoration:none;font-size:13px;padding:4px 10px;border:1px solid var(--line);border-radius:99px}}
nav a:hover{{background:var(--card)}}
section{{max-width:1700px;margin:0 auto;padding:22px 24px 6px;scroll-margin-top:60px}}h2{{margin:0;font-size:20px}}
h2 small{{color:var(--sub);font-weight:400;font-size:14px;margin-left:8px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:12px;margin-top:12px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}}
.card video{{display:block;width:100%;aspect-ratio:9/16;background:#000;cursor:pointer}}
.card div{{padding:8px 10px 10px;font-size:13px}}.card b{{display:block}}.id{{color:var(--sub);font-size:12px;margin-right:6px}}
.note{{color:var(--warn);font-size:12px}}footer{{max-width:1700px;margin:0 auto;padding:20px 24px 40px;color:var(--sub);font-size:13px}}
</style></head><body>
<header><h1>에펙 기본 글자 프리셋 견본 — {count}개</h1>
<p>에펙에 들어 있는 글자 프리셋을 같은 한글 자막(Noto Sans KR Black 100, 흰 글자·검은 외곽선)에 하나씩 건 결과입니다. 영상을 누르면 크게 봅니다.</p></header>
<nav>{nav}</nav>
{sections}
<footer>만든 날 {date} · 관제 112 · 주황 글씨 = 프리셋이 글꼴·크기를 바꾼 것</footer>
<script>
const io=new IntersectionObserver(es=>es.forEach(e=>{{const v=e.target;if(e.isIntersecting){{if(!v.src)v.src=v.dataset.src;v.play().catch(()=>{{}})}}else v.pause()}}),{{rootMargin:'200px'}});
document.querySelectorAll('video').forEach(v=>{{io.observe(v);v.addEventListener('click',()=>{{if(document.fullscreenElement)document.exitFullscreen();else v.requestFullscreen()}})}});
</script></body></html>"""


def main():
    rows = [ln.split("\t") for ln in (WORK / "presets_manifest.txt").read_text(encoding="utf-8-sig").splitlines() if ln.strip()]
    DEST.mkdir(parents=True, exist_ok=True)
    groups, missing, count = {}, [], 0
    for r in rows:
        vid, folder, name, font, size = r[0], r[1], r[2], r[3], r[4]
        src = WORK / "presets" / f"{vid}.mp4"
        if not src.exists() or src.stat().st_size < 10000:
            missing.append(vid)
            continue
        shutil.copy2(src, DEST / f"{vid}.mp4")
        count += 1
        note = "" if (font == "NotoSansKR-Black" and size == "100") else f'<span class="note">글꼴·크기 바뀜({html.escape(font)} {size})</span>'
        groups.setdefault(folder, []).append(
            f'<div class="card"><video data-src="{vid}.mp4" loop muted playsinline preload="none"></video>'
            f'<div><b><span class="id">{vid}</span>{html.escape(name)}</b>{note}</div></div>')
    keys = [k for k in ORDER if k in groups] + [k for k in groups if k not in ORDER]
    nav = "".join(f'<a href="#g{i}">{html.escape(KO.get(k, k))} {len(groups[k])}</a>' for i, k in enumerate(keys))
    sections = "\n".join(
        f'<section id="g{i}"><h2>{html.escape(KO.get(k, k))}<small>{html.escape(k)} · {len(groups[k])}개</small></h2>'
        f'<div class="grid">{"".join(groups[k])}</div></section>' for i, k in enumerate(keys))
    (DEST / "index.html").write_text(
        PAGE.format(count=count, nav=nav, sections=sections, date=datetime.date.today().isoformat()), encoding="utf-8")
    print(f"영상 {count}개 / 목록 {len(rows)}개 → {DEST / 'index.html'}")
    if missing:
        print(f"없는 영상 {len(missing)}개: " + ", ".join(missing[:30]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
