"""아침 브리핑 오케스트레이터: 생성→품질루프→이상징후 게이트→발송/에스컬레이션."""
import os, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import studio_data, card_render, viz_card, gemini_image  # noqa: E402
from scripts.goal_loop import verify, quality, pending  # noqa: E402

STUDIO_DIR = ROOT / "out" / "studio"


def _render_card(data: dict, date: str) -> str:
    STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    hero = STUDIO_DIR / "img" / f"{date}_hero.png"
    hero.parent.mkdir(parents=True, exist_ok=True)
    try:
        gemini_image.generate_hero(gemini_image.build_prompt(data), hero)
    except Exception:
        pass
    html = card_render.render_briefing_card(data, hero)
    html_path = STUDIO_DIR / f"{date}_브리핑.html"
    card_render.save_card_html(html, html_path)
    png_path = STUDIO_DIR / f"{date}_브리핑.png"
    viz_card.save_png(html_path, png_path)
    return str(png_path)


def _get_index_moves() -> dict:
    try:
        import kis_api
        k = kis_api.get_index_price("0001")
        q = kis_api.get_index_price("1001")
        return {"kospi": float(k.get("change_rate", 0)), "kosdaq": float(q.get("change_rate", 0))}
    except Exception:
        return {}


def _default_gemini():
    """gemini_fn 미주입 시 기본 구현. google-genai 직접 호출(gemini_image._load_env 재사용)."""
    from google import genai
    key = gemini_image._load_env().get("GEMINI_API_KEY", "")
    client = genai.Client(api_key=key)

    def fn(prompt):
        r = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return getattr(r, "text", "") or ""

    return fn


def run_morning_brief(date: str, gemini_fn=None, max_iter: int = 3) -> dict:
    try:
        gfn = gemini_fn or _default_gemini()
        data = studio_data.get_briefing_data(date)
        data.setdefault("date", date)

        quality_ok = False
        for _ in range(max_iter):
            c = quality.critique(data, gfn)
            if c["pass"]:
                quality_ok = True
                break
            data = quality.revise(data, c["issues"], gfn)

        png = _render_card(data, date)

        flags = verify.detect_anomalies(data, date, _get_index_moves())
        if not quality_ok:
            flags.append("품질 기준 미달(3회 개선 후에도)")

        caption = f"📊 {date} 아침 브리핑\n{data.get('headline', '')}"

        if flags:
            pending.write({
                "date": date, "png": png, "reasons": flags,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
            owner = os.environ.get("OWNER_CHAT_ID") or ""
            viz_card.send_telegram_photo(png, "⚠️ 확인 필요: " + " / ".join(flags), chat_id=owner or None)
            return {"status": "escalated", "reasons": flags, "png": png}

        viz_card.send_telegram_photo(png, caption)
        return {"status": "sent", "reasons": [], "png": png}
    except Exception as e:
        return {"status": "error", "reasons": [str(e)], "png": ""}
