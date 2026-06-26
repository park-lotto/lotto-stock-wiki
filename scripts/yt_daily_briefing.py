"""
매일 아침 자동 실행 — 미국증시 라이브 브리핑 생성
1. @futuresnow 채널 최신 스트림 URL 탐지
2. 한국어 자막 다운로드
3. Gemini API로 브리핑 생성
4. out/briefing_YYYYMMDD.md 저장
"""
import re, os, sys, json, subprocess, tempfile
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "out")
ENV_PATH = os.path.join(ROOT, ".env")
CHANNEL_URL = "https://www.youtube.com/@futuresnow/streams"

BRIEFING_PROMPT = """너는 글로벌 매크로 경제와 미국 증시를 분석하는 '수석 투자 전략가'이자 '데일리 시황 에디터'이다.

제공된 미국 증시 라이브 영상의 대본(트랜스크립트)을 바탕으로, 오늘 시장에서 일어난 모든 핵심 정보를 빠짐없이 담은 [데일리 마켓 브리핑 보고서]를 작성해 줘.

투자자들이 오늘 장의 '돈의 흐름'과 '리스크'를 명확히 파악할 수 있도록, 아래의 5가지 섹션에 맞춰 최대한 구체적인 수치와 맥락을 포함해 정리해야 해.

---

### [보고서 작성 구조]

1. 📊 시장 전반적 분위기 및 매크로 지표
   - **지수 종가 및 장세:** 다우, 나스닥, S&P 500, 러셀2000 등 주요 지수의 마감 분위기와 장중 변동성(휩소 유무).
   - **시장 내부 수치:** 당일 상승 종목수 vs 하락 종목수 비율, 공포와 탐욕 지수(공탐 수치), 빅스(VIX) 지수, 국채 금리 및 달러 인덱스 동향.
   - **핵심 경제 지표:** 당일 발표된 매크로 지표(PCE, CPI, GDP, 실업수당, 내구재 등)의 구체적인 수치와 시장 예상치 대비 결과, 이에 대한 시장의 해석.
   - **연준 위원 발언:** 영상에 등장한 연준 인사(파월, 윌리엄스, 굴스비 등)의 발언 요약 및 금리 전망 변화.

2. 🛒 섹터별 흐름 및 돈의 이동 (순환매 분석)
   - **강세 섹터/테마:** 오늘 가장 돈이 몰리고 상승세를 탄 섹터와 그 상승 원인.
   - **약세 섹터/테마:** 오늘 부진했거나 급락한 섹터와 그 하락 원인.
   - **시장의 서사(내러티브):** 순환매(Rotation)의 방향성 기술.

3. 📢 주요 기업별 핵심 이슈 및 뉴스 (B2B / B2C)
   - **실적 및 가이던스 발표 기업:** 당일 실적을 발표한 기업의 수치(매출, EPS)와 시장 반응.
   - **빅테크 및 주요 개별 기업 이슈:** 주요 기업의 당일 뉴스(가격 인상, 인력 이탈, 규제, 투자 의견 상/하향 등).
   - **진행자의 기업 해석:** 엇갈리게 해석한 맥락 정리.

4. 🚨 중동/지정학 리스크 및 원자재 속보
   - **중동 및 지정학적 이슈:** 팩트와 [카더라/추론] 구분하여 기록.
   - **원자재 동향:** 유가(WTI, 브렌트유), 금, 은, 천연가스, 리튬 가격 움직임.

5. 🔮 내일 장 주요 스케줄 및 투자자 체크포인트
   - **다음 일정:** 내일 발표될 중요 경제 지표 및 실적 발표 일정.
   - **마켓 한줄평:** 진행자의 한줄 요약 및 투자 멘탈 관리 조언.

---

### [작성 규칙]
- 진행자가 "카더라"라고 언급한 부분은 **[카더라/추론]** 말머리를 달아 기록.
- 맥스페인, 콜/풋 비율, 감마 플립 수치 등 옵션 데이터 수치 정확히 기재.
- 불릿포인트(·), 줄바꿈, 볼드체로 가독성 확보."""


# ── 유틸 ────────────────────────────────────────────────

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def load_api_key():
    with open(ENV_PATH, encoding='utf-8') as f:
        for line in f:
            if line.startswith('GEMINI_API_KEY_2='):
                return line.strip().split('=', 1)[1]
    raise ValueError("GEMINI_API_KEY_2 not found in .env")


# ── Step 1: 최신 스트림 URL 탐지 ────────────────────────

def get_latest_stream_url():
    log("최신 스트림 URL 탐지 중...")
    result = subprocess.run(
        ["python", "-m", "yt_dlp",
         "--flat-playlist", "--playlist-end", "3",
         "--print", "%(url)s|%(title)s|%(upload_date)s|%(live_status)s",
         "--no-update",
         CHANNEL_URL],
        capture_output=True, text=True, encoding='utf-8', errors='replace'
    )
    entries = []
    for line in result.stdout.strip().splitlines():
        if '|' in line and 'youtube.com' in line:
            parts = line.split('|')
            if len(parts) >= 4:
                entries.append({
                    'url': parts[0],
                    'title': parts[1],
                    'date': parts[2],
                    'status': parts[3],
                })

    if not entries:
        raise RuntimeError(f"스트림을 찾지 못했습니다.\nstdout: {result.stdout[:300]}\nstderr: {result.stderr[:300]}")

    # was_live (방송 종료) 우선, 없으면 첫 번째
    for e in entries:
        if e['status'] in ('was_live', 'not_live'):
            log(f"선택: {e['title']} ({e['date']}) — {e['url']}")
            return e['url'], e['title'], e['date']

    e = entries[0]
    log(f"선택(첫번째): {e['title']} ({e['date']}) — {e['url']}")
    return e['url'], e['title'], e['date']


# ── Step 2: 한국어 자막 다운로드 ────────────────────────

def download_subtitles(video_url, tmp_dir):
    log("한국어 자막 다운로드 중...")
    out_template = os.path.join(tmp_dir, "live.%(ext)s")
    result = subprocess.run(
        ["python", "-m", "yt_dlp",
         "--write-auto-subs", "--sub-langs", "ko",
         "--skip-download", "--no-update",
         "-o", out_template,
         video_url],
        capture_output=True, text=True, encoding='utf-8', errors='replace'
    )
    vtt_path = os.path.join(tmp_dir, "live.ko.vtt")
    if not os.path.exists(vtt_path):
        raise RuntimeError(f"자막 파일 없음\nstderr: {result.stderr[:500]}")
    size = os.path.getsize(vtt_path)
    log(f"자막 다운로드 완료: {size:,} bytes")
    return vtt_path


# ── Step 3: VTT 파싱 + 한국어 필터링 ───────────────────

def parse_vtt(vtt_path):
    with open(vtt_path, encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    segments = []
    current_time, current_text = '', []

    for line in lines:
        line = line.strip()
        if '-->' in line:
            if current_text and current_time:
                text = ' '.join(current_text).strip()
                if text:
                    segments.append((current_time, text))
            current_time = line.split('-->')[0].strip()[:8]
            current_text = []
        elif line and not line.isdigit() and not line.startswith('WEBVTT') and not line.startswith('NOTE'):
            clean = re.sub(r'<[^>]+>', '', line).strip()
            if clean:
                current_text.append(clean)

    # 중복 제거
    unique, prev = [], ''
    for t, txt in segments:
        if txt != prev:
            unique.append((t, txt))
            prev = txt

    # 한국어 필터
    def is_korean(text):
        kor = len(re.findall(r'[가-힣]', text))
        return kor > 5 or (kor / max(len(text.replace(' ', '')), 1)) > 0.3

    filtered = []
    prev = ''
    for t, txt in unique:
        if not is_korean(txt): continue
        if len(txt) < 8: continue
        if txt[:10] == prev[:10]: continue
        filtered.append((t, txt))
        prev = txt

    # 5분 블록 압축
    def t2s(t):
        try:
            h, m, s = t.split(':')
            return int(h)*3600 + int(m)*60 + int(s)
        except:
            return 0

    blocks = {}
    for t, txt in filtered:
        sec = t2s(t)
        bucket = (sec // 300) * 300
        key = f"{bucket//3600:02d}:{(bucket%3600)//60:02d}"
        blocks.setdefault(key, []).append(txt)

    parts = []
    for key in sorted(blocks):
        combined = ' '.join(blocks[key])[:600]
        parts.append(f"[{key}] {combined}")

    transcript = '\n'.join(parts)
    log(f"파싱 완료: {len(filtered)}개 세그먼트 → {len(parts)}개 블록, {len(transcript):,}자")
    return transcript


# ── Step 4: Gemini API 호출 ──────────────────────────────

def call_gemini(transcript, api_key):
    from google import genai
    from google.genai import types

    log("Gemini API 호출 중...")
    client = genai.Client(api_key=api_key)

    message = f"[트랜스크립트]\n{transcript}\n\n위 내용을 바탕으로 [데일리 마켓 브리핑 보고서]를 작성해 주세요."

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=message,
        config=types.GenerateContentConfig(
            system_instruction=BRIEFING_PROMPT,
            temperature=0.3,
            max_output_tokens=8192,
        )
    )
    log(f"Gemini 응답 완료: {len(response.text):,}자")
    return response.text


# ── Step 5: 저장 ─────────────────────────────────────────

def save_briefing(content, video_url, title, date_str):
    os.makedirs(OUT_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    out_path = os.path.join(OUT_DIR, f"briefing_{today}_미국증시.md")
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(f"# 데일리 마켓 브리핑 — {today}\n\n")
        f.write(f"*소스: [{title}]({video_url})*\n\n")
        f.write(content)
    log(f"저장 완료: {out_path}")
    return out_path


# ── 메인 ─────────────────────────────────────────────────

def main():
    log("=== 데일리 브리핑 자동화 시작 ===")
    try:
        api_key = load_api_key()
        video_url, title, date_str = get_latest_stream_url()

        with tempfile.TemporaryDirectory() as tmp_dir:
            vtt_path = download_subtitles(video_url, tmp_dir)
            transcript = parse_vtt(vtt_path)

        briefing = call_gemini(transcript, api_key)
        out_path = save_briefing(briefing, video_url, title, date_str)

        log("=== 완료 ===")
        print(f"\n{out_path}")
        return out_path

    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    main()
