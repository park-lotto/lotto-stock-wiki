"""새 리포트 3개 V3 추출"""
import os, json, requests
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

PDFS = [
    ('HD현대일렉트릭', 'https://stock.pstatic.net/stock-research/company/18/20260611_company_545237000.pdf'),
    ('원익IPS',       'https://stock.pstatic.net/stock-research/company/18/20260610_company_135650000.pdf'),
    ('FDC종목',       'https://stock.pstatic.net/stock-research/company/56/20260610_company_533058000.pdf'),
]

PROMPT_V3 = """증권사 리포트 PDF를 읽고 아래 JSON을 채워라.

절대 규칙:
1. 수치·날짜는 원문 그대로 (변환·계산 금지)
2. 방향값은 반드시 선택지 중 하나만
3. 없으면 null / 언급없으면 "언급없음"
4. 요약 금지 — 원문 문장 그대로

{
  "기본": {
    "종목명": "", "섹터": "반도체|기판|전력기기|조선|로봇|방산|바이오|2차전지|자동차|통신|반도체장비|기타",
    "세부섹터": "", "날짜": "", "증권사": "", "리포트제목": "원제목 그대로",
    "투자의견": "BUY|HOLD|SELL|Not Rated", "의견변경": "신규|상향|유지|하향",
    "목표주가": "", "현재주가": "", "상승여력": ""
  },
  "애널리스트_강조": {
    "핵심주장": "가장 말하고 싶은 것 — 원문 문장",
    "신규내용": "이번 리포트에서 처음 나온 내용",
    "볼드강조": ["볼드/반복 강조된 원문 최대 5개"]
  },
  "업황": {
    "방향": "강한상승|완만상승|중립|완만하락|강한하락|불명확",
    "사이클위치": "상승초입|상승중반|정점근접|하강초입|하강중|바닥|불명확",
    "수요": {"방향": "강증가|완만증가|유지|감소", "원문": "", "수치": ""},
    "공급": {"방향": "극심부족|타이트|균형|공급과잉", "원문": "", "수치": ""},
    "가격": {"방향": "급등|상승|유지|하락|급락", "원문": "", "수치": ""}
  },
  "실적": {
    "직전분기": {"기간": "", "매출": "", "영업이익": "", "OPM": "",
                "컨센대비": "대폭상회|상회|부합|하회|대폭하회|해당없음"},
    "다음분기전망": {"기간": "", "매출": "", "영업이익": "", "OPM": "",
                   "컨센대비": "상회전망|부합전망|하회전망|언급없음"},
    "연간추정": [{"연도": "", "매출": "", "영업이익": "", "EPS": ""}],
    "추정변경": {"방향": "상향|하향|유지", "변경률": "", "이유": ""}
  },
  "종목모멘텀": {
    "KPI": [
      {
        "지표명": "수주잔고·가동률·점유율·ASP·출하량·OPM·수주금액·매출비중 등 사업운영 지표만. 절대 포함 금지: 시가총액·외국인비중·베타·52주최고저·PER·PBR·ESG점수",
        "수치": "원문 그대로",
        "맥락": "이 수치가 왜 중요한지"
      }
    ],
    "신규모멘텀": "이번 리포트에서 처음 부각된 것",
    "밸류에이션근거": "목표주가 산출 방법·배수·비교 대상 원문"
  },
  "카탈리스트": [{"내용": "", "시점": "날짜/분기 반드시 기재", "임박도": "1개월내|3개월내|6개월내|장기"}],
  "리스크": [{"내용": "", "발현조건": "", "심각도": "높음|중간|낮음"}]
}

JSON만 반환."""

results = []
for name, url in PDFS:
    print(f'[{name}] 다운로드...')
    r = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
    if r.status_code != 200:
        print(f'  실패: HTTP {r.status_code}')
        results.append({'name': name, 'error': f'HTTP {r.status_code}'})
        continue
    print(f'  {len(r.content)//1024}KB → Gemini...')
    tmp = Path(f'_tmp_{name}.pdf')
    tmp.write_bytes(r.content)
    with open(tmp, 'rb') as fh:
        file_obj = client.files.upload(file=fh, config=types.UploadFileConfig(mime_type='application/pdf'))
    tmp.unlink()
    resp = client.models.generate_content(model='gemini-2.5-flash-lite', contents=[file_obj, PROMPT_V3])
    try:
        client.files.delete(name=file_obj.name)
    except Exception:
        pass
    raw = resp.text.strip()
    if raw.startswith('```'):
        raw = raw.split('```')[1]
        if raw.startswith('json'):
            raw = raw[4:]
    try:
        results.append(json.loads(raw))
        print(f'  OK')
    except Exception as e:
        results.append({'name': name, 'error': str(e), 'raw': raw[:300]})
        print(f'  FAIL: {e}')

Path('test_new3.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print('저장: test_new3.json')
