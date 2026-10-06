"""점검 도구 공용 — 장면별 등장 계획을 편집기 판단 함수(window.sceneStyle.motionPlan)에서 그대로 받는다(관제 144).
도구마다 기대값을 따로 계산하면 판단이 두 벌이 된다(0순위-B). 기대 등장 길이(ms)도 편집기 runCaptionEnter 와 같은 셈."""
import json, math, pathlib
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]
TEXT = (ROOT / "shopping_shorts/static/caption-motions.js").read_text(encoding="utf-8")
MOTIONS = json.loads(TEXT.split("/*JSON*/")[1])
STYLES = json.loads(TEXT.split("/*PACKS*/")[1])
MPACKS = json.loads(TEXT.split("/*MPACKS*/")[1])


def plans(context, snapshots):
    """[snapshot, ...] → [[장면별 효과 키], ...] — 같은 편집기를 한 번 열고 차례로 load."""
    url = (ROOT / "out/scene-style-ui-showcase.html").as_uri() + "?qa=1"
    out = []
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(); pg.goto(url); pg.wait_for_timeout(1200)
        for s in snapshots:
            pg.evaluate("([c,s])=>window.sceneStyle.load(c,s)", [context, s]); pg.wait_for_timeout(50)
            out.append(pg.evaluate("()=>window.sceneStyle.motionPlan()"))
        b.close()
    return out


def expect_ms(motion, caption):
    """편집기 runCaptionEnter 와 같은 셈: 단위 수 → 간격(stagger, spread 상한) → 마지막 단위 시작 + 한 단위 길이."""
    if not motion:
        return None
    m = MOTIONS[motion]; unit = m.get("unit")
    n = len(caption.split()) if unit == "word" else len(caption.replace(" ", "")) if unit == "char" else 1
    step = min(m.get("stagger", 0), m.get("spread", math.inf) / (n - 1)) if n > 1 else 0
    return math.ceil((n - 1) * step + m["ms"])
