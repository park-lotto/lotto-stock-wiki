"""장중 시황 브리핑 — 텔레그램 다이제스트(major 즉시 / minor 15분 배치) + 일일요약."""
from collections import Counter


def format_trigger(events: list, result: dict) -> str:
    labels = " · ".join(e.get("label", "") for e in (events or []))
    v = (result or {}).get("verdict", {}) or {}
    first_line = ((result or {}).get("narrative", "") or "").split("\n")[0]
    model = (result or {}).get("_model", "")
    head = f"🔔 {labels}" if labels else "🔔 시황 갱신"
    return f"{head}\n[{v.get('tone','')}] {v.get('line','')}\n{first_line}\n({model})"


class DigestBatcher:
    """major 이벤트는 즉시, minor는 minor_interval_s마다 묶어서 방출."""

    def __init__(self, minor_interval_s: int = 900):
        self.interval = minor_interval_s
        self._buf = []
        self._last_flush = 0.0

    def add(self, events: list, result: dict, now: float):
        is_major = any(e.get("major") for e in (events or []))
        text = format_trigger(events, result)
        if is_major:
            return text
        self._buf.append(text)
        if self._last_flush == 0.0:
            self._last_flush = now
        if now - self._last_flush >= self.interval:
            out = "📋 최근 브리핑 묶음\n\n" + "\n\n".join(self._buf)
            self._buf = []
            self._last_flush = now
            return out
        return None


def format_daily(calib_rows: list) -> str:
    total = len(calib_rows or [])
    noise = sum(1 for r in (calib_rows or []) if r.get("noise_flag"))
    by_type = Counter(e.get("type") for r in (calib_rows or [])
                      for e in r.get("fired_events", []))
    lines = ["📊 오늘 시황 브리핑 관측 요약",
             f"총 발동 {total}회 · 의심노이즈 {noise}건", "타입별:"]
    lines += [f"  - {k}: {v}" for k, v in by_type.most_common()]
    return "\n".join(lines)
