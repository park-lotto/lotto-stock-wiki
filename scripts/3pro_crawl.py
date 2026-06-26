"""
삼프로TV(@3protv) 3시간 주기 크롤링 + Gemini 분석
- 새 영상 감지 → 자막 다운로드 → Gemini 요약 → wiki/insights/3pro/ 저장
"""
import re, os, sys, json, subprocess, tempfile
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

ROOT       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(ROOT, "pipeline", "3pro_state.json")
OUT_DIR    = os.path.join(ROOT, "wiki", "insights", "3pro")
ENV_PATH   = os.path.join(ROOT, ".env")
CHANNEL_URL = "https://www.youtube.com/@3protv/videos"

# ── 코너별 추출 포커스 ───────────────────────────────────
CORNER_FOCUS = {
    "아침N투자":      "전날 미국시장 요약 + 당일 주목 섹터 + 수급 방향 + 환율",
    "클로징벨":       "지수 마감 수치 + 외국인/기관/개인 수급 + 섹터별 등락 + 내일 변수",
    "여의도 인사이트": "증권사 리포트 내용 + 목표주가 변화 + 전문가 전략 근거",
    "월가 뉴스레터":   "나스닥/SOX 흐름 + 빅테크 실적/주가 + 한국 연관 종목",
    "마켓 인사이드":   "운용사 매크로 시각 + 포트폴리오 전략 + 리스크 요인",
    "더블":          "리스크 관리 + 변동성 대응 전략 + 헤지 방법",
    "주린이 구조대":   "종목 상담 내용 + 개인투자자 실수 패턴 + 교육 포인트",
    "크립토":         "BTC/ETH 가격 + ETF 동향 + 규제 이슈",
    "뉴스3":          "대형 공시/이벤트 팩트 + 시장 영향",
    "기본":           "핵심 주제 + 언급 종목 + 전문가 시각",
}

GEMINI_SYSTEM = """당신은 한국 주식시장 전문 분석가이자 '종목 인텔리전스 에디터'다.
삼프로TV 영상 자막에서 투자에 활용 가능한 모든 정보를 정확하게 추출한다.

[주의사항]
- 자막은 STT 자동변환이므로 오인식이 있다. 문맥으로 보정하라.
  예: '필반' → 필라델피아 반도체 지수(SOX), '삼전닉스' → 삼성전자+SK하이닉스
- >> 기호는 화자 전환 표시다.
- 자막에 없는 내용을 절대 추가하지 마라.
- 불분명한 수치는 '~'로 표기하라."""

def make_prompt(title: str, corner: str, transcript: str) -> str:
    focus = CORNER_FOCUS.get(corner, CORNER_FOCUS["기본"])
    return f"""[영상 정보]
제목: {title}
코너: [{corner}]
날짜: {datetime.now().strftime('%Y-%m-%d')}

[이 코너 핵심 추출 포커스]
{focus}

[자막 트랜스크립트]
{transcript}

---
위 자막을 분석하여 아래 JSON 형식으로 정확히 출력하라.
자막에 없는 내용은 null로 표기하라.

{{
  "summary": "영상 핵심 주제 3줄 요약",
  "corner_type": "{corner}",
  "market_data": {{
    "kospi": "코스피 수치/등락",
    "kosdaq": "코스닥 수치/등락",
    "usd_krw": "달러원 환율",
    "us_markets": "미국 지수 언급",
    "other": "기타 지표"
  }},
  "supply_demand": {{
    "foreigner": "외국인 매매 방향 + 금액",
    "institution": "기관 매매 방향 + 금액",
    "individual": "개인 매매 방향 + 금액",
    "hot_sectors": "수급 몰린 섹터"
  }},
  "sectors": [
    {{"name": "섹터명", "view": "긍정/중립/부정", "reason": "이유", "key_stocks": ["종목1","종목2"]}}
  ],
  "stocks": [
    {{
      "name": "종목명",
      "code": "종목코드(있으면)",
      "context": "언급 맥락",
      "direction": "매수/매도/중립/단순언급",
      "reason": "근거",
      "numbers": "목표가/PER/EPS/수익률 등 수치"
    }}
  ],
  "macro_events": [
    {{"event": "이벤트명", "detail": "내용", "market_impact": "시장 영향"}}
  ],
  "key_insights": [
    "전문가가 강조한 핵심 포인트 (원문 인용)"
  ],
  "risks": [
    "언급된 리스크 요인"
  ],
  "strategy": "구체적 투자 전략 언급 (없으면 null)",
  "next_watchpoints": [
    "다음에 봐야 할 일정/지표/이벤트"
  ],
  "speaker_opinions": [
    {{"speaker": "진행자/게스트명", "key_opinion": "핵심 주장"}}
  ],
  "unverified": [
    "[카더라] 확인되지 않은 정보"
  ]
}}"""


# ── 유틸 ────────────────────────────────────────────────

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def load_api_key():
    with open(ENV_PATH, encoding='utf-8') as f:
        for line in f:
            if line.startswith('GEMINI_API_KEY_2='):
                return line.strip().split('=', 1)[1]
    raise ValueError("GEMINI_API_KEY_2 not found")

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {"seen_ids": [], "last_run": None}

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def detect_corner(title: str) -> str:
    title_l = title.lower()
    if '아침' in title and '투자' in title: return '아침N투자'
    if '클로징' in title or 'closing' in title_l: return '클로징벨'
    if '여의도' in title and '인사이트' in title: return '여의도 인사이트'
    if '월가' in title or '뉴스레터' in title: return '월가 뉴스레터'
    if '마켓 인사이드' in title or 'market inside' in title_l: return '마켓 인사이드'
    if '더블' in title: return '더블'
    if '주린이' in title: return '주린이 구조대'
    if '크립토' in title or 'crypto' in title_l: return '크립토'
    if '뉴스3' in title or '뉴스 3' in title: return '뉴스3'
    return '기본'


# ── Step 1: 새 영상 탐지 ────────────────────────────────

def get_new_videos(state):
    log("새 영상 탐지 중...")
    result = subprocess.run(
        ["python", "-m", "yt_dlp",
         "--flat-playlist", "--playlist-end", "10",
         "--print", "%(id)s|%(title)s|%(upload_date)s|%(duration_string)s",
         "--no-update", CHANNEL_URL],
        capture_output=True, text=True, encoding='utf-8', errors='replace'
    )
    seen = set(state.get("seen_ids", []))
    new_videos = []
    for line in result.stdout.strip().splitlines():
        if '|' not in line:
            continue
        parts = line.split('|', 3)
        if len(parts) < 4:
            continue
        vid_id, title, date, duration = parts
        vid_id = vid_id.strip()
        if vid_id and vid_id not in seen:
            new_videos.append({
                "id": vid_id,
                "url": f"https://www.youtube.com/watch?v={vid_id}",
                "title": title.strip(),
                "date": date.strip(),
                "duration": duration.strip(),
                "corner": detect_corner(title),
            })
    log(f"새 영상 {len(new_videos)}개 발견")
    return new_videos


# ── Step 2: 자막 다운로드 + 파싱 ────────────────────────

def get_transcript(video_url, tmp_dir):
    out_tpl = os.path.join(tmp_dir, "v.%(ext)s")
    subprocess.run(
        ["python", "-m", "yt_dlp",
         "--write-auto-subs", "--sub-langs", "ko",
         "--skip-download", "--no-update",
         "-o", out_tpl, video_url],
        capture_output=True, text=True, encoding='utf-8', errors='replace'
    )
    vtt_path = os.path.join(tmp_dir, "v.ko.vtt")
    if not os.path.exists(vtt_path):
        return None

    with open(vtt_path, encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    segments, current_time, current_text = [], '', []
    for line in lines:
        line = line.strip()
        if '-->' in line:
            if current_text and current_time:
                text = ' '.join(current_text).strip()
                if text:
                    segments.append((current_time, text))
            current_time = line.split('-->')[0].strip()[:8]
            current_text = []
        elif line and not line.isdigit() and not line.startswith('WEBVTT'):
            clean = re.sub(r'<[^>]+>', '', line).strip()
            if clean:
                current_text.append(clean)

    unique, prev = [], ''
    for t, txt in segments:
        if txt != prev:
            unique.append((t, txt))
            prev = txt

    def is_korean(text):
        kor = len(re.findall(r'[가-힣]', text))
        return kor > 3 or (kor / max(len(text.replace(' ', '')), 1)) > 0.2

    def t2s(t):
        try:
            h, m, s = t.split(':')
            return int(h)*3600 + int(m)*60 + int(s)
        except:
            return 0

    filtered = []
    prev = ''
    for t, txt in unique:
        if not is_korean(txt) or len(txt) < 6: continue
        if txt[:10] == prev[:10]: continue
        filtered.append((t, txt))
        prev = txt

    # 3분 블록 압축 (밀도 높게)
    blocks = {}
    for t, txt in filtered:
        sec = t2s(t)
        bucket = (sec // 180) * 180
        key = f"{bucket//3600:02d}:{(bucket%3600)//60:02d}"
        blocks.setdefault(key, []).append(txt)

    parts = []
    for key in sorted(blocks):
        combined = ' '.join(blocks[key])[:800]
        parts.append(f"[{key}] {combined}")

    return '\n'.join(parts)


# ── Step 3: Gemini 분석 ──────────────────────────────────

def analyze_with_gemini(video, transcript, api_key):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    prompt = make_prompt(video['title'], video['corner'], transcript)

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=GEMINI_SYSTEM,
            temperature=0.2,
            max_output_tokens=4096,
        )
    )
    return response.text


# ── Step 4: 저장 ─────────────────────────────────────────

def save_result(video, raw_result):
    os.makedirs(OUT_DIR, exist_ok=True)
    date_str = video.get('date', datetime.now().strftime('%Y%m%d'))
    safe_title = re.sub(r'[\\/:*?"<>|]', '', video['title'])[:40]
    filename = f"{date_str}_{video['corner']}_{safe_title}.md"
    out_path = os.path.join(OUT_DIR, filename)

    # JSON 추출 시도
    json_match = re.search(r'\{[\s\S]*\}', raw_result)
    parsed = None
    if json_match:
        try:
            parsed = json.loads(json_match.group())
        except:
            pass

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(f"# {video['title']}\n\n")
        f.write(f"- **코너**: [{video['corner']}]\n")
        f.write(f"- **날짜**: {date_str}\n")
        f.write(f"- **길이**: {video['duration']}\n")
        f.write(f"- **URL**: {video['url']}\n\n")
        f.write("---\n\n")

        if parsed:
            # 구조화된 마크다운으로 변환
            if parsed.get('summary'):
                f.write(f"## 핵심 요약\n{parsed['summary']}\n\n")

            if parsed.get('market_data'):
                md = parsed['market_data']
                f.write("## 시장 데이터\n")
                for k, v in md.items():
                    if v and v != 'null':
                        f.write(f"- **{k}**: {v}\n")
                f.write("\n")

            if parsed.get('supply_demand'):
                sd = parsed['supply_demand']
                f.write("## 수급\n")
                for k, v in sd.items():
                    if v and v != 'null':
                        f.write(f"- **{k}**: {v}\n")
                f.write("\n")

            if parsed.get('stocks'):
                f.write("## 언급 종목\n")
                f.write("| 종목 | 방향 | 근거 | 수치 |\n|------|------|------|------|\n")
                for s in parsed['stocks']:
                    name = s.get('name', '')
                    code = s.get('code', '')
                    label = f"{name}({code})" if code and code != 'null' else name
                    direction = s.get('direction', '')
                    reason = s.get('reason', '')
                    numbers = s.get('numbers', '')
                    f.write(f"| {label} | {direction} | {reason} | {numbers} |\n")
                f.write("\n")

            if parsed.get('key_insights'):
                f.write("## 핵심 인사이트\n")
                for ins in parsed['key_insights']:
                    f.write(f"- {ins}\n")
                f.write("\n")

            if parsed.get('risks'):
                f.write("## 리스크\n")
                for r in parsed['risks']:
                    f.write(f"- {r}\n")
                f.write("\n")

            if parsed.get('next_watchpoints'):
                f.write("## 다음 관전 포인트\n")
                for w in parsed['next_watchpoints']:
                    f.write(f"- {w}\n")
                f.write("\n")

            if parsed.get('unverified'):
                f.write("## [카더라]\n")
                for u in parsed['unverified']:
                    f.write(f"- {u}\n")
                f.write("\n")
        else:
            # JSON 파싱 실패 시 원문 저장
            f.write(raw_result)

    return out_path


# ── 메인 ─────────────────────────────────────────────────

def main():
    log("=== 삼프로TV 크롤링 시작 ===")
    try:
        api_key = load_api_key()
        state = load_state()
        new_videos = get_new_videos(state)

        if not new_videos:
            log("새 영상 없음. 종료.")
            state['last_run'] = datetime.now().isoformat()
            save_state(state)
            return

        for video in new_videos:
            log(f"처리 중: [{video['corner']}] {video['title']} ({video['duration']})")
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    transcript = get_transcript(video['url'], tmp)

                if not transcript:
                    log(f"  자막 없음 - 스킵: {video['id']}")
                    state['seen_ids'].append(video['id'])
                    continue

                log(f"  자막 {len(transcript):,}자 → Gemini 분석 중...")
                result = analyze_with_gemini(video, transcript, api_key)
                out_path = save_result(video, result)
                log(f"  저장: {out_path}")
                state['seen_ids'].append(video['id'])

            except Exception as e:
                log(f"  ERROR {video['id']}: {e}")

        state['last_run'] = datetime.now().isoformat()
        # seen_ids 최대 500개 유지
        state['seen_ids'] = state['seen_ids'][-500:]
        save_state(state)
        log("=== 완료 ===")

    except Exception as e:
        log(f"FATAL: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
