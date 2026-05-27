#!/usr/bin/env python3
"""
send_crawl_brief.py — 크롤링 블로그뉴스유튭 요약 → 텔레그램 발송

사용법:
  python send_crawl_brief.py           ← 오늘 파일 자동 탐지 + 발송
  python send_crawl_brief.py --dry     ← 발송 없이 미리보기만
  python send_crawl_brief.py --date 2026-05-26  ← 특정 날짜
"""
import sys, re, json, urllib.request, urllib.parse
from pathlib import Path
from datetime import date, datetime

sys.stdout.reconfigure(encoding="utf-8")

RAW_DIR = Path(__file__).parent / "raw" / "크롤링 블로그뉴스유튭 요약"

# ── 노이즈 필터 (주식 무관 키워드) ────────────────────────────────────
NOISE_KEYWORDS = [
    "스타벅스", "스벅", "탱크데이", "선불카드", "환불",
    "미스트롯", "이윤나", "윤나", "엘컴퍼니",
    "유로벨로", "리옹", "자전거 여행",
    "신곡 발표", "활동명", "재계약",
]

# ── 섹터 탐지 키워드 ────────────────────────────────────────────────────
SECTOR_MAP = {
    "💾 반도체·소부장": ["반도체", "HBM", "DRAM", "낸드", "MLCC", "소부장", "장비", "메모리",
                       "Capex", "삼성전기", "SK하이닉스", "임베디드 기판", "substrate", "반도체 재료"],
    "🚢 조선": ["조선", "LNG선", "가스선", "수주", "한화오션", "HD현대", "잠수함", "선박", "도크"],
    "⛽ 에너지·호르무즈": ["호르무즈", "유가", "WTI", "이란", "에너지", "석유", "원유"],
    "🤖 로봇·AI": ["로봇", "휴머노이드", "AI", "인공지능"],
}


# ── .env 로드 ──────────────────────────────────────────────────────────
def _load_env() -> dict:
    env_path = Path(__file__).parent / ".env"
    cfg = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg


# ── 텔레그램 발송 ──────────────────────────────────────────────────────
def send_telegram(text: str) -> bool:
    cfg = _load_env()
    token = cfg.get("BOT_TOKEN", "")
    chat_id = cfg.get("CHAT_ID", "")
    if not token or not chat_id:
        print("⚠️  .env 에 BOT_TOKEN / CHAT_ID 없음")
        return False

    # 4096자 초과 시 분할 발송
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for idx, chunk in enumerate(chunks, 1):
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }).encode()
        req = urllib.request.Request(url, data=data)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                if result.get("ok"):
                    print(f"✅ 발송 완료 ({idx}/{len(chunks)})")
                else:
                    print(f"❌ 오류: {result}")
                    return False
        except Exception as e:
            print(f"❌ 발송 실패: {e}")
            return False
    return True


# ── MD 파일 파싱 ───────────────────────────────────────────────────────
def parse_md(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = text.strip().splitlines()

    item = {
        "title": "",
        "source": "",
        "source_type": "",   # 뉴스묶음 / 블로그 / 유튜브
        "url": "",
        "summary": "",
    }

    # 제목
    for line in lines:
        if line.startswith("# "):
            item["title"] = line[2:].strip()
            break

    # 메타
    for line in lines:
        line_s = line.strip()
        if line_s.startswith("- **출처**:"):
            item["source"] = line_s.replace("- **출처**:", "").strip()
            item["source_type"] = "블로그"
        elif line_s.startswith("- **채널**:"):
            item["source"] = line_s.replace("- **채널**:", "").strip()
            item["source_type"] = "유튜브"
        elif line_s.startswith("- **키워드**:"):
            item["source"] = line_s.replace("- **키워드**:", "").strip()
            item["source_type"] = "뉴스묶음"
        if "바로가기](http" in line_s or "원문 보기](http" in line_s:
            m = re.search(r"\((https?://[^\)]+)\)", line_s)
            if m:
                item["url"] = m.group(1)

    # 요약 (첫 문장 최대 100자)
    summary_lines = []
    capturing = False
    for line in lines:
        if re.match(r"^##\s+(본문|핵심 요약|종합 요약)", line):
            capturing = True
            continue
        if capturing:
            if line.startswith("## ") or line.startswith("- **수집된"):
                break
            if line.startswith("- ["):   # 기사 링크 목록 라인 스킵
                continue
            if line.strip():
                summary_lines.append(line.strip())

    if summary_lines:
        full = " ".join(summary_lines)
        # 한국어 문장 분리
        sent = re.split(r"(?<=[다이요며니다])\s+", full)
        first = sent[0] if sent else full
        # 한자·일어 등 노이즈 제거
        first = re.sub(r"[^가-힣 -~＀-￯]+", " ", first).strip()
        item["summary"] = first[:100]

    return item


# ── 노이즈 체크 ────────────────────────────────────────────────────────
def is_noise(item: dict) -> bool:
    text = (item["title"] + " " + item["summary"]).lower()
    return any(kw.lower() in text for kw in NOISE_KEYWORDS)


# ── 섹터 탐지 ─────────────────────────────────────────────────────────
def detect_sectors(item: dict) -> list:
    text = item["title"] + " " + item["summary"]
    return [s for s, kws in SECTOR_MAP.items() if any(kw in text for kw in kws)]


# ── 제목 dedupe ────────────────────────────────────────────────────────
def dedupe(items: list) -> list:
    seen = set()
    result = []
    for item in items:
        # 제목 앞 60자 기준 중복 제거
        key = item["title"][:60]
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


# ── 메시지 빌드 ────────────────────────────────────────────────────────
def _esc(text: str) -> str:
    """텔레그램 HTML 모드 이스케이프 (<>&)"""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_message(items: list, target_date: str) -> str:
    now = datetime.now().strftime("%H:%M")

    news  = [i for i in items if i["source_type"] == "뉴스묶음"]
    yt    = [i for i in items if i["source_type"] == "유튜브"]
    blogs = [i for i in items if i["source_type"] == "블로그"]

    # 섹터 집계
    sector_counts: dict = {}
    for i in items:
        for s in detect_sectors(i):
            sector_counts[s] = sector_counts.get(s, 0) + 1
    top_sectors = sorted(sector_counts, key=lambda x: -sector_counts[x])

    L = []
    L.append(f"📰 <b>로또의 주식 — 오늘의 크롤링 브리핑</b>")
    L.append(f"<i>{target_date}  ·  {now}  ·  {len(items)}건</i>")

    # 섹터 태그
    if top_sectors:
        L.append("")
        L.append("━━━━━━━━━━━━━━━")
        L.append("🔖 <b>오늘 언급 섹터</b>")
        for s in top_sectors[:5]:
            bar = "●" * sector_counts[s]
            L.append(f"  {s}  <code>{bar}</code> {sector_counts[s]}건")

    # 뉴스묶음
    if news:
        L.append("")
        L.append("━━━━━━━━━━━━━━━")
        L.append("📰 <b>뉴스</b>")
        for item in news:
            title = re.sub(r"\[.*?\]\s*오늘의 주요 뉴스 묶음", "", item["title"]).strip()
            title = _esc(title or item["source"])
            if item["url"]:
                L.append(f'  🔹 <a href="{item["url"]}">{title}</a>')
            else:
                L.append(f"  🔹 {title}")
            if item["summary"]:
                L.append(f"     <i>{_esc(item['summary'][:80])}</i>")

    # 유튜브
    if yt:
        L.append("")
        L.append("━━━━━━━━━━━━━━━")
        L.append("📺 <b>유튜브</b>")
        for item in yt:
            src = _esc(item["source"])
            t = re.sub(r"^\d{2}/\d{2}/\d{4}\s*", "", item["title"])
            t = _esc(t[:55]) + ("…" if len(t) > 55 else "")
            if item["url"]:
                L.append(f'  🎬 <a href="{item["url"]}">[{src}] {t}</a>')
            else:
                L.append(f"  🎬 [{src}] {t}")

    # 블로그
    if blogs:
        L.append("")
        L.append("━━━━━━━━━━━━━━━")
        L.append("✏️ <b>블로그</b>")
        for item in blogs:
            src = _esc(item["source"])
            raw_t = item["title"]
            t = _esc(raw_t[:55]) + ("…" if len(raw_t) > 55 else "")
            if item["url"]:
                L.append(f'  📌 <a href="{item["url"]}">[{src}] {t}</a>')
            else:
                L.append(f"  📌 [{src}] {t}")

    L.append("")
    L.append("━━━━━━━━━━━━━━━")
    L.append(f"<i>🤖 STOCK BRAIN  ·  로또의 주식</i>")

    return "\n".join(L)


# ── 메인 ──────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]
    dry_run = "--dry" in args

    target_date = date.today().strftime("%Y-%m-%d")
    for i, a in enumerate(args):
        if a == "--date" and i + 1 < len(args):
            target_date = args[i + 1]

    if not RAW_DIR.exists():
        print(f"❌ 폴더 없음: {RAW_DIR}")
        return

    all_files = sorted(RAW_DIR.glob("*.md"))
    today_files = [f for f in all_files if f.name.startswith(target_date)]

    if not today_files:
        print(f"⚠️  {target_date} 날짜 파일 없음 — 전체 {len(all_files)}개 중 최신 사용")
        today_files = all_files[-20:]   # 최근 20개 fallback

    print(f"📂 파일 {len(today_files)}개 로드")

    # 파싱
    items = []
    skipped = []
    for f in today_files:
        item = parse_md(f)
        if is_noise(item):
            skipped.append(item["title"][:40])
        else:
            items.append(item)

    # 중복 제거
    items = dedupe(items)

    if skipped:
        print(f"🚫 노이즈 제외 {len(skipped)}건:")
        for s in skipped:
            print(f"   · {s}")

    print(f"✅ 발송 대상: {len(items)}건\n")

    msg = build_message(items, target_date)

    print("=" * 52)
    print(msg)
    print("=" * 52)
    print()

    if dry_run:
        print("-- DRY RUN: 발송 생략 --")
        return

    send_telegram(msg)


if __name__ == "__main__":
    main()
