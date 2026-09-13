# A안 본사 한 동 · 실제 모델 1차

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
