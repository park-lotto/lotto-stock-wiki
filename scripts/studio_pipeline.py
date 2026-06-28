"""딸깍 생성 파이프라인 — 단계별 SSE 이벤트를 yield하고 산출물/이력을 남긴다."""
import sys, json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import studio_data, gemini_image, card_render
import viz_card

STUDIO_DIR = ROOT / "out" / "studio"
IMG_DIR = STUDIO_DIR / "img"

STEPS = {1: "수급·시황 데이터 수집", 2: "AI 히로이미지 생성",
         3: "카드 디자인 렌더링", 4: "이미지 추출(PNG)", 5: "텔레그램 채널 전송"}


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
    STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    try:
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
