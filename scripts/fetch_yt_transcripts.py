"""
유튜브 전체 자막 추출기 v2 -youtube-transcript-api 기반
한국 10개 + 해외 5개 전체 스크립트 → 개별 위키 파일 저장

사용법:
    python scripts/fetch_yt_transcripts.py           # 전체 15개
    python scripts/fetch_yt_transcripts.py --id KR-01
"""

import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
from youtube_transcript_api.formatters import TextFormatter

OUT_DIR = Path(__file__).parent.parent / "wiki" / "외부인사이트" / "레퍼런스_영상"

# ── 분석 대상 -조회수 상위 선별 ────────────────────────────────
VIDEOS = [
    # ══ 한국 채널 10개 ══
    {
        "id": "KR-01", "channel": "어비월드",
        "vid": "kAwsc5oc2Og",
        "memo": "AI 직원 5명 채용, 인건비 0원 실화 (Manus Skills) | 14만뷰",
    },
    {
        "id": "KR-02", "channel": "월텍남",
        "vid": "GzGcQzMo_Rw",
        "memo": "업무 전부 자동화, 구글의 역대급 AI 에이전트 | 20만뷰",
    },
    {
        "id": "KR-03", "channel": "일잘러 장피엠",
        "vid": "c-a4GBOxhXQ",
        "memo": "나의 AI 에이전트 전환기 (클로드 코드, 오픈클로) | 16만뷰",
    },
    {
        "id": "KR-04", "channel": "CONNECT AI LAB",
        "vid": "qDKHEXZ8p6w",
        "memo": "AI 직원 10명이 24시간 일하는 완전 무료 프로그램 | 10만뷰",
    },
    {
        "id": "KR-05", "channel": "CONNECT AI LAB",
        "vid": "Jas_74VZiPE",
        "memo": "AI로 돈 버는 게 막막하다면 무조건 보세요 (NotebookLM+안티그래비티) | 9만뷰",
    },
    {
        "id": "KR-06", "channel": "CONNECT AI LAB",
        "vid": "Gts_7nuf9dQ",
        "memo": "이게 진짜 자동화, AI 직원 10명이 동시에 연구/앱 개발 | 8.7만뷰",
    },
    {
        "id": "KR-07", "channel": "콜잇 AI",
        "vid": "tv8Dzpd9B6s",
        "memo": "구글이 공개한 미친 AI, 디자이너 없이 혼자 마케팅 | 8.6만뷰",
    },
    {
        "id": "KR-08", "channel": "CONNECT AI LAB",
        "vid": "BZynp51fBRU",
        "memo": "대화형 AI 시대는 끝났다, 구글 에이전트 유튜브 수익화 자동화 | 6.5만뷰",
    },
    {
        "id": "KR-09", "channel": "와이스트릿",
        "vid": "66coEEnAdSk",
        "memo": "직원 5명 공짜로 고용한 셈, 커서AI 프로그래머 세상 | 5만뷰",
    },
    {
        "id": "KR-10", "channel": "CONNECT AI LAB",
        "vid": "5KQgXA1hj_g",
        "memo": "구글 AI 자동화: 스티치+안티그래비티로 5인분 혼자 | 3만뷰",
    },
    # ══ 해외 채널 5개 ══
    {
        "id": "EN-01", "channel": "Futurepedia",
        "vid": "EH5jx5qPabU",
        "memo": "From Zero to First AI Agent in 25 Min (No Coding) | 373만뷰",
    },
    {
        "id": "EN-02", "channel": "Liam Ottley",
        "vid": "w0H1-b044KY",
        "memo": "How to Build & Sell AI Agents: Ultimate Beginner Guide | 282만뷰",
    },
    {
        "id": "EN-03", "channel": "Nate Herk",
        "vid": "Ey18PDiaAYI",
        "memo": "Build & Sell n8n AI Agents (8+ Hour Course, No Code) | 169만뷰",
    },
    {
        "id": "EN-04", "channel": "Dan Martell",
        "vid": "w-XPlC3a2oI",
        "memo": "How to Build a $10M Solo AI Business (Zero Coding) | 66만뷰",
    },
    {
        "id": "EN-05", "channel": "Chris Koerner",
        "vid": "AA-EL571oG4",
        "memo": "I Built an AI Agent That Works While I Sleep | 38만뷰",
    },
]


def fetch_transcript(vid_id: str) -> tuple[list[dict], str]:
    """
    자막 가져오기. (segments, lang) 반환.
    한국어 → 영어 → 자동생성 순으로 시도.
    v1.x 신 API: YouTubeTranscriptApi() 인스턴스 → .list() → .find_transcript()
    """
    api = YouTubeTranscriptApi()

    try:
        tlist = api.list(vid_id)
    except Exception as e:
        return [], f"list_error:{e}"

    # 한국어 우선
    for langs in [["ko", "ko-KR"], ["en", "en-US", "en-GB"]]:
        try:
            t = tlist.find_transcript(langs)
            segs = t.fetch()
            raw = [{"start": s.start, "duration": s.duration, "text": s.text}
                   for s in segs]
            return raw, t.language_code
        except Exception:
            pass

    # 어떤 언어든 첫 번째
    try:
        for t in tlist:
            segs = t.fetch()
            raw = [{"start": s.start, "duration": s.duration, "text": s.text}
                   for s in segs]
            return raw, t.language_code
    except Exception:
        pass

    return [], "none"


def segments_to_sections(segments: list[dict]) -> list[dict]:
    """
    타임스탬프 기반으로 섹션 자동 분할.
    30초 이상 공백이면 새 섹션으로 간주.
    """
    if not segments:
        return []

    sections = []
    buf = [segments[0]]
    for prev, cur in zip(segments, segments[1:]):
        gap = cur["start"] - prev["start"]
        if gap > 30:
            sections.append(buf)
            buf = []
        buf.append(cur)
    if buf:
        sections.append(buf)
    return sections


def fmt_time(sec: float) -> str:
    sec = int(sec)
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def save_wiki(video: dict, segments: list[dict], lang: str):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_ch = re.sub(r"[^\w가-힣]", "_", video["channel"])
    fname = OUT_DIR / f"ref_{video['id']}_{safe_ch}.md"
    date_str = datetime.now().strftime("%Y-%m-%d")
    url = f"https://www.youtube.com/watch?v={video['vid']}"

    # 전체 텍스트
    full_text = " ".join(s["text"].replace("\n", " ") for s in segments)
    total_sec = segments[-1]["start"] if segments else 0
    total_time = fmt_time(total_sec)

    # 섹션 분할
    sections = segments_to_sections(segments)

    lines = [
        f"# 레퍼런스 분석: {video['id']} -{video['channel']}",
        "",
        f"> 수집일: {date_str}  |  자막언어: {lang}  |  총 길이: ~{total_time}",
        f"> URL: {url}",
        f"> 메모: {video['memo']}",
        "",
        "---",
        "",
        "## 전체 자막 (타임스탬프 + 원문)",
        "",
        "> 이 섹션이 핵심 -실제 스크립트 전체",
        "",
    ]

    for seg in segments:
        t = fmt_time(seg["start"])
        text = seg["text"].replace("\n", " ").strip()
        lines.append(f"`{t}` {text}")

    lines += [
        "",
        "---",
        "",
        "## 섹션별 구조 (30초 간격 자동 분할)",
        "",
    ]

    for i, sec in enumerate(sections, 1):
        start_t = fmt_time(sec[0]["start"])
        end_t = fmt_time(sec[-1]["start"])
        sec_text = " ".join(s["text"].replace("\n", " ") for s in sec)
        lines += [
            f"### 섹션 {i}  [{start_t} ~ {end_t}]",
            "",
            sec_text,
            "",
        ]

    lines += [
        "---",
        "",
        "## 구조 분석 (나중에 채우기)",
        "",
        "| 항목 | 내용 |",
        "|------|------|",
        "| 오프닝 첫 문장 | |",
        "| 훅 방식 | |",
        "| 본론 흐름 | |",
        "| 클라이맥스 타이밍 | |",
        "| CTA | |",
        "| 잘된 이유 | |",
        "| 우리 영상에 쓸 것 | |",
        "",
    ]

    fname.write_text("\n".join(lines), encoding="utf-8")
    return fname


def save_index(results: list[dict]):
    idx = OUT_DIR / "인덱스.md"
    date_str = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "# AI 직원/에이전트 레퍼런스 영상 -인덱스",
        "",
        f"> 수집일: {date_str}",
        "",
        "## 한국 채널",
        "",
        "| ID | 채널 | 메모 | 자막 | 파일 |",
        "|----|------|------|------|------|",
    ]
    for r in results:
        if r["id"].startswith("KR"):
            ok = "OK" if r["segs"] > 0 else "없음"
            lines.append(
                f"| {r['id']} | {r['channel']} | {r['memo'][:40]} "
                f"| {r['segs']}줄({ok}) | [{r['id']}]({r.get('fname','')}) |"
            )
    lines += [
        "",
        "## 해외 채널",
        "",
        "| ID | 채널 | 메모 | 자막 | 파일 |",
        "|----|------|------|------|------|",
    ]
    for r in results:
        if r["id"].startswith("EN"):
            ok = "OK" if r["segs"] > 0 else "없음"
            lines.append(
                f"| {r['id']} | {r['channel']} | {r['memo'][:40]} "
                f"| {r['segs']}줄({ok}) | [{r['id']}]({r.get('fname','')}) |"
            )
    idx.write_text("\n".join(lines), encoding="utf-8")
    print(f"[인덱스] {idx}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", help="특정 ID만 (예: KR-01)")
    args = ap.parse_args()

    targets = VIDEOS
    if args.id:
        targets = [v for v in VIDEOS if v["id"] == args.id]
        if not targets:
            print(f"ID '{args.id}' 없음")
            sys.exit(1)

    results = []
    for i, video in enumerate(targets, 1):
        print(f"\n[{i}/{len(targets)}] {video['id']} {video['channel']}")
        try:
            segs, lang = fetch_transcript(video["vid"])
            print(f"  자막: {len(segs)}줄  언어: {lang}")
            if segs:
                fname = save_wiki(video, segs, lang)
                print(f"  저장: {fname.name}")
            else:
                fname = None
                print(f"  자막 없음 - 파일 미저장")
            results.append({**video, "segs": len(segs), "lang": lang,
                            "fname": fname.name if fname else ""})
        except Exception as e:
            print(f"  오류: {e}")
            results.append({**video, "segs": 0, "lang": "err", "fname": ""})
        time.sleep(1)

    save_index(results)

    print("\n" + "=" * 60)
    print("완료 요약")
    print("=" * 60)
    for r in results:
        status = "OK" if r["segs"] > 0 else "자막없음"
        print(f"  {r['id']} {r['channel'][:18]:18s} | {r['segs']:5d}줄 | {status}")


if __name__ == "__main__":
    main()
