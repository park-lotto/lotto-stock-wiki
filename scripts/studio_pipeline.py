"""딸깍 생성 파이프라인 — 단계별 SSE 이벤트를 yield하고 산출물/이력을 남긴다."""
import sys, json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import studio_data, gemini_image, card_render
import studio_picks, card_picks
import viz_card

STUDIO_DIR = ROOT / "out" / "studio"
IMG_DIR = STUDIO_DIR / "img"

STEPS = {1: "수급·시황 데이터 수집", 2: "AI 히로이미지 생성",
         3: "카드 디자인 렌더링", 4: "이미지 추출(PNG)", 5: "텔레그램 채널 전송"}

PICKS_STEPS = {1: "신호 스냅샷 로드", 2: "수급빈집 탑픽 산출(교집합)",
               3: "카드 렌더링", 4: "이미지 추출(PNG)", 5: "텔레그램 채널 전송"}


def _append_index(entry: dict) -> None:
    STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    idx_path = STUDIO_DIR / "index.json"
    idx = []
    if idx_path.exists():
        try:
            idx = json.loads(idx_path.read_text(encoding="utf-8"))
        except Exception:
            idx = []
    idx.insert(0, entry)  # 최신이 위
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")


def _step(i, status, msg=""):
    return {"type": "step", "id": i, "status": status,
            "message": msg or STEPS[i]}


def generate_briefing(date: str):
    try:
        STUDIO_DIR.mkdir(parents=True, exist_ok=True)
        IMG_DIR.mkdir(parents=True, exist_ok=True)
        # ① 데이터
        yield _step(1, "running")
        data = studio_data.get_briefing_data(date)
        yield _step(1, "done")

        # ② Gemini 히로 이미지
        yield _step(2, "running")
        hero = IMG_DIR / f"{date}_hero.png"
        prompt = gemini_image.build_prompt(data)
        res = gemini_image.generate_hero(prompt, hero)
        msg = "폴백 이미지 사용" if res.get("fallback") else "AI 이미지 생성"
        yield _step(2, "done", msg)

        # ③ 카드 렌더
        yield _step(3, "running")
        html = card_render.render_briefing_card(data, hero)
        html_path = STUDIO_DIR / f"{date}_브리핑.html"
        card_render.save_card_html(html, html_path)
        yield _step(3, "done")

        # ④ PNG 추출
        yield _step(4, "running")
        png_path = STUDIO_DIR / f"{date}_브리핑.png"
        ok_png = viz_card.save_png(html_path, png_path)
        if not ok_png:
            yield _step(4, "error", "PNG 추출 실패(Playwright 확인)")
            yield {"type": "error", "message": "PNG 추출 실패"}
            return
        yield _step(4, "done")

        # ⑤ 텔레그램 전송 (실패해도 부분 성공)
        yield _step(5, "running")
        caption = f"📊 {date} 아침 브리핑\n{data.get('headline','')}"
        sent = viz_card.send_telegram_photo(png_path, caption)
        yield _step(5, "done" if sent else "error",
                    "전송 완료" if sent else "전송 실패(PNG는 저장됨)")

        entry = {"date": date, "type": "briefing",
                 "png": str(png_path), "html": str(html_path),
                 "thumb": str(png_path), "sent_tg": bool(sent),
                 "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")}
        _append_index(entry)
        yield {"type": "done", "png": str(png_path), "html": str(html_path),
               "thumb": str(png_path), "sent_tg": bool(sent)}
    except Exception as e:
        yield {"type": "error", "message": str(e)}


def _pstep(i, status, msg=""):
    return {"type": "step", "id": i, "status": status, "message": msg or PICKS_STEPS[i]}


def generate_picks(date: str):
    """시황 + 수급빈집 탑픽 통합 카드 — signal_snapshot 기반(daily_scenario 불필요)."""
    try:
        STUDIO_DIR.mkdir(parents=True, exist_ok=True)
        # ① 신호 스냅샷 로드 + ② 탑픽 산출(교집합)
        yield _pstep(1, "running")
        data = studio_picks.get_picks(top_n=4)
        if not data.get("picks"):
            yield _pstep(1, "error", "신호 스냅샷 없음/탑픽 0종")
            yield {"type": "error", "message": "signal_snapshot 없음 또는 탑픽 0종"}
            return
        yield _pstep(1, "done", f"{data.get('source','')} 로드")

        yield _pstep(2, "running")
        names = " · ".join(p["name"] for p in data["picks"][:4])
        yield _pstep(2, "done", f"탑픽 {len(data['picks'])}종: {names}")

        # ③ 카드 렌더
        yield _pstep(3, "running")
        html = card_picks.render_picks_card(data)
        html_path = STUDIO_DIR / f"{date}_탑픽.html"
        card_picks.save_card_html(html, html_path)
        yield _pstep(3, "done")

        # ④ PNG 추출
        yield _pstep(4, "running")
        png_path = STUDIO_DIR / f"{date}_탑픽.png"
        if not viz_card.save_png(html_path, png_path):
            yield _pstep(4, "error", "PNG 추출 실패(Playwright 확인)")
            yield {"type": "error", "message": "PNG 추출 실패"}
            return
        yield _pstep(4, "done")

        # ⑤ 텔레그램 전송 (실패해도 부분 성공)
        yield _pstep(5, "running")
        caption = (f"🌅 {data.get('date','')} 시황 + 수급빈집 탑픽\n"
                   f"주도섹터 교집합 탑픽: {names}\n"
                   f"(9점표·수급빈집·소르티노 + 원자DB 근거)")
        sent = viz_card.send_telegram_photo(png_path, caption)
        yield _pstep(5, "done" if sent else "error",
                     "전송 완료" if sent else "전송 실패(PNG는 저장됨)")

        entry = {"date": date, "type": "picks",
                 "png": str(png_path), "html": str(html_path),
                 "thumb": str(png_path), "sent_tg": bool(sent),
                 "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")}
        _append_index(entry)
        yield {"type": "done", "png": str(png_path), "html": str(html_path),
               "thumb": str(png_path), "sent_tg": bool(sent)}
    except Exception as e:
        yield {"type": "error", "message": str(e)}
