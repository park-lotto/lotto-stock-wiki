#!/usr/bin/env python3
"""감사 결과를 검색 가능한 로컬 폰트 라이브러리 팩으로 만든다."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / "font_collection"
PACK = COLLECTION / "library_pack"


def face_score(row: dict) -> tuple[int, int]:
    text = " ".join(row.get("full_names", []) + row.get("subfamilies", []) + [row["path"]]).lower()
    score = 0
    if any(x in text for x in ("variable", "[wght", " vf", "-vf", "_vf")):
        score += 70
    if "black" in text:
        score += 55
    elif "extra bold" in text or "extrabold" in text:
        score += 48
    elif "bold" in text:
        score += 42
    if "display" in text or "condensed" in text:
        score += 18
    if "regular" in text:
        score += 8
    if "italic" in text:
        score -= 5
    return score, -row["bytes"]


def main() -> int:
    rows = json.loads((COLLECTION / "audit" / "files.json").read_text(encoding="utf-8"))
    intl_path = COLLECTION / "manifests" / "github_international.json"
    intl = json.loads(intl_path.read_text(encoding="utf-8")) if intl_path.exists() else {"sources": []}
    repo_meta = {x["repo"].replace("/", "__"): x for x in intl["sources"]}

    chosen = {}
    for row in rows:
        if not row.get("valid"):
            continue
        family = next((x for x in row.get("families", []) if x), Path(row["path"]).stem)
        parts = Path(row["path"]).parts
        source = parts[2] if len(parts) > 2 else "unknown"
        key = (source, family)
        if key not in chosen or face_score(row) > face_score(chosen[key]):
            chosen[key] = row

    cards = []
    for (source, family), row in chosen.items():
        parts = Path(row["path"]).parts
        meta = repo_meta.get(parts[3], {}) if source == "github-international" and len(parts) > 3 else {}
        path_from_pack = "../" + str(Path(row["path"]).relative_to("font_collection")).replace("\\", "/")
        hook_text = " ".join([family, *row.get("full_names", []), *row.get("subfamilies", []), meta.get("group", "")]).lower()
        hook = source == "github-international" or any(word in hook_text for word in (
            "black", "bold", "heavy", "display", "condensed", "poster", "headline",
            "gasoek", "bagel fat", "do hyeon", "jua", "climate crisis", "gmarket",
        ))
        cards.append({
            "id": f"f{len(cards)}",
            "family": family,
            "face": next(iter(row.get("full_names", [])), family),
            "subfamily": next(iter(row.get("subfamilies", [])), ""),
            "path": path_from_pack,
            "source": source,
            "repo": meta.get("repo", ""),
            "group": meta.get("group", "hangul" if row.get("has_korean") else "latin"),
            "use": meta.get("use", "한글 제목·자막" if row.get("has_korean") else "영문·숫자 포인트"),
            "korean": bool(row.get("has_korean")),
            "hook": hook,
            "glyphs": row.get("glyphs", 0),
            "format": Path(row["path"]).suffix[1:].upper(),
        })
    cards.sort(key=lambda x: (not x["hook"], not x["korean"], x["source"] != "github-international", x["family"].lower()))

    PACK.mkdir(parents=True, exist_ok=True)
    (PACK / "catalog.js").write_text(
        "window.FONT_CATALOG = " + json.dumps(cards, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    (PACK / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (PACK / "README.md").write_text(
        "# 숏템 폰트 라이브러리 팩\n\n"
        f"- 대표 패밀리: {len(cards)}개\n"
        f"- 한글 지원 대표 패밀리: {sum(x['korean'] for x in cards)}개\n"
        f"- GitHub 해외 대표 패밀리: {sum(x['source'] == 'github-international' for x in cards)}개\n"
        "- `index.html`은 `py -m http.server 8765 -d font_collection`로 열면 실제 폰트 미리보기가 동작합니다.\n"
        "- 원본 파일은 `../files`, 라이선스는 `../licenses`, 출처 기록은 `../manifests`에 있습니다.\n"
        "- 해외 폰트는 대부분 한글이 없으므로 한글 훅과 섞어 쓰는 영문·숫자 포인트용입니다.\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "families": len(cards),
        "korean": sum(x["korean"] for x in cards),
        "github_international": sum(x["source"] == "github-international" for x in cards),
        "pack": str(PACK),
    }, ensure_ascii=False, indent=2))
    return 0


INDEX_HTML = r'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>숏템 폰트 라이브러리</title>
<style>
:root{color-scheme:dark;--bg:#080b10;--panel:#10151d;--line:#263140;--ink:#f6f8fb;--muted:#8c98a8;--lime:#dfff37;--cyan:#32e6d0}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.45 Arial,"Malgun Gothic",sans-serif}button,input{font:inherit}
.shell{max-width:1680px;margin:auto;padding:30px}.top{display:grid;grid-template-columns:1fr auto;align-items:end;gap:24px;margin-bottom:24px}
h1{margin:0;font-size:clamp(32px,4vw,64px);letter-spacing:-.055em;line-height:.92}.mark{color:var(--lime)}.summary{color:var(--muted);text-align:right}
.tools{position:sticky;top:0;z-index:20;display:flex;flex-wrap:wrap;gap:10px;padding:14px;background:rgba(8,11,16,.93);border:1px solid var(--line);border-radius:18px;backdrop-filter:blur(16px);margin-bottom:18px}
input{min-width:240px;flex:1;background:#0c1118;color:var(--ink);border:1px solid #344154;border-radius:11px;padding:12px 14px;outline:none}input:focus{border-color:var(--cyan)}
button{border:1px solid #344154;background:#111923;color:#bac5d3;border-radius:999px;padding:9px 14px;cursor:pointer}button.on{background:var(--ink);color:#090c11;border-color:var(--ink)}
.count{align-self:center;margin-left:auto;color:var(--cyan);font-weight:800}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:14px}
.card{min-height:250px;display:flex;flex-direction:column;overflow:hidden;border:1px solid var(--line);border-radius:18px;background:var(--panel);box-shadow:0 10px 40px #0004}.card:hover{border-color:#516078;transform:translateY(-2px)}
.specimen{min-height:160px;padding:26px 24px;display:flex;align-items:center;background:linear-gradient(145deg,#f5f2ea,#d9dde5);color:#080a0d;font-size:42px;line-height:1.08;letter-spacing:-.045em;overflow-wrap:anywhere}
.meta{padding:16px 18px 18px}.name{font-size:18px;font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.row{display:flex;gap:7px;flex-wrap:wrap;margin-top:9px}.tag{font-size:12px;padding:4px 8px;border:1px solid #344154;border-radius:999px;color:#aeb9c7}.tag.hot{color:#07110f;background:var(--cyan);border-color:var(--cyan)}
.use{margin-top:10px;color:var(--muted);font-size:14px}.empty{grid-column:1/-1;padding:80px;text-align:center;color:var(--muted)}
@media(max-width:700px){.shell{padding:18px}.top{grid-template-columns:1fr}.summary{text-align:left}.grid{grid-template-columns:1fr}.specimen{font-size:34px}.count{width:100%;margin-left:0}}
</style>
</head>
<body><main class="shell">
<header class="top"><h1>SHORTTEM<br><span class="mark">TYPE LIBRARY</span></h1><div class="summary" id="summary"></div></header>
<section class="tools" aria-label="폰트 필터">
<input id="sample" value="놀라운 생활 아이디어 2026" aria-label="미리보기 문구">
<input id="search" placeholder="폰트명·출처·용도 검색" aria-label="검색">
<button class="on" data-filter="hook">훅 추천</button><button data-filter="all">전체</button><button data-filter="korean">한글</button><button data-filter="github-international">GitHub 해외</button><button data-filter="condensed">콘덴스드</button><button data-filter="display">디스플레이</button>
<span class="count" id="count"></span>
</section><section class="grid" id="grid"></section>
</main><script src="catalog.js"></script><script>
const state={filter:'hook',query:'',sample:'놀라운 생활 아이디어 2026'};const grid=document.querySelector('#grid');const loaded=new Set();
function match(x){const q=state.query.toLowerCase();const text=[x.family,x.face,x.source,x.repo,x.group,x.use].join(' ').toLowerCase();const f=state.filter;return(!q||text.includes(q))&&(f==='all'||f==='hook'&&x.hook||f==='korean'&&x.korean||f==='github-international'&&x.source===f||f==='condensed'&&x.group.includes('condensed')||f==='display'&&/(display|black|slab|expressive|experimental|kinetic|ultra)/.test(x.group))}
function loadFont(x,el){if(loaded.has(x.id))return;loaded.add(x.id);const ff=new FontFace(x.id,`url("${x.path}")`);ff.load().then(v=>{document.fonts.add(v);el.style.fontFamily=x.id}).catch(()=>el.dataset.failed='1')}
function render(){const list=FONT_CATALOG.filter(match);grid.innerHTML=list.length?'':'<div class="empty">조건에 맞는 폰트가 없습니다.</div>';for(const x of list){const card=document.createElement('article');card.className='card';card.innerHTML=`<div class="specimen"></div><div class="meta"><div class="name">${x.family}</div><div class="row"><span class="tag ${x.korean?'hot':''}">${x.korean?'한글 지원':'영문 포인트'}</span><span class="tag">${x.group}</span><span class="tag">${x.format}</span></div><div class="use">${x.use}${x.repo?' · '+x.repo:''}</div></div>`;const specimen=card.firstElementChild;specimen.textContent=x.korean?state.sample:'MAKE IT IMPOSSIBLE TO IGNORE';grid.append(card);observer.observe(specimen)}document.querySelector('#count').textContent=`${list.length}개`;document.querySelector('#summary').innerHTML=`대표 패밀리 ${FONT_CATALOG.length}개<br>한글 ${FONT_CATALOG.filter(x=>x.korean).length} · GitHub 해외 ${FONT_CATALOG.filter(x=>x.source==='github-international').length}`}
const observer=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){const card=e.target.closest('.card');const i=[...grid.children].indexOf(card);const list=FONT_CATALOG.filter(match);if(list[i])loadFont(list[i],e.target);observer.unobserve(e.target)}}),{rootMargin:'300px'});
document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-filter]').forEach(x=>x.classList.remove('on'));b.classList.add('on');state.filter=b.dataset.filter;render()});
document.querySelector('#search').oninput=e=>{state.query=e.target.value;render()};document.querySelector('#sample').oninput=e=>{state.sample=e.target.value||'놀라운 생활 아이디어 2026';render()};render();
</script></body></html>'''


if __name__ == "__main__":
    raise SystemExit(main())
