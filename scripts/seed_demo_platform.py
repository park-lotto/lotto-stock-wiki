"""틱톡·도우인 랭킹에 **데모용 임시 데이터**를 채운다(영상 촬영용, 2026-07-30).

실제 수집 파이프라인은 아직 없다. 촬영할 때 탭이 비어 보이지 않도록 임시로 채우고,
진짜 구현이 붙으면 `--clear`로 지우면 된다. 저장 위치가 실제 수집과 같은
`settings.last_run::<platform>`이라 화면·API를 하나도 안 고치고 그대로 보인다.

⚠️ 데모 데이터임을 남긴다: 각 항목에 `demo: true`가 박힌다. 나중에 "이거 진짜 수집한
데이터인가?"를 판별할 수 있어야 한다 — 라벨 없는 가짜 데이터가 제일 위험하다.

쓰는 법:
    python3 scripts/seed_demo_platform.py --platform tiktok
    python3 scripts/seed_demo_platform.py --platform douyin
    python3 scripts/seed_demo_platform.py --platform tiktok --clear   # 지우기
    python3 scripts/seed_demo_platform.py --platform tiktok --file my.json

내용을 바꾸려면 `shopping_shorts/data/demo/<platform>.json`을 편집하면 된다
(없으면 이 파일 안의 기본 샘플을 쓴다).
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shopping_shorts.config import DB_PATH   # noqa: E402
from shopping_shorts.store import Store      # noqa: E402

_DEMO_DIR = Path(__file__).resolve().parents[1] / "shopping_shorts" / "data" / "demo"

# 기본 샘플 — 실존 계정을 흉내내지 않는다(가공 핸들). 촬영에서 화면이 채워져 보이는 게 목적.
_SAMPLE = {
    "tiktok": [
        ("kitchen.pick", "주방템 픽", "홈템", 182000, 4300, 210, 96),
        ("livingroom.log", "리빙로그", "홈템", 143000, 3900, 175, 88),
        ("selfcook.daily", "자취요리 데일리", "레시피", 121000, 3100, 260, 74),
        ("gadget.review.kr", "가전 리뷰", "가전", 98000, 2400, 141, 61),
        ("tidy.house", "정리수납 하우스", "홈템", 87000, 2100, 133, 55),
        ("beauty.minute", "1분 뷰티", "뷰티", 76000, 1900, 118, 47),
        ("small.room.diy", "원룸 DIY", "홈템", 64000, 1500, 102, 39),
        ("daiso.hunter", "다이소 헌터", "홈템", 58000, 1300, 95, 33),
    ],
    "xiaohongshu": [
        ("home.note.kr", "홈노트", "홈템", 96000, 5200, 340, 180),
        ("kitchen.diary", "주방일기", "홈템", 84000, 4600, 291, 152),
        ("onecook.note", "혼밥노트", "레시피", 73000, 3900, 254, 131),
        ("tidy.note", "정리노트", "홈템", 61000, 3300, 208, 108),
        ("skin.note.daily", "스킨노트", "뷰티", 54000, 2800, 176, 92),
        ("small.appliance", "소형가전 기록", "가전", 47000, 2400, 151, 77),
        ("room.makeover", "방꾸미기", "홈템", 39000, 1900, 124, 61),
        ("daiso.note", "다이소 노트", "홈템", 32000, 1500, 101, 48),
    ],
    "douyin": [
        ("chufang.hao", "厨房好物", "홈템", 264000, 7100, 320, 150),
        ("jiaju.sheji", "家居设计", "홈템", 205000, 5600, 268, 122),
        ("yiren.canzhuo", "一人餐桌", "레시피", 176000, 4700, 233, 101),
        ("xiaojiadian", "小家电测评", "가전", 152000, 4100, 198, 87),
        ("shouna.dashi", "收纳大师", "홈템", 131000, 3400, 171, 72),
        ("meizhuang.1fen", "美妆一分钟", "뷰티", 118000, 2900, 149, 63),
        ("zujin.gaizao", "租房改造", "홈템", 94000, 2200, 126, 48),
        ("haowu.tuijian", "好物推荐", "홈템", 81000, 1800, 108, 41),
    ],
}

_GRADES = ["🔥", "🚀", "👍", "—"]


def _build(platform, rows, now):
    """샘플 행 → 랭킹 카드가 그대로 읽는 항목(build_overseas_items 출력과 같은 모양)."""
    items = []
    for i, (handle, title, category, views, likes, comments, shares) in enumerate(rows):
        base = likes + comments + shares
        age_h = 3 + i * 2.5                      # 최근 3시간~하루 사이로 흩어놓는다
        published = now - timedelta(hours=age_h)
        items.append({
            "platform": platform,
            "shortcode": f"demo_{platform}_{i:02d}",
            "name": title,
            "username": handle,
            "inpock": "",
            "followers": None,
            "thumbnail": "",                     # 외부 이미지 안 씀(로딩 지연·저작권 회피)
            "video_url": "",
            "url": "",
            "caption": f"{title} · 데모 데이터",
            "category": category,
            "views": views,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "base": base,
            "delta": int(base * 0.18),
            "accel": int(base * 0.05),
            "speed": round(base / age_h, 1),
            "density": 0.0,
            "age_hours": round(age_h, 1),
            "grade": _GRADES[min(i // 3, len(_GRADES) - 1)],
            "is_new": i < 3,
            "published_at": published.isoformat(),
            "demo": True,                        # ★데모 표시 — 진짜 수집분과 구분
        })
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", required=True, choices=sorted(_SAMPLE))
    ap.add_argument("--clear", action="store_true", help="데모 데이터 삭제(빈 목록으로)")
    ap.add_argument("--file", help="직접 만든 항목 JSON(리스트) 경로")
    args = ap.parse_args()

    store = Store(DB_PATH)
    now = datetime.now(timezone.utc)

    if args.clear:
        store.save_last_run_platform(args.platform, [], None)
        print(f"[demo] {args.platform} 데모 데이터 삭제")
        return 0

    if args.file:
        items = json.loads(Path(args.file).read_text(encoding="utf-8"))
    else:
        path = _DEMO_DIR / f"{args.platform}.json"
        rows = (json.loads(path.read_text(encoding="utf-8")) if path.exists()
                else _SAMPLE[args.platform])
        items = _build(args.platform, [tuple(r) for r in rows], now)

    store.save_last_run_platform(args.platform, items, now.isoformat())
    print(f"[demo] {args.platform} {len(items)}건 채움 (demo=true 표시됨)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
