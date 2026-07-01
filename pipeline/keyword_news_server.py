"""키워드 뉴스 v2 — 이슈 레이더 + 섹터 심화 교차키워드.

Layer1(radar): 시장이 오늘 반응한 이슈를 역포착 (특징주·정책·증권가). 등록 안 한 이슈도 잡음.
Layer2(cross): 핵심 7섹터 A×B 교차쿼리로 정밀 심화 추적.
공통: URL·제목 dedup(당일 state 누적) + 규칙 광고필터.

원문 낱개로 안 쏜다. 쿼리당 '묶음' 1파일 → 대시보드 AI 다이제스트로 정리.
매일 2회 cron(장전 08:20 / 마감후 15:40).
실행: python3 keyword_news.py
"""
import sys
import re
import html
import json
import urllib.parse
from datetime import datetime
from pathlib import Path

import feedparser

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from api import user_store

OUT_BASE = ROOT / "output" / "md"
CFG_PATH = ROOT / "news_keywords.json"
PER_KW = 18


def _clean(t):
    return html.unescape(re.sub(r"<[^>]+>", "", t or "")).strip()


def _split_src(title):
    """구글뉴스 '제목 - 출처' 분리."""
    if " - " in title:
        base, tail = title.rsplit(" - ", 1)
        return base.strip(), tail.strip()
    return title, ""


def _norm_title(title):
    """dedup용 제목 정규화 (공백·특수문자 제거)."""
    return re.sub(r"[^가-힣A-Za-z0-9]", "", title or "")


def _load_cfg():
    try:
        return json.loads(CFG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] news_keywords.json 로드 실패({e}) → user_store 키워드만 사용")
        return {}


def _build_queries(cfg):
    """(query, tag) 목록 생성. tag=레이더/심화/단독/멤버."""
    queries = []
    seen_q = set()

    def add(q, tag):
        q = q.strip()
        if q and q not in seen_q:
            seen_q.add(q)
            queries.append((q, tag))

    # Layer1 — 이슈 레이더
    for group in (cfg.get("radar") or {}).values():
        for kw in group:
            add(kw, "레이더")
    # Layer2 — 섹터 심화 A×B 교차
    for sec in (cfg.get("cross") or {}).values():
        for a in sec.get("a", []):
            for b in sec.get("b", []):
                add(f"{a} {b}", "심화")
    # 단독 매크로
    for kw in cfg.get("solo") or []:
        add(kw, "단독")
    # 멤버십 커스텀 키워드 (user_store)
    try:
        for kw in user_store.get_all_keywords():
            add(kw, "멤버")
    except Exception as e:
        print(f"[WARN] user_store 키워드 로드 실패: {e}")
    return queries


def _make_ad_filter(cfg):
    af = cfg.get("ad_filter") or {}
    title_bl = af.get("title_blacklist") or []
    src_bl = af.get("source_blacklist") or []

    def is_ad(title, src):
        tl = title.lower()
        if any(w.lower() in tl for w in title_bl):
            return True
        if any(s.lower() in (src or "").lower() for s in src_bl):
            return True
        return False

    return is_ad


def _load_seen(news_dir, today):
    """당일 이미 수집한 URL·제목 state 로드 (교차/재실행 중복 차단)."""
    p = news_dir / f".seen_{today}.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return set(d.get("links", [])), set(d.get("titles", [])), p
    except Exception:
        return set(), set(), p


def _save_seen(p, links, titles):
    try:
        p.write_text(json.dumps({"links": sorted(links), "titles": sorted(titles)},
                                ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[WARN] seen state 저장 실패: {e}")


def _sector_of(cfg, kw):
    """심화 쿼리('A B')가 어느 섹터인지 역매핑."""
    for sec, m in (cfg.get("cross") or {}).items():
        for b in m.get("b", []):
            if b in kw:
                return sec
    return "기타"


def _build_digest(cfg, now, radar, sectors):
    """멤버십용 '오늘 놓치면 안 되는 이슈' 다이제스트 텍스트 생성."""
    slot = "장전" if now.hour < 12 else "마감후"
    lines = [f"🔔 *오늘 놓치면 안 되는 이슈* · {now.strftime('%m-%d %H:%M')} ({slot})"]

    if radar:
        lines.append("\n🔥 *이슈 레이더*")
        for kw in radar:
            heads = radar[kw][:1]  # 키워드당 대표 1건
            for h in heads:
                lines.append(f"· \\[{kw}] {h}")

    if sectors:
        lines.append("\n📊 *섹터 심화*")
        for sec in sectors:
            for h in sectors[sec][:2]:  # 섹터당 2건
                lines.append(f"· \\[{sec}] {h}")

    return "\n".join(lines)


def _send_digest(text):
    """활성 멤버(news 설정 ON)에게 다이제스트 발송. 실패해도 크롤 중단 없음."""
    try:
        from notifiers import telegram_sender_v2 as ts
        from api import user_store

        async def _run():
            for u in user_store.get_all_users():
                if not u.get("enabled"):
                    continue
                if not user_store.get_settings(u["id"]).get("news"):
                    continue
                await ts._send_to_user(u, text)

        ts._run_async(_run())
        print("다이제스트 텔레 발송 완료")
    except Exception as e:
        print(f"[WARN] 다이제스트 발송 실패: {e}")


def collect():
    cfg = _load_cfg()
    queries = _build_queries(cfg)
    is_ad = _make_ad_filter(cfg)

    now = datetime.now()
    today, hhmm = now.strftime("%Y-%m-%d"), now.strftime("%H%M")
    news_dir = OUT_BASE / today / "news"
    news_dir.mkdir(parents=True, exist_ok=True)

    seen_links, seen_titles, seen_path = _load_seen(news_dir, today)
    made = ad_skip = dup_skip = 0
    radar_new = {}    # {키워드: [제목...]}  이번 run 신규만
    sector_new = {}   # {섹터: [제목...]}

    for kw, tag in queries:
        url = ("https://news.google.com/rss/search?q="
               + urllib.parse.quote(kw) + "&hl=ko&gl=KR&ceid=KR:ko")
        feed = feedparser.parse(url)
        rows, new_titles = [], []
        for e in feed.entries[:PER_KW]:
            title, src = _split_src(_clean(e.get("title", "")))
            link = e.get("link", "")
            if getattr(e, "source", None) and getattr(e.source, "title", None):
                src = e.source.title
            if not title:
                continue
            ntitle = _norm_title(title)
            # dedup: 링크 or 정규화 제목 (당일 누적 + 이번 run)
            if (link and link in seen_links) or (ntitle and ntitle in seen_titles):
                dup_skip += 1
                continue
            # 광고필터
            if is_ad(title, src):
                ad_skip += 1
                continue
            seen_links.add(link)
            seen_titles.add(ntitle)
            desc = _clean(e.get("summary", ""))
            try:
                pub = datetime(*e.published_parsed[:6]).strftime("%m-%d %H:%M")
            except Exception:
                pub = today
            line = f"- {title} ({src}, {pub})"
            if desc and desc[:20] != title[:20]:
                line += f"\n  {desc[:160]}"
            rows.append(line)
            new_titles.append(title)
        if not rows:
            continue
        # 다이제스트용 신규 제목 수집
        if tag == "레이더":
            radar_new[kw] = new_titles
        elif tag == "심화":
            sec = _sector_of(cfg, kw)
            sector_new.setdefault(sec, []).extend(new_titles)
        body = "\n".join(rows)
        md = (
            f"# [{tag}] {kw}\n\n"
            f"- **출처**: 구글뉴스\n"
            f"- **날짜**: {now.strftime('%Y-%m-%d %H:%M')}\n"
            f"- **키워드**: {kw}\n"
            f"- **분류**: {tag}\n"
            f"- **관련종목**: -\n\n"
            f"## 본문 요약\n\n{body}\n"
        )
        safe_kw = kw.replace("/", "_").replace(" ", "·")
        (news_dir / f"{today}_{hhmm}_[{tag}]{safe_kw}_kw.md").write_text(md, encoding="utf-8")
        made += 1

    _save_seen(seen_path, seen_links, seen_titles)
    print(f"묶음 생성: {made}개 (쿼리 {len(queries)}) / 중복스킵 {dup_skip} / 광고스킵 {ad_skip}")

    # 다이제스트 텔레 발송 (신규 이슈 있을 때만)
    if cfg.get("telegram_digest", True) and (radar_new or sector_new):
        _send_digest(_build_digest(cfg, now, radar_new, sector_new))


if __name__ == "__main__":
    collect()
