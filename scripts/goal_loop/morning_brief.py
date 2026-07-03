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
    """gemini_fn 미주입 시 기본 구현. gemini-2.5-flash 우선, 429 등 실패 시 gemini-3-flash-preview 폴백."""
    from google import genai
    key = gemini_image._load_env().get("GEMINI_API_KEY", "")
    client = genai.Client(api_key=key)

    def fn(prompt):
        for model in ("gemini-2.5-flash", "gemini-3-flash-preview"):
            try:
                r = client.models.generate_content(model=model, contents=prompt)
                txt = getattr(r, "text", "") or ""
                if txt:
                    return txt
            except Exception:
                continue
        return ""

    return fn


def _ensure_scenario(date: str) -> None:
    """Stage 0: daily_scenario로 out/scenario_{date}.md 생성(없을 때만). best-effort."""
    scen = ROOT / "out" / f"scenario_{date}.md"
    if scen.exists():
        return
    try:
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "daily_scenario.py"), "--date", date],
                       cwd=str(ROOT), capture_output=True, timeout=300)
    except Exception:
        pass


def _escalate(png, reasons: list, date: str) -> dict:
    """이상/실패 시: 대기 저장 + (OWNER_CHAT_ID 있을 때만) 사장님 개인 텔레 알림. 채널로는 절대 안 보냄(fail-closed)."""
    pending.write({"date": date, "png": png or "", "reasons": reasons,
                   "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")})
    owner = (os.environ.get("OWNER_CHAT_ID") or "").strip()
    if owner:
        try:
            if png:
                viz_card.send_telegram_photo(png, "⚠️ 확인 필요: " + " / ".join(reasons), chat_id=owner)
            else:
                viz_card.send_telegram_message("⚠️ 아침 브리핑 보류: " + " / ".join(reasons), chat_id=owner)
        except Exception:
            pass
    return {"status": "escalated", "reasons": reasons, "png": png or ""}


def run_morning_brief(date: str, gemini_fn=None, max_iter: int = 3) -> dict:
    try:
        gfn = gemini_fn or _default_gemini()

        _ensure_scenario(date)                       # Stage 0: 데이터·1차 드래프트 생성
        data = studio_data.get_briefing_data(date)
        data.setdefault("date", date)

        # ── 빈 데이터 가드: 헛소리 생성·발행 원천 차단 ──
        # 콘텐츠(headline/lines)가 비면 quality.revise가 근거 없이 지어낼 수 있으므로
        # 개선 루프에 절대 넣지 않고 즉시 에스컬레이션(채널 발행 안 함).
        if not (str(data.get("headline") or "").strip() or data.get("lines")):
            return _escalate(None, ["브리핑 데이터 없음(Stage0 실패) — 발행 중단, 수동 확인 필요"], date)

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

        if flags:                                    # fail-closed: 채널 발행 안 하고 에스컬레이션
            return _escalate(png, flags, date)

        viz_card.send_telegram_photo(png, f"📊 {date} 아침 브리핑\n{data.get('headline', '')}")
        return {"status": "sent", "reasons": [], "png": png}
    except Exception as e:
        # 침묵 금지: 실패해도 대기 저장 + 사장님 알림(가능하면)
        return _escalate(None, [f"브리핑 실패: {str(e)[:200]}"], date)


def should_run_now(now_dt, last_run_date) -> bool:
    """평일 & 08:00~08:14 & 오늘 미실행이면 True. (서버 데몬 게이트, 순수 함수라 테스트 용이)"""
    if now_dt.weekday() >= 5:            # 토(5)·일(6) 제외
        return False
    mins = now_dt.hour * 60 + now_dt.minute
    if not (480 <= mins <= 494):         # 08:00~08:14
        return False
    return last_run_date != now_dt.strftime("%Y-%m-%d")
