"""점검 판정값과 결과 레코드 — 층·항목이 달라도 저장·화면·알림은 이 한 벌만 쓴다."""
from dataclasses import dataclass

GREEN, YELLOW, RED, GRAY = "green", "yellow", "red", "gray"
ORDER = {RED: 0, YELLOW: 1, GRAY: 2, GREEN: 3}


@dataclass
class Result:
    layer: str            # L0 | L1 | L2 | L3
    name: str             # 일상어 이름(화면에 그대로)
    verdict: str          # GREEN|YELLOW|RED|GRAY
    reason: str = ""
    signature: str = ""   # 같은 항목의 이력을 잇는 키
    page: str = ""
    evidence_dir: str = ""
    dur_ms: int = 0


@dataclass
class Sample:
    item: str             # health 파일명(h_ranking_fresh)
    name: str             # META["name"]
    value: float | None
    ok: bool | None       # None = 판정 불가(회색)
    detail: str = ""
    evidence_url: str = ""

    @property
    def verdict(self):
        if self.ok is None:
            return GRAY
        return GREEN if self.ok else RED
