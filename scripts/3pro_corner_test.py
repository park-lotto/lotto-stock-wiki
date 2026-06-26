"""
삼프로TV 코너별 1개씩 테스트
"""
import re, os, sys, subprocess, tempfile
from datetime import datetime
sys.stdout.reconfigure(encoding='utf-8')

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR  = os.path.join(ROOT, "wiki", "insights", "3pro")
ENV_PATH = os.path.join(ROOT, ".env")

CORNER_VIDEOS = [
    {"id": "yp_uOWMAvHk", "corner": "아침N투자",      "title": "7월, 삼성전자 실적이 시장을 살릴까?_26.06.26.",                 "duration": "16:14"},
    {"id": "ZGk0LeHt9zg", "corner": "클로징벨",       "title": "[6월 25일 시황] 반도체 강세에도 더 신경써야 할 변수",            "duration": "1:13:01"},
    {"id": "GzqDK8ThQvY", "corner": "여의도 인사이트", "title": "탐욕의 레버리지가 키운 폭락장",                                 "duration": "38:31"},
    {"id": "UNhh4SxifwI", "corner": "크립토 PLUS",    "title": "은행 외환 결제를 둘러싼 리플과 체인링크의 경쟁",                 "duration": "30:16"},
    {"id": "V9l0FaDexLw", "corner": "뉴스3",           "title": "SK하이닉스 분기 10조 돌파…HBM ADR 분석",                       "duration": "29:30"},
    {"id": "bhFa5eU0pFs", "corner": "월가 뉴스레터",   "title": "마이크론·샌디스크 등 메모리 반도체 급등",                       "duration": "43:54"},
    {"id": "UIsAqZPaWqI", "corner": "주린이 구조대",   "title": "코스피 변동성에 속지 않아야 수익 낼 수 있습니다",               "duration": "52:10"},
    {"id": "9lZVpFREQvU", "corner": "마켓 인사이드",   "title": "반도체 독주가 계속될수록 더 조심해야 하는 이유",                 "duration": "43:27"},
]

CORNER_FOCUS = {
    "아침N투자":      "전날 미국시장 요약 + 당일 주목 섹터 + 수급 방향 + 환율",
    "클로징벨":       "지수 마감 수치 + 외국인/기관/개인 수급 + 섹터별 등락 + 내일 변수",
    "여의도 인사이트": "증권사 리포트 내용 + 목표주가 변화 + 전문가 전략 근거",
    "월가 뉴스레터":   "나스닥/SOX 흐름 + 빅테크 실적/주가 + 한국 연관 종목",
    "마켓 인사이드":   "운용사 매크로 시각 + 포트폴리오 전략 + 리스크 요인",
    "더블":           "리스크 관리 + 변동성 대응 전략 + 헤지 방법",
    "주린이 구조대":   "종목 상담 내용 + 개인투자자 실수 패턴 + 교육 포인트",
    "크립토 PLUS":    "BTC/ETH 가격 + ETF 동향 + 규제 이슈",
    "뉴스3":          "대형 공시/이벤트 팩트 + 시장 영향",
}

SYSTEM = """당신은 한국 주식시장 전문 분석가이자 '종목 인텔리전스 에디터'다.
삼프로TV 영상 자막에서 투자에 활용 가능한 모든 정보를 정확하게 추출한다.
- STT 오인식 보정: '필반'→필라델피아반도체(SOX), '삼전닉스'→삼성전자+SK하이닉스
- >> 기호는 화자 전환 표시
- 자막에 없는 내용 절대 추가 금지, 불분명한 수치는 '~'로 표기"""

def log(msg): print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def load_key():
    with open(ENV_PATH, encoding='utf-8') as f:
        for line in f:
            if line.startswith('GEMINI_API_KEY_3='):
                return line.strip().split('=',1)[1]

def get_transcript(url, tmp):
    subprocess.run(
        ["python","-m","yt_dlp","--write-auto-subs","--sub-langs","ko",
         "--skip-download","--no-update","-o",os.path.join(tmp,"v.%(ext)s"),url],
        capture_output=True, text=True, encoding='utf-8', errors='replace'
    )
    vtt = os.path.join(tmp,"v.ko.vtt")
    if not os.path.exists(vtt): return None
    with open(vtt, encoding='utf-8') as f: content = f.read()

    segs, cur_t, cur_txt = [], '', []
    for line in content.split('\n'):
        line = line.strip()
        if '-->' in line:
            if cur_txt and cur_t:
                segs.append((cur_t, ' '.join(cur_txt).strip()))
            cur_t = line.split('-->')[0].strip()[:8]
            cur_txt = []
        elif line and not line.isdigit() and not line.startswith('WEBVTT'):
            c = re.sub(r'<[^>]+>','',line).strip()
            if c: cur_txt.append(c)

    uniq, prev = [], ''
    for t,txt in segs:
        if txt!=prev: uniq.append((t,txt)); prev=txt

    def kor(s): return len(re.findall(r'[가-힣]',s))
    def t2s(t):
        try: h,m,s=t.split(':'); return int(h)*3600+int(m)*60+int(s)
        except: return 0

    filt, prev = [], ''
    for t,txt in uniq:
        if kor(txt)<4 or len(txt)<6: continue
        if txt[:10]==prev[:10]: continue
        filt.append((t,txt)); prev=txt

    blocks = {}
    for t,txt in filt:
        s=t2s(t); b=(s//180)*180
        k=f"{b//3600:02d}:{(b%3600)//60:02d}"
        blocks.setdefault(k,[]).append(txt)

    return '\n'.join(f"[{k}] {' '.join(v)[:800]}" for k,v in sorted(blocks.items()))

def call_gemini(video, transcript, api_key):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=api_key)
    focus = CORNER_FOCUS.get(video['corner'], "핵심 주제 + 언급 종목 + 전문가 시각")
    prompt = f"""[영상 정보]
제목: {video['title']}
코너: [{video['corner']}]
날짜: {datetime.now().strftime('%Y-%m-%d')}

[이 코너 핵심 추출 포커스]
{focus}

[자막]
{transcript}

---
위 자막을 분석하여 아래 JSON 형식으로 출력하라.

{{
  "summary": "영상 핵심 주제 3줄 요약",
  "market_data": {{"kospi":"","kosdaq":"","usd_krw":"","us_markets":"","other":""}},
  "supply_demand": {{"foreigner":"","institution":"","individual":"","hot_sectors":""}},
  "sectors": [{{"name":"","view":"긍정/중립/부정","reason":"","key_stocks":[]}}],
  "stocks": [{{"name":"","code":"","context":"","direction":"매수/매도/중립/단순언급","reason":"","numbers":""}}],
  "macro_events": [{{"event":"","detail":"","market_impact":""}}],
  "key_insights": ["전문가 핵심 발언 원문 인용"],
  "risks": ["리스크 요인"],
  "strategy": "구체적 투자 전략 (없으면 null)",
  "next_watchpoints": ["다음 관전 포인트"],
  "speaker_opinions": [{{"speaker":"","key_opinion":""}}],
  "unverified": ["[카더라] 확인되지 않은 정보"]
}}"""

    r = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM, temperature=0.2, max_output_tokens=8192)
    )
    return r.text

def save(video, raw):
    import json
    os.makedirs(OUT_DIR, exist_ok=True)
    safe = re.sub(r'[\\/:*?"<>|]','',video['title'])[:40]
    fname = f"TEST_{video['corner']}_{safe}.md"
    path = os.path.join(OUT_DIR, fname)

    parsed = None
    # ```json ... ``` 코드블록 우선 시도
    m = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', raw)
    if m:
        try: parsed = json.loads(m.group(1))
        except: pass
    # 실패 시 전체 범위 greedy 매칭
    if not parsed:
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            try: parsed = json.loads(m.group())
            except: pass

    with open(path,'w',encoding='utf-8') as f:
        f.write(f"# [{video['corner']}] {video['title']}\n\n")
        f.write(f"- **길이**: {video['duration']} | **URL**: {video['url']}\n\n---\n\n")
        if parsed:
            if parsed.get('summary'):
                f.write(f"## 핵심 요약\n{parsed['summary']}\n\n")
            md = parsed.get('market_data',{})
            vals = {k:v for k,v in md.items() if v and v!='null'}
            if vals:
                f.write("## 시장 데이터\n")
                for k,v in vals.items(): f.write(f"- **{k}**: {v}\n")
                f.write("\n")
            sd = parsed.get('supply_demand',{})
            vals = {k:v for k,v in sd.items() if v and v!='null'}
            if vals:
                f.write("## 수급\n")
                for k,v in vals.items(): f.write(f"- **{k}**: {v}\n")
                f.write("\n")
            stocks = parsed.get('stocks',[])
            if stocks:
                f.write("## 언급 종목\n")
                f.write("| 종목 | 방향 | 근거 | 수치 |\n|------|------|------|------|\n")
                for s in stocks:
                    n=s.get('name',''); c=s.get('code','')
                    label=f"{n}({c})" if c and c!='null' else n
                    f.write(f"| {label} | {s.get('direction','')} | {s.get('reason','')} | {s.get('numbers','')} |\n")
                f.write("\n")
            if parsed.get('key_insights'):
                f.write("## 핵심 인사이트\n")
                for i in parsed['key_insights']: f.write(f"- {i}\n")
                f.write("\n")
            if parsed.get('risks'):
                f.write("## 리스크\n")
                for r in parsed['risks']: f.write(f"- {r}\n")
                f.write("\n")
            if parsed.get('strategy') and parsed['strategy'] not in ('null',None):
                f.write(f"## 전략\n{parsed['strategy']}\n\n")
            if parsed.get('next_watchpoints'):
                f.write("## 다음 관전 포인트\n")
                for w in parsed['next_watchpoints']: f.write(f"- {w}\n")
                f.write("\n")
            if parsed.get('unverified'):
                f.write("## 카더라\n")
                for u in parsed['unverified']: f.write(f"- {u}\n")
        else:
            f.write(raw)
    return path

def main():
    api_key = load_key()
    for v in CORNER_VIDEOS:
        v['url'] = f"https://www.youtube.com/watch?v={v['id']}"

    results = []
    for video in CORNER_VIDEOS:
        log(f"\n{'='*55}")
        log(f"[{video['corner']}] {video['title']} ({video['duration']})")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                transcript = get_transcript(video['url'], tmp)
            if not transcript:
                log("자막 없음 - 스킵"); continue
            log(f"자막 {len(transcript):,}자 → Gemini 분석 중...")
            result = call_gemini(video, transcript, api_key)
            path = save(video, result)
            results.append((video['corner'], path))
            log(f"저장: {path}")
        except Exception as e:
            log(f"ERROR: {e}")
            import traceback; traceback.print_exc()

    print("\n\n=== 완료 ===")
    for corner, path in results:
        print(f"  [{corner}] {os.path.basename(path)}")

if __name__ == "__main__":
    main()
