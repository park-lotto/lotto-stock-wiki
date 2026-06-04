# NEXT SESSION
날짜: 2026-06-04 | PC: 집PC

## 세션 요약
yt-gemini-pipeline 품질 개선 + 파이프라인 재설계 시행착오 세션.
주제 발굴 → 주인공 종목 선정 규칙 정립 → LIG D&A 리서치까지 진행.

---

## 미완료 — 다음 세션 최우선

### 1. SKILL.md 전면 재설계 (가장 중요)
오늘 정립한 규칙 전체 반영:
- 파이프라인 5단계 구조 공식화
- Claude 역할 = 편집장 (규칙집행 + 스토리 아키텍트 + 검수) — 리서치 아님
- Gemini Deep Research → Claude 브리프 → Gemini API 대본 플로우 명시

### 2. LIG D&A 영상 브리프 확정 + 대본 생성
- 각도: "천궁-II 1발 쏘면 19억이 사라집니다"
- 주인공: LIG D&A (사용자 확정)
- Deep Research 리포트는 사용자가 세션에 직접 붙여넣기

## 완료 항목
- 영상주제_후보풀.md 생성 (세트1: 각도A/B/C)
- SKILL.md 주인공 종목 선정 5단계 규칙 추가
- gemini_script.py UnicodeEncodeError 수정
- 각도D/E/F 브리프 + 스크립트 생성
- LIG D&A Gemini Deep Research 리포트 확보 (세션 내)

## 파일 경로
- `.agents/skills/yt-gemini-pipeline/SKILL.md`
- `channel/yt/영상주제_후보풀.md`

## 핵심 학습
1. Claude 역할 = 파이프라인 설계자·편집장. 리서치 도구 아님
2. Gemini Deep Research > Claude WebSearch (품질 압도적)
3. grounding WARN = 각도힌트만 있는 브리프에서 발생
4. 올바른 흐름: Gemini Deep Research → Claude 브리프 → Gemini API 대본 → Claude 검수
