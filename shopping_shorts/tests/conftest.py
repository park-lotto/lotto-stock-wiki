"""테스트 공통 픽스처.

SSRF 가드(_reject_ssrf)는 도메인이 **실제로 어느 IP로 뜨는지** 확인한다(DNS rebinding
1차 방어). 그래서 가드가 걸린 라우트를 테스트하면 유닛테스트가 실제 DNS를 타게 되고,
- 네트워크 없는 CI/오프라인에선 "호스트 해석 실패"로 422가 되어 무관한 테스트가 깨지고,
- 있어도 조회 지연만큼 느려지며 결과가 환경에 따라 흔들린다.
→ 이름해석만 결정적으로 고정한다. 스킴 검사·사설망/링크로컬 IP 판정 등 가드의 실제
  로직은 그대로 돈다(IP 리터럴은 애초에 DNS를 안 탄다).
"""
import socket

import pytest

_PUBLIC_IP = "93.184.216.34"      # 공인 IP — 가드가 "내부망 아님"으로 통과시킨다.
# 이름이 내부망을 가리키는 상황을 재현하고 싶은 테스트를 위해 남겨둔다.
_FORCE_PRIVATE = {"internal.example", "metadata.example"}


@pytest.fixture(autouse=True)
def offline_dns(monkeypatch):
    def _fake_gethostbyname(host):
        if host in _FORCE_PRIVATE:
            return "169.254.169.254"
        return _PUBLIC_IP

    monkeypatch.setattr(socket, "gethostbyname", _fake_gethostbyname)
