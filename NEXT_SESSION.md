# NEXT_SESSION
날짜: 2026-06-16 | PC: 집PC (소넷 세션)

## 세션 요약
카카오클로드 EP1 에셋 폴더 구조 완성 + 씬별 방식 확정.

## ✅ 완료
- `productions/kakao_ep1/` 전체 폴더 구조 확정
  - 01_veo/intro/ (4클립) + 01_veo/outro/ (4클립) — 씬 2개
  - 02_face/ (S3만 얼굴)
  - 03_screen/ (S2·S5·S7·S8·S9·S10·cold_open)
  - 04_remotion/ / 05_audio/ / 06_final/
- `ASSET_MAP.md` — 전체 에셋 체크리스트 완성
- 씬별 대본 txt 파일 생성 (각 폴더 안)
- **S2 대본 사용자가 직접 수정** → `02_face/s02_script.txt` (더 자연스러운 말투)
- **Veo 클립 + Remotion 오버레이** 방식 확정 (KK_Veo_Intro.tsx / KK_Veo_Outro.tsx — 오푸스 설계 필요)
- S2: 화면녹화 배경 + 별도 음성 방식 확정 → `KK_S2_L30.tsx` 경로 s02_screen.mp4로 변경
- MP4 gitignore 처리 (videos/**/*.mp4, remotion-stock/public/**/*.mp4)
- TSX 경로 전체 ep1/ 로 통일

## 전체 씬 구조 (확정)
| 씬 | 배경 | Remotion | TSX |
|---|---|---|---|
| Veo 인트로 (4클립) | AI여자 Veo | 카톡목업·전환효과 | KK_Veo_Intro.tsx ❌ |
| Veo 아웃트로 (4클립) | AI여자 Veo | 수미상관·구독CTA | KK_Veo_Outro.tsx ❌ |
| S2 페인포인트 | 화면녹화(앱브라우징) | 앱아이콘·"30분" | KK_S2_L30.tsx ✓ |
| S3 철학 | 얼굴 녹화 | 텍스트 그래픽 | KK_S3_L30.tsx ✓ |
| S4 로드맵 | 없음 | 순수 Remotion | ❌ 미제작 |
| S5 설치 | 화면녹화 | PiP + 자막 | KK_S5_PiP.tsx ✓ |
| S6 MCP | 없음/bg | 순수 Remotion | KK_S6_MCP.tsx ✓ |
| S7~S10 | 화면녹화 | PiP + 자막 | ❌ 미제작 |
| S11 응용 | 없음 | 순수 Remotion | ❌ 미제작 |
| 전환컷 0.7s | 없음 | 순수 Remotion | ❌ 미제작 |

## ❌ 다음 할 것

### 🧑 네가 할 것
- [ ] Veo 클립 생성: `01_veo/intro/` 4개 + `01_veo/outro/` 4개
- [ ] 화면 녹화: cold_open, s02_screen, s05~s10_screen → `03_screen/`
- [ ] 얼굴 녹화: s03_face → `02_face/`
- [ ] 음성 별도 녹음: s02_voice.mp3 → `05_audio/`

### 🔴 오푸스 1회 설계 (한번에 같이)
- [ ] KK_Veo_Intro.tsx (4클립 × Remotion 오버레이)
- [ ] KK_Veo_Outro.tsx (4클립 × Remotion 오버레이)
- [ ] KK_Transition.tsx (전환컷 0.7s)

### ⚙️ 소넷 작업 (녹화 완료 후)
- [ ] S2 대본 수정본 → SUBS 업데이트 (새 대본 이미 `02_face/s02_script.txt`에 있음)
- [ ] S4·S7~S11 TSX 제작 (KK_S6_TEMPLATE.tsx 복제)
- [ ] Whisper → SUBS 싱크
- [ ] 렌더 + ffmpeg concat

## 관련 파일
- `productions/kakao_ep1/ASSET_MAP.md` — 전체 체크리스트
- `productions/kakao_ep1/01_veo/intro/*.txt` — Veo 클립 대사
- `productions/kakao_ep1/02_face/s02_script.txt` — S2 수정 대본 ⚡
- `channel/yt/yt_카카오클로드_대본_v7.md` — 전체 대본
- `remotion-stock/src/kakao/` — TSX 코드
