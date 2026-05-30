"""
주식 유튜브 핫클립 자막 + 썸네일 분석기
신사임당, 달란트투자 등 상위 채널 최신 인기 영상 뽑기

사용법:
    python scripts/fetch_yt_stock_reference.py
    python scripts/fetch_yt_stock_reference.py --id SS-01
"""
import argparse, re, sys, time
from datetime import datetime
from pathlib import Path
from youtube_transcript_api import YouTubeTranscriptApi

sys.stdout.reconfigure(encoding='utf-8')

OUT_DIR = Path(__file__).parent.parent / "wiki" / "외부인사이트" / "주식_레퍼런스"

# ── 최근 핫클립 선별 (조회수 + 채널 기준) ────────────────────────
VIDEOS = [
    # ══ 신사임당 ══
    {
        "id": "SS-01", "channel": "신사임당",
        "vid": "DMc6AiXXPKk",
        "title": "로봇은 그냥 이 '2개'만 사모아라 6월 미친듯이 올라갑니다 (이승조 무극선생 3부)",
        "views": "6.7만", "days_ago": 8,
        "thumbnail_text": "로봇은 그냥 이'2개'만 사모아라 / 6월, 미친듯이 올라갑니다다",
    },
    {
        "id": "SS-02", "channel": "신사임당",
        "vid": "zqBbJUwI0TY",
        "title": "6월 주도주 싹다 바뀐다 현금으로 지금 기판주 사세요! 삼성전기랑 같이 100배 오릅니다",
        "views": "5.4만", "days_ago": 1,
        "thumbnail_text": "현금으로 싹다 기판주 사세요 삼성전기랑 같이 100배 오릅니다",
    },
    {
        "id": "SS-03", "channel": "신사임당",
        "vid": "fvZ5OQYV2Bk",
        "title": "1억 있으면 40% 40%나 넘어라 역대급 폭등 신호탄 포착",
        "views": "4.2만", "days_ago": 5,
        "thumbnail_text": "1억 있으면 40% 40%나 넘어라 역대급 폭등 신호탄 포착",
    },
    {
        "id": "SS-04", "channel": "신사임당",
        "vid": "XqWM4PdV7vY",
        "title": "30만전자·220만닉스 확장 반도체 타고 코스피 1만 됩니다",
        "views": "3.8만", "days_ago": 3,
        "thumbnail_text": "30만전자·220만닉스 확장 / 반도체 타고 코스피 1만 됩니다",
    },
    # ══ 달란트투자 ══
    {
        "id": "DT-01", "channel": "달란트투자",
        "vid": "mBgR5fQS9LA",
        "title": "2차전지 폭등 임박했습니다 [투자자 필수 시청]",
        "views": "8.2만", "days_ago": 4,
        "thumbnail_text": "2차전지 폭등 임박했습니다",
    },
    # ══ 경제 원탑 ══
    {
        "id": "ET-01", "channel": "경제원탑",
        "vid": "Ks0WP8GiZyI",
        "title": "삼성전자 난리난 진짜 이유. 단 한 주라도 있다면 이렇게 하세요",
        "views": "6.1만", "days_ago": 6,
        "thumbnail_text": "삼성전자 난리난 진짜 이유 / 단 한 주라도 있다면 이렇게",
    },
]

def fmt_time(sec: float) -> str:
    sec = int(sec)
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def fetch_transcript(vid_id: str):
    api = YouTubeTranscriptApi()
    try:
        tlist = api.list(vid_id)
        for langs in [["ko", "ko-KR"], ["en"]]:
            try:
                t = tlist.find_transcript(langs)
                segs = t.fetch()
                return [{"start": s.start, "text": s.text} for s in segs], t.language_code
            except Exception:
                pass
        for t in tlist:
            segs = t.fetch()
            return [{"start": s.start, "text": s.text} for s in segs], t.language_code
    except Exception as e:
        return [], str(e)
    return [], "none"

def analyze_thumbnail(thumbnail_text: str) -> dict:
    """썸네일 텍스트에서 공식 분석"""
    patterns = {
        "숫자_충격": bool(re.search(r'\d+[만억%배]|\d{2,}', thumbnail_text)),
        "시간_압박": bool(re.search(r'6월|5월|다음주|오늘|지금|즉시|임박', thumbnail_text)),
        "행동_촉구": bool(re.search(r'사세요|모으세요|사모아라|하세요', thumbnail_text)),
        "과장_표현": bool(re.search(r'미친|역대급|폭등|난리|완전|무조건', thumbnail_text)),
        "대형종목": bool(re.search(r'삼성|SK|LG|현대|NVIDIA|엔비디아', thumbnail_text)),
    }
    matched = [k for k, v in patterns.items() if v]
    return {"패턴": matched, "공식수": len(matched)}

def save_analysis(video: dict, segs: list, lang: str):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fname = OUT_DIR / f"ref_{video['id']}_{video['channel']}.md"

    full_text = " ".join(s["text"].replace("\n", " ") for s in segs)
    total_sec = segs[-1]["start"] if segs else 0

    thumb_analysis = analyze_thumbnail(video.get("thumbnail_text", ""))

    # 앞 60초 훅 추출
    hook_segs = [s for s in segs if s["start"] < 60]
    hook_text = " ".join(s["text"] for s in hook_segs)

    # 전체 구조 (30초 단위 섹션)
    sections = []
    buf = []
    for s in segs:
        if buf and s["start"] - buf[-1]["start"] > 30:
            sections.append(buf)
            buf = []
        buf.append(s)
    if buf:
        sections.append(buf)

    lines = [
        f"# 주식 레퍼런스: {video['id']} — {video['channel']}",
        "",
        f"> 수집일: {datetime.now().strftime('%Y-%m-%d')}",
        f"> 조회수: {video['views']} ({video['days_ago']}일 전)",
        f"> 자막: {lang} | 총 길이: ~{fmt_time(total_sec)}",
        f"> URL: https://www.youtube.com/watch?v={video['vid']}",
        "",
        "---",
        "",
        "## 제목 + 썸네일 분석",
        "",
        f"**제목**: {video['title']}",
        "",
        f"**썸네일 텍스트**: {video.get('thumbnail_text', '—')}",
        "",
        "**썸네일 공식 분석**:",
    ]
    for p in thumb_analysis["패턴"]:
        lines.append(f"- ✅ {p}")
    lines += [
        f"- **공식 매칭 수**: {thumb_analysis['공식수']}/5",
        "",
        "---",
        "",
        "## 첫 60초 훅 (전체 공식의 핵심)",
        "",
        f"> {hook_text}",
        "",
        "**훅 분석**:",
        f"- 첫 문장 방식: {segs[0]['text'] if segs else '—'}",
        "",
        "---",
        "",
        "## 전체 자막",
        "",
    ]
    for seg in segs:
        lines.append(f"`{fmt_time(seg['start'])}` {seg['text'].replace(chr(10), ' ')}")

    lines += [
        "",
        "---",
        "",
        "## 섹션별 흐름",
        "",
    ]
    for i, sec in enumerate(sections, 1):
        t0 = fmt_time(sec[0]["start"])
        t1 = fmt_time(sec[-1]["start"])
        txt = " ".join(s["text"].replace("\n", " ") for s in sec)
        lines += [f"### 섹션 {i} [{t0}~{t1}]", "", txt[:400], ""]

    lines += [
        "---",
        "",
        "## 우리 영상에 쓸 것",
        "",
        "| 항목 | 벤치마킹 포인트 |",
        "|------|---------------|",
        "| 제목 공식 | |",
        "| 썸네일 공식 | |",
        "| 훅 방식 | |",
        "| 클라이맥스 타이밍 | |",
        "| STOCK BRAIN 연결 | |",
        "",
    ]

    fname.write_text("\n".join(lines), encoding="utf-8")
    return fname

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", help="특정 ID만 (예: SS-01)")
    args = ap.parse_args()
    targets = VIDEOS if not args.id else [v for v in VIDEOS if v["id"] == args.id]

    print(f"\n주식 유튜브 핫클립 분석 — {len(targets)}개\n{'='*50}")
    for i, video in enumerate(targets, 1):
        print(f"\n[{i}/{len(targets)}] {video['id']} {video['channel']} | {video['views']} | {video['days_ago']}일 전")
        print(f"  제목: {video['title'][:50]}...")
        thumb = analyze_thumbnail(video.get("thumbnail_text", ""))
        print(f"  썸네일 공식: {thumb['패턴']} ({thumb['공식수']}/5)")
        segs, lang = fetch_transcript(video["vid"])
        print(f"  자막: {len(segs)}줄 ({lang})", end=" ")
        if segs:
            fname = save_analysis(video, segs, lang)
            print(f"→ {fname.name}")
        else:
            print("→ 자막 없음")
        time.sleep(1)

    print(f"\n{'='*50}")
    print(f"저장 위치: {OUT_DIR}")

if __name__ == "__main__":
    main()
