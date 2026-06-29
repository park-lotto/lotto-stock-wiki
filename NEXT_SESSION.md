# NEXT SESSION — 2026-06-29 (집PC)

## 세션 요약
NotebookLM MCP (notebooklm-mcp-cli, Python) 정착 완료.
텔레그램 오늘 크롤링 12개 소스 기반 Q1~Q7 쿼리 모두 완료.

## 완료 항목
- notebooklm-mcp-cli (jacob-bd, PyPI) 정상 작동 확인
  - `nlm notebook query <notebook_id> "질문"` 방식으로 사용
  - notebook id: `2630cdd9-812d-4af5-8b94-d8636a3c852c`
- Q1~Q7 인사이트 추출 완료 (대화창에 전부 표시됨)
  - Q1: 섹터 수급이동 (반도체→헬스케어/소프트웨어/방어주 대순환)
  - Q2: TP표 (SK하이닉스 330만↑, 고려아연·LS 신규커버, 에코프로비엠↓)
  - Q3: 상승재료 TOP3 (GLP-1 메디케어, AI소프트웨어순환, 고려아연구조적이익) / 하락 TOP3 (오픈AI상장연기, CXMT, 카시카리)
  - Q4: HBM ASP 2027년 35%↑, NAND 격상, PLP·유리기판 가속
  - Q5: 고려아연 핵심광물플랫폼, LS전선 믹스개선, 대한조선 2028 가시성
  - Q6: CXMT 애플타진, 반도체소재 탈일본화 14종, 중국 ESS 550GWh, 희소금속 60%↑
  - Q7: 7/1 한국수출(반도체핵심), 7/1 메디케어GLP-1 개시, 7/3 미국 NFP, 7/7 삼성전자 잠정실적

## 미완료 — 집에서 할 것

### 1. NotebookLM 인사이트 HTML 브리핑 저장
오늘 Q1~Q7 결과를 `out/nlm_briefing_20260629.html`로 저장.
→ "nlm briefing html 만들어줘" 하면 됨 (재쿼리로 자동 생성)

### 2. 백그라운드 Python nlm 자동화 (토큰 0)
```python
# 아이디어: pipeline/nlm_daily.py
import subprocess, json
nb = "2630cdd9-812d-4af5-8b94-d8636a3c852c"
queries = [("q1_수급","..."), ("q2_tp","..."), ...]
for name, q in queries:
    r = subprocess.run(["nlm","notebook","query",nb,q],
                       capture_output=True, text=True, encoding="utf-8")
    json.dump(json.loads(r.stdout), open(f"out/nlm/{name}.json","w",encoding="utf-8"), ensure_ascii=False)
```
→ Claude 토큰 소모 없이 결과 파일 저장, 나중에 선택적으로 읽기

## 기술 메모 (nlm CLI)
- 올바른 캡처 방법 (한글 정상):
  ```powershell
  $raw = (nlm notebook query $nb "질문" 2>&1 | Out-String)
  ($raw | ConvertFrom-Json).answer
  ```
- `Set-Content -Encoding UTF8` 파이프 방식은 한글 깨짐 → 쓰지 말 것
- NotebookLM URL: https://notebooklm.google.com/notebook/2630cdd9-812d-4af5-8b94-d8636a3c852c
