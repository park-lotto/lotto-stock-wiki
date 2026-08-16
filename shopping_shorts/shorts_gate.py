# -*- coding: utf-8 -*-
"""쇼츠 결과물이 '내보내도 되는 물건인가'를 숫자로 판정한다(2026-08-15 신설).

★왜 만들었나. 정지 프레임만 보고 "됐다"고 보고하다 사장님께 "부자연스러운데 너는
  그걸 측정 못하나"를 들었다. 실제로 눈으로 못 잡던 것 두 개가 측정으로 바로 나왔다:
    - 진행바가 처음부터 끝까지 풀폭(t가 프레임별로 평가 안 됨) → 진행바가 아니었다
    - 시작 1.2초가 디지털 무음(-163 LUFS) → 쇼츠에선 '소리 안 나는 영상'으로 넘긴다
  둘 다 코드를 내가 쓰고도 몰랐다. 그래서 판정을 사람 눈에서 떼어낸다.

원칙: **하나라도 걸리면 결과물을 내보내지 않는다.** 조용한 폴백 금지(0순위-B와 같은 정신).

한계(정직하게): 여기 있는 것은 전부 '명백한 결함'이다. 디자인이 촌스러운 것, 문구가
지루한 것은 못 잡는다. 게이트 통과 = 결함 없음이지 잘 만들었다는 뜻이 아니다.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field

# 영상 창 위치는 템플릿이 정하므로 호출부가 넘긴다. 기본은 전체 화면.
FULL_CROP = "crop=iw:ih:0:0"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    value: float | None = None


@dataclass
class GateResult:
    checks: list[Check] = field(default_factory=list)

    @property
    def ok(self):
        return all(c.ok for c in self.checks)

    def failures(self):
        return [c for c in self.checks if not c.ok]

    def report(self):
        lines = [f"{'OK ' if c.ok else 'NG '} {c.name}: {c.detail}" for c in self.checks]
        lines.append("판정: " + ("통과" if self.ok else
                                 f"불합격 {len(self.failures())}건"))
        return "\n".join(lines)

    def to_dict(self):
        return {"ok": self.ok,
                "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail, "value": c.value}
                           for c in self.checks]}


# ────────────────────────────────────────────────────────────
# 원자료 뽑기
# ────────────────────────────────────────────────────────────
def _loudness_series(path):
    """[(초, 순간 라우드니스 M)] — ebur128의 M은 400ms 창이라 데드에어 판정에 맞다."""
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path),
         "-af", "ebur128=metadata=1,ametadata=print:key=lavfi.r128.M:file=-",
         "-f", "null", "-"], capture_output=True, text=True).stdout
    rows, t = [], None
    for line in out.splitlines():
        m = re.match(r"frame:\d+\s+pts:\d+\s+pts_time:([\d.]+)", line)
        if m:
            t = float(m.group(1))
            continue
        m2 = re.search(r"lavfi\.r128\.M=(-?[\d.]+|-?inf)", line)
        if m2 and t is not None:
            v = m2.group(1)
            rows.append((t, -200.0 if "inf" in v else float(v)))
    return rows


def _integrated_loudness(path):
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-af", "loudnorm=print_format=json",
         "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"\{[^{}]*input_i[^{}]*\}", out, re.S)
    if not m:
        return None
    try:
        return float(json.loads(m.group(0))["input_i"])
    except Exception:                              # noqa: BLE001
        return None


def _frame_diff(path, crop=FULL_CROP):
    """[(초, 프레임 간 평균 절대차)] — 밝기 평균이 아니라 **차분**을 본다.

    밝기 평균만 보면 '화면이 통째로 바뀌었는데 평균은 같은' 컷을 놓친다.
    tblend=difference로 실제 픽셀 변화량을 뽑는다.
    """
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path),
         "-vf", f"{crop},scale=160:90,tblend=all_mode=difference,"
                f"signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-",
         "-f", "null", "-"], capture_output=True, text=True).stdout
    rows, t = [], None
    for line in out.splitlines():
        m = re.match(r"frame:\d+\s+pts:\d+\s+pts_time:([\d.]+)", line)
        if m:
            t = float(m.group(1))
            continue
        m2 = re.search(r"lavfi\.signalstats\.YAVG=([\d.]+)", line)
        if m2 and t is not None:
            rows.append((t, float(m2.group(1))))
    return rows


def _duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True).stdout.strip()
    return float(out) if out else 0.0


# ────────────────────────────────────────────────────────────
# 검사
# ────────────────────────────────────────────────────────────
LEAD_SILENCE_MAX = 0.3      # 초. 이보다 길면 "소리 안 나는 영상"으로 넘긴다
DEADAIR_MAX = 0.4           # 초. 본문 중 이만큼 넘게 조용하면 이탈
DEADAIR_LEVEL = -50.0       # LUFS. 이 아래를 조용한 것으로 본다
JUMP_MAX = 12.0             # LU. 인접 1초 창 라우드니스 차이
FREEZE_HEAD_MAX = 0.5       # 초. 첫 3초 안에서 허용하는 정지
FREEZE_LEVEL = 0.05         # 차분이 이 아래면 정지로 본다
SEAM_MIN_GAP = 1.5          # 초. 컷 사이 최소 간격(연속 이음매 금지)
LUFS_TARGET = -14.0
LUFS_TOL = 2.0


def run(path, *, crop=FULL_CROP, expect_captions=None, dynamic_probe=None,
        ignore_tail=0.0):
    """결과물 mp4 → GateResult.

    dynamic_probe: [(이름, 함수)] — 함수(시각초)가 값을 주면, 두 시점 값이 달라야 한다.
                   진행바처럼 't에 따라 변해야 하는 요소'가 실제로 변하는지 본다
                   (2026-08-15: 이 검사가 없어서 풀폭 고정 진행바를 못 잡았다).
    ignore_tail:   끝에서 이 시간만큼은 오디오 검사에서 뺀다.
                   ★왜 필요한가(2026-08-15 실측). 마지막 페이드아웃 + 무음 엔드카드는
                     **의도된 마무리**인데, 라우드니스 점프 검사가 이걸 30.2 LU 결함으로
                     잡았다. 정적 게인으로 바꿔도 안 없어져서 원인을 오래 헤맸다 —
                     게인은 점프를 만들 수 없으니 애초에 필터 문제가 아니었던 것이다.
                     "의도한 것"과 "사고"를 가르는 정보는 호출부만 안다.
    """
    res = GateResult()
    dur = _duration(path)
    res.checks.append(Check("길이", dur > 3, f"{dur:.1f}초", dur))

    loud = _loudness_series(path)
    if loud:
        # ① 선두 무음
        lead = 0.0
        for t, v in loud:
            if v > -35:
                break
            lead = t
        res.checks.append(Check(
            "선두 무음", lead <= LEAD_SILENCE_MAX,
            f"{lead:.2f}초 (기준 {LEAD_SILENCE_MAX}초 이하)", lead))

        # ② 데드에어 — 시작·끝 페이드 구간은 뺀다
        body = [(t, v) for t, v in loud if 1.0 <= t <= dur - 1.0]
        worst, run_len, run_start = 0.0, 0.0, None
        prev_t = None
        for t, v in body:
            if v < DEADAIR_LEVEL:
                if run_start is None:
                    run_start = t
                run_len = t - run_start
                worst = max(worst, run_len)
            else:
                run_start = None
            prev_t = t
        res.checks.append(Check(
            "데드에어", worst <= DEADAIR_MAX,
            f"최장 {worst:.2f}초 (기준 {DEADAIR_MAX}초 이하)", worst))

        # ③ 라우드니스 점프 — 1초 창 평균끼리 비교(의도된 마무리 구간은 뺀다)
        lim = dur - ignore_tail
        wins = {}
        for t, v in loud:
            if v > -100 and t <= lim:
                wins.setdefault(int(t), []).append(v)
        avg = {k: sum(v) / len(v) for k, v in sorted(wins.items())}
        ks = sorted(avg)
        jumps = [(ks[i], abs(avg[ks[i]] - avg[ks[i - 1]]))
                 for i in range(1, len(ks)) if ks[i] - ks[i - 1] == 1]
        mx = max((j for _, j in jumps), default=0.0)
        res.checks.append(Check(
            "라우드니스 점프", mx <= JUMP_MAX,
            f"최대 {mx:.1f} LU (기준 {JUMP_MAX} 이하)", mx))

        # ④ 최종 라우드니스
        ii = _integrated_loudness(path)
        if ii is not None:
            res.checks.append(Check(
                "최종 라우드니스", abs(ii - LUFS_TARGET) <= LUFS_TOL,
                f"{ii:.1f} LUFS (목표 {LUFS_TARGET}±{LUFS_TOL})", ii))
    else:
        res.checks.append(Check("오디오", False, "오디오 트랙을 못 읽었습니다"))

    # ⑤ 첫 3초 '죽은 시작' — 화면도 멈추고 소리도 없는 구간
    # ★처음엔 '정지'만 봤다가 기준을 고쳤다(2026-08-15). 화면녹화·자막카드 콘텐츠는
    #   정지 화면이 정상이다(이 원본의 전체 차분 중앙값 0.02). 정지 자체는 결함이
    #   아니고, **정지인데 소리까지 없을 때** 시청자가 "재생이 안 되네"로 읽는다.
    #   그래서 두 조건이 동시에 성립하는 구간만 잡는다.
    diffs = _frame_diff(path, crop)
    if diffs:
        def quiet_at(tt):
            if not loud:
                return False
            v = min(loud, key=lambda x: abs(x[0] - tt))[1]
            return v < -35

        head = [(t, v) for t, v in diffs if t <= 3.0]
        longest, start = 0.0, None
        for t, v in head:
            dead = v < FREEZE_LEVEL and quiet_at(t)
            if dead:
                start = t if start is None else start
                longest = max(longest, t - start)
            else:
                start = None
        res.checks.append(Check(
            "죽은 시작(정지+무음)", longest <= FREEZE_HEAD_MAX,
            f"최장 {longest:.2f}초 (기준 {FREEZE_HEAD_MAX}초 이하)", longest))

        # ⑥ 컷 리듬 — 큰 변화(컷)가 1.5초 안에 연달아 오면 정신없다
        vals = sorted(v for _, v in diffs)
        thr = max(8.0, vals[int(len(vals) * 0.98)] if vals else 8.0)
        seams = [t for t, v in diffs if v >= thr]
        merged = []
        for t in seams:
            if not merged or t - merged[-1] > 0.2:
                merged.append(t)
        gaps = [merged[i] - merged[i - 1] for i in range(1, len(merged))]
        mn = min(gaps) if gaps else 99.0
        res.checks.append(Check(
            "컷 리듬", mn >= SEAM_MIN_GAP,
            f"최소 간격 {mn:.2f}초, 컷 {len(merged)}개 (기준 {SEAM_MIN_GAP}초 이상)", mn))
    else:
        res.checks.append(Check("영상", False, "프레임을 못 읽었습니다"))

    # ⑦ 동적 요소 — 't에 따라 변해야 하는 것'이 정말 변하는가
    for name, fn in (dynamic_probe or []):
        a, b = fn(1.0), fn(max(2.0, dur - 1.0))
        res.checks.append(Check(
            f"동적요소:{name}", a != b, f"t=1s {a} / t=끝 {b}"))

    return res


def bar_width_probe(path, y, h=10, w=1080):
    """진행바처럼 '가로로 자라야 하는 막대'의 폭을 재는 탐침을 만든다."""
    def probe(t):
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(path), "-frames:v", "1",
             "-vf", f"crop={w}:{h}:0:{y}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
            capture_output=True).stdout
        row = raw[:w]
        return sum(1 for b in row if b > 100)
    return probe
