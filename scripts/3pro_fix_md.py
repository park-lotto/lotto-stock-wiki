"""기존 저장된 파일에서 JSON 추출해서 깔끔한 마크다운으로 재변환"""
import os, re, json, sys
sys.stdout.reconfigure(encoding='utf-8')

DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "wiki", "insights", "3pro")

def extract_json(raw):
    # ```json ... ``` 코드블록 우선 추출
    m = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', raw)
    if m:
        try: return json.loads(m.group(1))
        except: pass
    # 코드블록 없이 바로 JSON인 경우
    m = re.search(r'\{[\s\S]*\}', raw)
    if m:
        try: return json.loads(m.group())
        except: pass
    # 마지막 시도: 가장 큰 { } 블록
    try:
        start = raw.index('{')
        # 역방향으로 마지막 } 찾기
        end = raw.rindex('}') + 1
        return json.loads(raw[start:end])
    except:
        return None

def to_markdown(path, parsed, meta_header):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(meta_header)

        if parsed.get('summary'):
            f.write(f"## 핵심 요약\n{parsed['summary']}\n\n")

        md = {k:v for k,v in parsed.get('market_data',{}).items() if v and v not in ('null','None',None,'')}
        if md:
            f.write("## 시장 데이터\n")
            labels = {'kospi':'코스피','kosdaq':'코스닥','usd_krw':'달러원','us_markets':'미국시장','other':'기타'}
            for k,v in md.items():
                f.write(f"- **{labels.get(k,k)}**: {v}\n")
            f.write("\n")

        sd = {k:v for k,v in parsed.get('supply_demand',{}).items() if v and v not in ('null','None',None,'')}
        if sd:
            f.write("## 수급\n")
            labels = {'foreigner':'외국인','institution':'기관','individual':'개인','hot_sectors':'주목 섹터'}
            for k,v in sd.items():
                f.write(f"- **{labels.get(k,k)}**: {v}\n")
            f.write("\n")

        secs = [s for s in parsed.get('sectors',[]) if s.get('name')]
        if secs:
            f.write("## 섹터 분석\n")
            for s in secs:
                icon = {'긍정':'🟢','부정':'🔴','중립':'🟡'}.get(s.get('view',''),'⚪')
                stocks = ', '.join(s.get('key_stocks') or [])
                f.write(f"### {icon} {s['name']} ({s.get('view','')})\n")
                if s.get('reason'): f.write(f"{s['reason']}\n")
                if stocks: f.write(f"- 관련 종목: {stocks}\n")
                f.write("\n")

        stocks = [s for s in parsed.get('stocks',[]) if s.get('name')]
        if stocks:
            f.write("## 언급 종목\n")
            f.write("| 종목 | 방향 | 근거 | 수치 |\n|------|------|------|------|\n")
            dir_icon = {'매수':'🟢 매수','매도':'🔴 매도','중립':'⚪ 중립','단순언급':'• 언급'}
            for s in stocks:
                n = s.get('name','')
                c = s.get('code','')
                label = f"{n}({c})" if c and c not in ('null',None,'') else n
                direction = dir_icon.get(s.get('direction',''), s.get('direction',''))
                reason = (s.get('reason') or '').replace('\n',' ')[:60]
                numbers = s.get('numbers') or ''
                f.write(f"| {label} | {direction} | {reason} | {numbers} |\n")
            f.write("\n")

        events = [e for e in parsed.get('macro_events',[]) if e.get('event')]
        if events:
            f.write("## 매크로 이벤트\n")
            for e in events:
                f.write(f"### {e['event']}\n")
                if e.get('detail'): f.write(f"{e['detail']}\n\n")
                if e.get('market_impact'): f.write(f"> **시장 영향**: {e['market_impact']}\n\n")

        insights = parsed.get('key_insights',[])
        if insights:
            f.write("## 핵심 인사이트\n")
            for i in insights:
                f.write(f"> {i}\n\n")

        risks = parsed.get('risks',[])
        if risks:
            f.write("## 리스크\n")
            for r in risks: f.write(f"- ⚠️ {r}\n")
            f.write("\n")

        strategy = parsed.get('strategy')
        if strategy and strategy not in ('null', None):
            f.write(f"## 전략\n{strategy}\n\n")

        wps = parsed.get('next_watchpoints',[])
        if wps:
            f.write("## 다음 관전 포인트\n")
            for w in wps: f.write(f"- 📌 {w}\n")
            f.write("\n")

        speakers = [s for s in parsed.get('speaker_opinions',[]) if s.get('speaker')]
        if speakers:
            f.write("## 출연진 의견\n")
            for s in speakers:
                f.write(f"- **{s['speaker']}**: {s.get('key_opinion','')}\n")
            f.write("\n")

        unverified = parsed.get('unverified',[])
        if unverified:
            f.write("## 카더라\n")
            for u in unverified: f.write(f"- 🔸 {u}\n")
            f.write("\n")

def main():
    files = [f for f in os.listdir(DIR) if f.endswith('.md')]
    fixed = 0
    for fname in files:
        path = os.path.join(DIR, fname)
        raw = open(path, encoding='utf-8').read()

        # 이미 마크다운 변환된 파일인지 확인 (## 핵심 요약 있으면 패스)
        if '## 핵심 요약' in raw and '```json' not in raw:
            print(f"✅ 이미 변환됨: {fname}")
            continue

        # 메타 헤더 추출 (첫 5줄)
        lines = raw.split('\n')
        meta_end = next((i for i,l in enumerate(lines) if l.strip() == '---'), 6)
        meta_header = '\n'.join(lines[:meta_end+1]) + '\n\n'

        parsed = extract_json(raw)
        if not parsed:
            print(f"❌ JSON 추출 실패: {fname}")
            continue

        to_markdown(path, parsed, meta_header)
        print(f"🔄 변환 완료: {fname}")
        fixed += 1

    print(f"\n총 {fixed}개 파일 변환 완료")

if __name__ == '__main__':
    main()
