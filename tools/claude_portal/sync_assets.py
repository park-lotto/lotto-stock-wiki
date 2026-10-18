# -*- coding: utf-8 -*-
"""클로드형 원본 자산 등록(관제 234) — 글꼴·효과음·BGM·꾸미기 템플릿·짤 원본을 sha256 내용주소로 저장소(assets/<sha256>)에 넣고
claude_assets 표(id, kind, name, sha256, size, preview_id, grp)를 갱신한다. 저장은 claude_portal.put_blob 하나(내용주소 주인).

어디서 찾나(2026-10-18 실측 위치):
  글꼴    out/scene-style-ui-showcase.html 의 @font-face(렌더러가 실제로 여는 파일) — id font:<family>
          + 거기 없는 static/fonts/*.ttf·otf 는 "Cc"+줄기 이름(엔진 tools/calcopy/register_fonts.py 와 같은 이름 규칙 — 칼카피 틀이 쓰는 이름)
  효과음  shopping_shorts/assets/sfx_packs/팩NN/*.wav — id sfx:팩NN/<파일>, grp=팩NN
  BGM     shopping_shorts/assets/bgm_lib/catalog.json tracks — id bgm:<id>
  템플릿  deco_templates.TEMPLATES → static/templates/<file> — id template:<id>
  짤      DB scene_assets(cid 0, clip, category meme, tone) 의 media_path — id meme:<번호>, grp=감정. ★서버에만 있을 수 있다

    py tools/claude_portal/sync_assets.py --db <reference.db> [--store <CLAUDE_STORE_DIR>] [--no-prune]
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SS = ROOT / "shopping_shorts"
SHOWCASE = ROOT / "out" / "scene-style-ui-showcase.html"
SFX_SLOT = {"opener": "오프너", "pop": "뽁", "dung": "둥", "ding": "띠링", "whoosh": "휙", "tick": "틱", "click2": "딸깍2"}


def font_sources():
    """(family, 파일 Path) — 렌더러 등록 글꼴 + 등록 안 된 창고 글꼴(Cc 이름)."""
    out, seen_stems = [], set()
    if SHOWCASE.exists():
        html = SHOWCASE.read_text(encoding="utf-8")
        for fam, url in re.findall(r'@font-face\s*\{[^}]*?font-family:\s*"([^"]+)"[^}]*?src:\s*url\("([^"]+)"', html):
            p = (SHOWCASE.parent / url).resolve()
            if p.exists():
                out.append((fam, p))
                seen_stems.add(p.stem.lower())
    for p in sorted((SS / "static" / "fonts").glob("*")):
        if p.suffix.lower() in (".ttf", ".otf") and p.stem.lower() not in seen_stems:
            out.append(("Cc" + re.sub(r"[^A-Za-z0-9_-]", "", p.stem), p))
    return out


def sfx_sources():
    base = SS / "assets" / "sfx_packs"
    for d in sorted(base.glob("팩*")):
        for f in sorted(d.iterdir()):
            if f.suffix.lower() in (".wav", ".mp3"):
                yield d.name, f


def bgm_sources():
    base = SS / "assets" / "bgm_lib"
    cat = json.loads((base / "catalog.json").read_text(encoding="utf-8"))
    for t in cat.get("tracks") or []:
        f = base / f"{t['id']}.mp3"
        if f.exists():
            yield t, f


def template_sources():
    from shopping_shorts import deco_templates
    for t in deco_templates.TEMPLATES:
        f = SS / "static" / "templates" / t["file"]
        if f.exists():
            yield t, f


def meme_sources(store):
    try:
        rows = store.list_scene_assets(customer_id=0, asset_type="clip", category="meme") or []
    except Exception as e:      # noqa: BLE001 — 표가 없는 빈 DB 면 짤 0개(사실을 출력한다)
        print(f"  짤: DB 조회 실패({type(e).__name__}) — 0개로 둔다")
        return []
    out = []
    for a in rows:
        emo = str(a.get("tone") or "").strip()
        mp = a.get("media_path")
        if emo and mp and Path(mp).exists():
            out.append((a, emo, Path(mp)))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--store", default="")
    ap.add_argument("--no-prune", action="store_true")
    a = ap.parse_args(argv)
    if a.store:
        os.environ["CLAUDE_STORE_DIR"] = a.store
    from shopping_shorts import claude_portal as cp
    from shopping_shorts.store import Store
    st = Store(a.db)
    cp.ensure_schema(st)
    seen = {k: set() for k in cp.ASSET_KINDS}
    n = {k: 0 for k in cp.ASSET_KINDS}

    for fam, p in font_sources():
        sha, size = cp.put_blob(p)
        cp.upsert_asset(st, f"font:{fam}", "font", p.name, sha, size, grp="", preview_id=fam, meta={"label": None})
        seen["font"].add(f"font:{fam}")
        n["font"] += 1
    for pack, f in sfx_sources():
        sha, size = cp.put_blob(f)
        aid = f"sfx:{pack}/{f.name}"
        cp.upsert_asset(st, aid, "sfx", f.name, sha, size, grp=pack, preview_id=pack, meta={"slot": SFX_SLOT.get(f.stem, f.stem)})
        seen["sfx"].add(aid)
        n["sfx"] += 1
    for t, f in bgm_sources():
        sha, size = cp.put_blob(f)
        aid = f"bgm:{t['id']}"
        cp.upsert_asset(st, aid, "bgm", f.name, sha, size, preview_id=t["id"], meta={"title": t.get("title"), "artist": t.get("artist")})
        seen["bgm"].add(aid)
        n["bgm"] += 1
    for t, f in template_sources():
        sha, size = cp.put_blob(f)
        aid = f"template:{t['id']}"
        cp.upsert_asset(st, aid, "template", f.name, sha, size, preview_id=t["id"], meta={"label": t.get("name")})
        seen["template"].add(aid)
        n["template"] += 1
    memes = meme_sources(st)
    for a_, emo, f in memes:
        sha, size = cp.put_blob(f)
        aid = f"meme:{a_['id']}"
        cp.upsert_asset(st, aid, "meme", f.name, sha, size, grp=emo, meta={"dur": a_.get("duration")})
        seen["meme"].add(aid)
        n["meme"] += 1

    pruned = 0
    if not a.no_prune:
        for kind in cp.ASSET_KINDS:
            if kind == "meme" and not memes:
                continue          # 이 PC 에 짤이 없다고 서버 등록분을 지우지 않는다
            for r in cp._assets(st, kind):
                if r["id"] not in seen[kind]:
                    with cp._tx(st, write=True) as c:
                        c.execute("DELETE FROM claude_assets WHERE id=?", (r["id"],))
                    pruned += 1
    blobs = len(list((cp.store_dir() / "assets").glob("*")))
    print("등록:", " · ".join(f"{k} {v}" for k, v in n.items()), f"| 빠진 행 삭제 {pruned} | 저장소 파일 {blobs}개 ({cp.store_dir()})")
    if not memes:
        print("짤: 이 PC DB 에 짤 원본(scene_assets meme, 파일 있음)이 없다 — meme 종류는 비워 뒀다(서버에서 이 도구를 돌리면 채워진다)")
    return n


if __name__ == "__main__":
    main()
