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


def summarize(rows, prev):
    """점검 결과 목록을 신호등 요약 + '새로 빨개진 것'으로 압축한다."""
    counts = {RED: 0, YELLOW: 0, GRAY: 0, GREEN: 0}
    newly = []
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        if r["verdict"] == RED and prev.get(r["signature"]) != RED:
            newly.append(r)
    overall = GRAY if counts[GRAY] else RED if counts[RED] else YELLOW if counts[YELLOW] else GREEN
    if newly:
        names = "·".join(r["name"] for r in newly[:3])
        headline = f"{names}이(가) 새로 빨개졌습니다. 빨강 {counts[RED]}건, 판정 불가 {counts[GRAY]}건."
    elif counts[GRAY]:
        headline = f"판정 불가 {counts[GRAY]}건 — 점검기 상태를 먼저 보세요."
    elif counts[RED]:
        headline = f"어제와 같은 빨강 {counts[RED]}건이 계속됩니다."
    elif counts[YELLOW]:
        headline = f"빨강은 없고 주의 {counts[YELLOW]}건입니다."
    else:
        headline = "전부 정상입니다."
    return {"counts": {"red": counts[RED], "yellow": counts[YELLOW],
                       "gray": counts[GRAY], "green": counts[GREEN]},
            "overall": overall, "newly_red": newly, "headline": headline}
