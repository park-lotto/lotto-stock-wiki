# PC 속도 진단

## 2026-09-10 실측

- CPU: AMD Ryzen 7 5700X (8코어 16스레드), 부스트 동작 확인
- RAM: 32GB, 가용 약 8.7GB, 페이지파일 실사용 약 1.8GB
- 저장장치: Samsung 970 EVO Plus 1TB, Healthy, 여유 338.3GB, 측정 당시 디스크 사용률 3%·대기열 0
- GPU: RTX 3060 12GB, 측정 당시 43°C·사용률 22%
- 핵심 병목: `tools/track.py finish 기간탭12시간`이 실행한 `pytest -n auto` 아래 `find.exe` 13개가 5초 평균 CPU 57.5%(약 9.2코어) 점유
- 최근 7일 System 이벤트 로그에서 WHEA·Disk·stornvme·NTFS 관련 하드웨어 오류 미검출
- 결론: 현재 느림은 CPU 성능 부족보다 비정상 병렬 테스트 프로세스가 직접 원인. CPU 교체 보류.

## 다음 할 일

- 2026-09-10 후속: 당시 활성 작업은 `장면그림` 트랙의 `finish`였다. 멈춘 pytest 하위 트리와 이전 실행에서 고아로 남은 `find.exe` 15개를 종료했다.
- 종료 후 `find.exe` 0개, CPU 100% → 12%, 가용 메모리 약 8.7GB → 12.4GB로 회복됨을 실측했다.
- `장면그림` 트랙 커밋은 `origin/track/장면그림`에 모두 백업되어 있으며 main 병합은 아직 안 됐다.
- 반복되면 Python 3.14 환경에서 pytest 워커가 `command /c ver | find` 계열 호출에 걸리는 원인을 별도 코드 트랙에서 조사한다.
- CPU 온도는 Windows 기본 센서에서 노출되지 않아 미확인. 필요 시 HWiNFO 센서 화면으로 부하 온도를 확인한다.
