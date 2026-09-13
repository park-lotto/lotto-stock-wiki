# A안 본사 한 동 · 실제 모델 1차

## 소재·실내 보강 v3 (2026-09-13)

- 사용자 승인: 따뜻한 고급 사옥 소재, 밖에서 보이는 실내 사실감 개선. 외형·층고·기존 비교 카메라 유지.
- `hq_premium.py`: 저장된 v2를 입력으로 절차적 석재/월넛/패브릭 결, 짙은 브론즈/유리, 회의실·업무석·라운지·책장·천장 마감·리셉션 세부 생성. `makers-lab-hq-a-v3.blend` 별도 저장.
- `hq-premium-{day,night,entry,lobby,window}.png`: 실제 Cycles/OptiX 96샘플 렌더. 기존 `hq-*.png` 보존. 검토 페이지 기본값 v3, 수정 전 외관 버튼으로 같은 카메라 v2 비교.
- v2에서 `hq_premium_verify.py` RED, v3에서 구조 GREEN. 실제 5개 렌더 직접 검토, 과한 원형 광원 반사 확인 후 직사각 광원/반사 가시성 보정. 브라우저 7탭·이미지 로딩·모바일 폭 확인.
- 실행: 새 Blender 프로세스에서 `--background <절대 v2.blend> --python-exit-code 1 --python <절대 hq_premium.py> --python <절대 hq_premium_verify.py> --python <절대 hq_render.py>`. 재렌더만 할 때는 **저장된 v3.blend를 새로 로드한 후** `hq_render.py` 실행. 기존 렌더 스크립트가 메모리 월드를 야간 상태로 남기므로 같은 메모리에서 반복 실행하지 않는다.
- 일반 코드 검수에서 새 변경의 중대한 결함 없음, 위 재렌더 주의점 지적. 페이블 검수 아님.
- 여전히 최종 실사 품질/운영 공간 완성 아님. 회의실·좌석은 디자인용 가상 배치이며 실제 조직/수량과 미연결. 자유 회전·보행 뷰어는 아직 없음.

사용자 최신 지시: 전체 구현보다 건물 한 동부터. 기존 캠퍼스와 `/hq/` 페이지는 보존한다.

## 산출물

- `/hq-building/`: 주간·야간·입구·로비의 **실제 Blender 고정 시점 렌더**와 승인 A 생성시안 비교. 자유 회전 뷰어 아님.
- `.artifacts/makers-lab-hq-a-v1.blend`: MCP로 생성한 초기 모델, 기존 연결 검증 장면 보존.
- `.artifacts/makers-lab-hq-a-v2.blend`: 렌더 검사 후 재질/조경/천장/가구를 보정한 모델. GUI MCP 장면은 v1일 수 있으므로 최신 파일을 명시적으로 열 것.
- Blender 파일은 로컬 산출물이며 git 제외. 재현 스크립트와 검토 PNG는 트랙에 보존한다.

## 재현

1. `mcp_check.py --script company_ops/blender/hq_verify.py`: 최초 장면 없음으로 RED 확인했다.
2. 전용 Blender에서 `mcp_check.py --script company_ops/blender/hq_build.py`: 같은 이름의 장면 있으면 덮어쓰기 거절. 실제 MCP safe mode 켠 상태 생성·저장 성공.
3. Blender `--background <절대 v1.blend> --python <절대 hq_refine.py> --python <절대 hq_verify.py> --python <절대 hq_render.py>`.
4. 산출 PNG 4장을 `static/hq-building/`에 복사하고 정적 서버8931에서 `node company_ops/tests/hq-building.cjs`.

## 확인과 한계

- Cycles/RTX3080Ti OptiX 렌더 4종을 직접 확인. 최초 과노출·각진 수목·로비 지붕 누락·사인 가림을 확인 후 보정했다.
- 중앙 높은 유리 로비, 옥상 2단 후퇴, 양측 업무 공간, 리셉션/계단/메자닌, 입구 캐노피와 근접 광장.
- 실제 도면이 없는 디자인 모델. 치수는 제작 가정이며 확정 설계/시공 도면 아님.
- 원본 A의 최종 사실적 품질 재현 완료 아님. 옥상 빈 구간, 외벽 세부, 야간 상부 조명, 실내 가구/난간/동선은 추가 설계 필요. 화려한 전체 배경으로 미완성 건물을 감추지 않고 한 동을 검토한다.
- GLB 웹 전달, 자유 회전/보행/충돌, 운영 워커·음성·자동화 연결은 이번에 하지 않았다.
- main 배포하지 않는다. 건물 형태 피드백 후 같은 모델을 세부 수정한다.
