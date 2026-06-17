# NEXT_SESSION
날짜: 2026-06-17 | PC: 집PC (소넷 세션)

## 세션 요약
카카오클로드 EP1 씬 폴더 전면 재구조화 + OBS 세팅 완료.
대본 녹음·화면녹화 준비 완료 상태.

## ✅ 완료
- S3 대본 구어체 수정 (s03_script.txt)
- 씬별 폴더 구조 전면 개편 (미디어타입별 → 씬별)
  - 기존: 01_veo / 02_face / 03_screen / 04_remotion / 05_audio / 06_final
  - 신규: 00_cold_open / 01_veo_intro/clip1~4 / S02~S11 / transition / 99_veo_outro/clip_a~d / _audio / _final
- 각 씬 폴더에 script.txt + design.md 생성 (오푸스 작성용 플레이스홀더)
- Veo/Remotion씬에 design_prompt.txt 추가
- S04·S06·S11 script.txt 신규 생성 (v7.md에서 추출)
- intro.mp4 / outro.mp4 = 4클립 합본 확인 → 01_veo_intro / 99_veo_outro 루트에 위치
- ASSET_MAP.md 전면 업데이트
- T3CHFEED 레퍼런스 분석 (편집 리듬: 훅→채널스팅→본론)
- KK_ChannelSting.tsx 신규 추가 (T3CHFEED 스타일 채널 로고 스팅)
- OBS 설치 + RTX 3060 NVENC 세팅 (1080p 30fps 15000Kbps MKV)
- VLC 설치 (HEVC 재생용)

## ❌ 다음 할 것

### 🧑 네가 할 것 (녹화·녹음)
- [ ] 음성 녹음: S2·S3·S4·S5·S6·S7·S8·S9·S10·S11 대본 읽기
      → CapCut에서 실수 구간 컷 → 씬 폴더에 저장
- [ ] 화면 녹화 (OBS):
      - S2: 인베스팅→나스닥→네이버뉴스→텔레그램→유튜브 (45초, 무음)
      - S5: Claude 설치 과정
      - S7: PlayMCP 연동
      - S8: 프롬프트 입력
      - S9: 플러그인 패키징
      - S10: 예약 작업 설정
- [ ] cold_open: 폰에 카톡 브리핑 오는 화면 (2초)

### ⚙️ 소넷 (파일 다 들어오면)
- [ ] Whisper 돌려서 타임스탬프 + 대본 추출
- [ ] 음성 실수 구간 ffmpeg 컷 (CapCut에서 1차 정리 후)
- [ ] script.txt 타임스탬프 버전으로 업데이트
- [ ] 씬별 검수 체크리스트

### 🔴 오푸스 1회 (검수 완료 후)
**편집 전략 설계 먼저, 그 다음 TSX 구현**
- [ ] 전체 영상 편집 리듬 전략 (T3CHFEED 스타일 채널 스팅 포함)
- [ ] KK_ChannelSting.tsx (채널 로고 스팅 3~4초)
- [ ] KK_Veo_Intro.tsx (intro.mp4 오버레이)
- [ ] KK_Veo_Outro.tsx (outro.mp4 오버레이)
- [ ] KK_Transition.tsx (씬간 0.7초 전환)
- [ ] KK_S4_Roadmap.tsx
- [ ] KK_S11_Apply.tsx

### Phase 2 오푸스 (녹화 완료 후)
- [ ] KK_S7~S10.tsx (화면녹화 PiP 4개)

## 녹화 가이드
- OBS 저장 경로: C:\Users\TheRose\Videos
- 단축키: Alt+F9 녹화 시작/중지
- 화면녹화는 넉넉하게 (45초+) 길게 찍기
- 음성 실수하면 3초 쉬고 그 문장만 다시
- S2: 1.5배속 처리 예정 (소넷이 ffmpeg으로)
- S5·S7~S10: 1x 원본 속도 유지

## 관련 파일
- `productions/kakao_ep1/ASSET_MAP.md` — 전체 체크리스트
- `productions/kakao_ep1/S02~S11/script.txt` — 씬별 대본
- `channel/yt/yt_카카오클로드_대본_v7.md` — 마스터 대본
- `remotion-stock/src/kakao/` — 기존 TSX 코드
