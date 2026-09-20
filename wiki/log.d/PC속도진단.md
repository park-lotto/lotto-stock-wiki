# PC속도진단

- 2026-09-10: Ryzen 7 5700X/32GB/970 EVO Plus 상태 실측. 디스크·메모리보다 `pytest -n auto`가 만든 `find.exe` 13개(전체 CPU 57.5%)가 현재 느림의 직접 원인으로 확인되어 CPU 교체는 보류 판단.
- 후속 정리: `장면그림` finish의 멈춘 pytest와 고아 `find.exe` 15개 종료. CPU 100%→12%, 가용 RAM 8.7GB→12.4GB 회복; 트랙 커밋은 원격에 보존됨.
