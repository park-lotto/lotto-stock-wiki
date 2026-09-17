# 2026-09-16 장면꾸미기 LAB 로컬 실측

- 입력: 4.000초 1080×1920 무자막 청소 영상 + 실제 WAV 두 비트(훅 1.800초, 본문 2.200초)
- 실행: `tools/scene_style_lab_probe.py`가 `create_copy()` → `render_copy()` → `build_capcut_copy()` 순서로 실제 호출
- 훅 말자막: 0개. 0.900초와 1.767초 프레임에서 말자막이 보이지 않음
- 본문 첫 자막: 1.800초 프레임부터 표시(기대 1.800초, 오차 0프레임)
- 청소본: 네 출구 모두 편성 서명 `738df405dbc0ee00`
- MP4: 길이 4.000초, SHA-256 `887c23e627eac32cb2f5c1c939cc1074ec9b27721be8d0dfe5290f9c10dac2f1`
- MP4 실파일 영수증: SHA-256·132,388 bytes·4.000초를 manifest에 기록했고, 영상 응답 직전 해시/크기를 다시 검사한다. 랜딩 계약도 같은 해시를 가리킨다.
- 경계 접촉시트: SHA-256 `31a4edd9606811da44503a96e5746e413c5075211a117d74e6a3ba08a59eed46`
- CapCut: 네이티브 텍스트 트랙 0개, `scene-style-overlay` 4개
  - 0–900,000μs
  - 900,000–1,800,000μs
  - 1,800,000–2,800,000μs
  - 2,800,000–4,000,000μs
- 랜딩: 관리자 쿠키가 있을 때만 열렸고 동일 `lab-final.mp4`를 직접 재생함
- 관리자 화면: 미리보기·CapCut의 배선 비교와 네 출구의 청소본/위치를 확인했다. MP4·랜딩의 훅 자막/본문 시작은 자동 PASS로 과장하지 않고 `실물 육안 확인`으로 표시하며, 아래 실제 프레임 검수로 확인했다.
- 비교표의 PASS 범위: 미리보기는 장면 컨텍스트, MP4는 실파일 해시, CapCut은 생성 JSON 시간 역검증, 랜딩은 MP4 동일 해시다. 픽셀/OCR 자동판정으로 과장하지 않는다.
- 원본 freshness: 영상 편성뿐 아니라 TTS 파일 SHA-256과 자막 분할·시작·길이도 묶어, 복사 뒤 어느 하나가 바뀌면 렌더·랜딩·영상·CapCut 재료 제공을 차단한다.
- CapCut 모션: 제목/도형 애니메이션 PNG를 30fps 프레임 구간으로 펼친다. CapCut JSON으로 동일 이전을 보장하지 못하는 전체화면 `zoom-punch` 카메라 모션은 정적으로 축소하지 않고 생성 자체를 차단한다.
- 원본 job: 시험 manifest와 산출물은 `_scene_style_lab/<lab_id>` 아래에만 생성됐고 원본 job 객체는 변경되지 않음

재현 명령:

```powershell
py tools/scene_style_lab_probe.py --fixture shopping_shorts/tests/fixtures/scene_style_lab_two_beats.json --out out/scene-style-lab-probe
ffmpeg -y -i out/scene-style-lab-probe/lab-final.mp4 -vf "select='eq(n,27)+eq(n,53)+eq(n,54)+eq(n,70)',scale=360:-1,tile=4x1" -frames:v 1 out/scene-style-lab-probe/boundary.jpg
py tools/open_scene_style_lab.py --probe out/scene-style-lab-probe/probe-result.json
```
