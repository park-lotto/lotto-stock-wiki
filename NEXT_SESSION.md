# NEXT SESSION

> 날짜: 2026-06-04 | 집PC에서 이어서
> 세션 요약: Gemini 딥리서치 파이프라인 구축 + 첫 영상 대본 완성 (소부장 자금순환)

---

## ✅ 완료 항목

- Gemini Deep Research 연동 3가지 방법 `.mcp.json`에 등록
  - MCP A: `gemini-research` (uvx gemini-research-mcp)
  - MCP B: `gemini` (@rlabs-inc/gemini-mcp) ← 메인으로 사용 예정
  - Python: `scripts/gemini_yt_deep_research.py` ← 지금 바로 사용 가능
- `yt-content-research` → `yt-gemini-pipeline` 풀 파이프라인 첫 실전 실행
- 영상 대본 완성: **"삼성전자가 빠진 날 소부장이 30% 오른 이유 — 자금 순환의 법칙"**
  - 브리프: `channel/yt/brief_소부장자금순환_20260604.md`
  - 최종 대본: `channel/yt/script_소부장자금순환_20260604_final.md`
  - 원본 백업: `raw/yt/script_소부장자금순환_20260604_gemini.md`
- `유뷰트제작가이드1` 스킬 생성: `.agents/skills/유뷰트제작가이드1/SKILL.md`

---

## ⏳ 미완료 — 다음 세션에서

### 1순위: MCP B 활성화 (집PC 재시작 전)
```powershell
$key = (Get-Content "C:\Users\TheRose\Desktop\로또의 주식\.env" | Select-String "^GEMINI_API_KEY=").ToString().Split("=",2)[1]
[Environment]::SetEnvironmentVariable("GEMINI_API_KEY", $key, "User")
```
→ Claude Code 재시작 후 `gemini-deep-research` MCP 툴 사용 가능

### 2순위: 영상 제작 이어가기
- `/yt-planner` 실행 → 씬별 Remotion 컴포넌트 설계
- 실화면 촬영 필요 데이터:
  - 원익IPS 수주잔고 +4배 그래프
  - 코스피 vs 코스닥 오늘 비교 차트
  - ADR 지표 설명 그래픽
  - 자금 이동 흐름 인포그래픽 (코스피→코스닥)

### 3순위: 기획서 + 후보풀 업데이트
- `channel/yt/영상주제_후보풀.md` → 소부장자금순환을 확정 완료로 이동

---

## 관련 파일 경로

| 파일 | 경로 |
|------|------|
| 최종 대본 | `channel/yt/script_소부장자금순환_20260604_final.md` |
| 브리프 | `channel/yt/brief_소부장자금순환_20260604.md` |
| 딥리서치 스크립트 | `scripts/gemini_yt_deep_research.py` |
| MCP 설정 | `.mcp.json` |
| 영상 제작 스킬 | `.agents/skills/유뷰트제작가이드1/SKILL.md` |
