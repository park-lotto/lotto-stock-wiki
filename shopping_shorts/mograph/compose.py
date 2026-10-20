# -*- coding: utf-8 -*-
"""작업물 조립 — 판단 주인 build_work (관제 244).
장면표(plan.plan_from_lines) → 템플릿(templates/shop_intro.html)에 PLAN 을 박아 작업 폴더 src/index.html 하나를 만든다.
★작업대 미리보기(iframe)와 HyperFrames 렌더가 **같은 파일**을 읽는다 — 화면·렌더 두 벌 금지(0순위-C).
작업 폴더: data/mograph/renders/work-<id>/ (render.py 가 그대로 렌더한다 — slug 'work-…')."""
import hashlib
import json
import shutil
import time
from pathlib import Path

from shopping_shorts.mograph import plan as _plan, render as _render

TEMPLATES = Path(__file__).parent / "templates"
STATIC = Path(__file__).resolve().parents[1] / "static"
FONTS = ["Pretendard-Regular.otf", "Pretendard-SemiBold.otf", "Pretendard-Bold.otf", "Pretendard-ExtraBold.otf", "NanumMyeongjo-ExtraBold.ttf"]
TEMPLATE_VERSION = {"shop_intro": "shop_intro.v1", "shop_pocket": "shop_pocket.v1"}


def work_id(lines, product, preset_id):
    raw = json.dumps([lines, product, preset_id], ensure_ascii=False, sort_keys=True)
    return "work-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def build_work(lines, product=None, preset_id=_plan.DEFAULT_PRESET, template=None, timings=None):
    """되돌려 주는 값 = {id, dir, plan}. 같은 입력이면 같은 id(다시 만들어도 덮어쓴다). 템플릿은 프리셋(template 칸)이 정한다 — 없으면 shop_intro."""
    pl = _plan.plan_from_lines(lines, product, preset_id, timings)
    template = template or _plan._preset(preset_id).get("template") or "shop_intro"
    if not (TEMPLATES / (template + ".html")).exists():
        raise ValueError("없는 템플릿: %s" % template)
    wid = work_id(lines, pl["product"], preset_id)
    d = _render.out_dir(wid)
    src = d / "src"
    if src.exists():
        shutil.rmtree(src)
    (src / "vendor").mkdir(parents=True)
    (src / "fonts").mkdir()
    shutil.copy2(STATIC / "mograph" / "vendor" / "gsap.min.js", src / "vendor" / "gsap.min.js")
    for f in FONTS:
        shutil.copy2(STATIC / "fonts" / f, src / "fonts" / f)
    html = (TEMPLATES / (template + ".html")).read_text(encoding="utf-8")
    assert "__PLAN__" in html and 'data-duration="15"' in html
    # 길이는 루트 속성에 박는다 — HyperFrames 는 JS 가 바꾼 dataset 이 아니라 파일의 속성값을 읽는다(실측: 9.7초 작업이 15초로 렌더돼 뒤 5초가 검정)
    html = html.replace('data-duration="15"', 'data-duration="%s"' % pl["total"]).replace("__PLAN__", json.dumps(pl, ensure_ascii=False))
    (src / "index.html").write_text(html, encoding="utf-8")
    meta = {"id": wid, "template": TEMPLATE_VERSION.get(template, template), "made": time.strftime("%Y-%m-%d %H:%M:%S"), "lines": lines,
            "product": pl["product"], "preset": preset_id, "total": pl["total"], "scenes": len(pl["scenes"])}
    (d / "work.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "plan.json").write_text(json.dumps(pl, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"id": wid, "dir": str(d), "plan": pl, "meta": meta}


def load_work(wid):
    d = _render.out_dir(wid)
    p = d / "work.json"
    if not wid.startswith("work-") or not p.exists():
        return None
    meta = json.loads(p.read_text(encoding="utf-8"))
    meta["plan"] = json.loads((d / "plan.json").read_text(encoding="utf-8")) if (d / "plan.json").exists() else None
    meta["render"] = _render.status(wid)
    return meta


def list_works(limit=30):
    out = []
    if not _render.RENDERS_DIR.exists():
        return out
    for d in sorted(_render.RENDERS_DIR.glob("work-*"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        w = load_work(d.name)
        if w:
            w.pop("plan", None)
            out.append(w)
    return out
