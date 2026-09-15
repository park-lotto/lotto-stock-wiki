---
name: project-agents-video-progress
description: 에이전트직원 영상 씬별 제작 진행 현황 — 컨펌/완성 씬 기록
metadata:
  type: project
---

영상 제목: "나는 자는 동안 직원 10명이 밤새 일한다"
총 길이: 8분 20초 목표

**컨펌 완료 씬 (Remotion 컴포넌트 + Whisper 싱크 완성)**

| 씬 | 컴포넌트 ID | 프레임 | 오디오 | 비고 |
|----|-----------|------|------|------|
| 씬1 훅 | `AG01-Timeline-Hook` | 600프레임 | `voice/s01.mp3` (19.98초) | Whisper 싱크 완료 |
| 씬2 공감 | `AG-S02-Empathy` | 979프레임 | `voice/ag_s02.m4a` (32.62초) | Whisper 싱크 완료 |
| 씬3 선언 | `AG-S03-Declaration` | 532프레임 | `voice/ag_s03.m4a` (17.74초) | Whisper 싱크 완료 |
| 씬4-1 총괄소개 | `AG-S04-1-Boss` | 412프레임 | `voice/ag_s4-1.m4a` (13.74초) | Whisper 싱크 완료 |
| 씬4-2 수집직원 | `AG-S04-2-Collect` | 1660프레임 | `voice/ag_s4-2.m4a` (55.34초) | Whisper 싱크 완료 |
| 씬4-3 수급직원 | `AG-S04-3-Supply` | 725프레임 | `voice/ag_s4-3.m4a` (24.18초) | Whisper 싱크 완료 |
| 씬4-4 탑픽직원 | `AG-S04-4-Toppick` | 550프레임 | `voice/ag_s4-4.m4a` (18.32초) | Whisper 싱크 완료 |
| 씬4-5 브리핑직원 | `AG-S04-5-Brief` | 637프레임 | `voice/ag_s4-5.m4a` (21.24초) | Whisper 싱크 완료 |
| 씬4-6 배포직원 | `AG-S04-6-Deploy` | 587프레임 | `voice/ag_s4-6.m4a` (19.58초) | Whisper 싱크 완료 |
| 씬4-7 나머지직원 | `AG-S04-7-Others` | 686프레임 | `voice/ag_s4-7.m4a` (22.86초) | Whisper 싱크 완료 |

**Remotion 컴포넌트 존재 (오디오 싱크 미적용)**

| 씬 | 컴포넌트 ID | 비고 |
|----|-----------|------|
| 씬3 베이스 | `AG02-Agents` | 750프레임. AG_S03으로 대체됨 |
| 씬5 클라이맥스 | `AG01-Timeline-Climax` | 750프레임. 오디오 미적용 |
| 씬6 자각 | `AG03-Awareness` | 1200프레임. 오디오 미적용 |
| 씬7 여운 | `AG04-Tease` | 900프레임. 오디오 미적용 |
| 씬8 CTA | `AG05-CTA` | 900프레임. 오디오 미적용 |
| 씬4-5 배포 | `AG06-Delivery` | 750프레임. 오디오 미적용 |

**제작 대기 씬 (실화면 촬영 필요)**

- 씬2 일부: 텔레방·증권사앱·유튜브 3분할 화면 녹화
- 씬4-1: 터미널 로그 화면 녹화 (calc_oscillator 실행)
- 씬4-3: 탑픽 스코어카드 HTML 화면
- 씬4-4: 아침 노트 HTML 화면
- 씬4-5: 텔레그램 수신 화면 캡처
- 씬6 일부: 커피 마시는 실촬영

**스타일 규칙 (컨펌됨)**
- 이모지(40%) + 텍스트(60%) 혼합 — 이모지만 또는 텍스트만 NG
- 자막바 필수 (하단 16%, Whisper 세그먼트 싱크)
- [[feedback-remotion-style]] 참조

**Why:** 사용자가 씬별로 녹음 파일 넣으며 순서대로 제작 중. 컨펌된 씬은 덮어쓰지 않고 누적.
**How to apply:** 다음 세션에서 이어받을 때 이 파일로 현재 진행 상황 파악.
