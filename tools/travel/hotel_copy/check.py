"""검사 — 대본(렌더 전)과 결과물(렌더 후)을 원본 실측값(refs/<id>.json)에 대조한다. 숫자로 먼저 거르고 표로 남긴다.

대본 검사(script_issues)  줄 수·역할 말(지나면/까지/특히/지만/싶다면…)·글자 수(원본 ±25%)·조각=문장·숫자 출처
결과물 검사(video_report)  길이·컷 길이·말 속도·소리 크기·다시 받아쓰기 일치·컷 안 입체 움직임
"""
import json
import re
import subprocess
from pathlib import Path

import cv2
import numpy as np

NUM = re.compile(r"\d[\d,\.]*")


def script_issues(ep, ref, facts_text):
    out = []
    roles = ref["roles"]
    if len(ep["lines"]) != len(roles):
        out.append("줄 수 %d — 원본 %d줄" % (len(ep["lines"]), len(roles)))
    for i, (ln, r) in enumerate(zip(ep["lines"], roles), 1):
        t = ln["text"]
        n = len(t.replace(" ", ""))
        if abs(n - r["chars"]) > max(5, r["chars"] * 0.25):
            out.append("%d줄 %d자 — 원본 %d자(±25%%)" % (i, n, r["chars"]))
        for m in r["must"]:
            if m.replace(" ", "") not in t.replace(" ", ""):
                out.append("%d줄 '%s' 없음 — 원본 역할(%s)의 뼈대 말" % (i, m, r["role"]))
        if "".join(ln["chunks"]).replace(" ", "") != t.replace(" ", ""):
            out.append("%d줄 자막 조각을 이으면 문장과 다르다" % i)
        if any(len(c.replace(" ", "")) > 9 for c in ln["chunks"]):
            out.append("%d줄 자막 조각이 9자를 넘는다(원본 최대 9자: '지하2,003m에서')" % i)
        if len(ln.get("shot_hints") or []) != r["shots"]:
            out.append("%d줄 사진 %d장 — 원본 %d컷" % (i, len(ln.get("shot_hints") or []), r["shots"]))
        for num in NUM.findall(t):
            if num.rstrip(".,") not in facts_text:
                out.append("%d줄 숫자 '%s' 가 자료(facts)에 없다 — 지어낸 숫자 금지" % (i, num))
    return out


def _probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def lufs(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True, errors="replace")
    m = re.findall(r"I:\s+(-?[\d\.]+) LUFS", r.stderr)
    return float(m[-1]) if m else None


def parallax(path, cuts):
    """컷마다 처음·끝을 줌·이동(아핀)으로 맞춘 뒤 남는 어긋남 % — 사진 줌만이면 0에 가깝다(원본 26~53%)."""
    cap = cv2.VideoCapture(str(path))

    def fr(t):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * 30))
        return cv2.cvtColor(cv2.resize(cap.read()[1], (270, 480)), cv2.COLOR_BGR2GRAY).astype(np.float32)
    out = []
    for a, b, *_ in cuts:
        A, B = fr(a + 0.05), fr(b - 0.08)
        msk = np.ones_like(A, np.uint8)
        msk[110:200] = 0
        msk[340:] = 0
        w = np.eye(2, 3, dtype=np.float32)
        try:
            _, w = cv2.findTransformECC(A, B, w, cv2.MOTION_AFFINE, (3, 100, 1e-5), msk, 5)
        except cv2.error:
            out.append(None)
            continue
        Bw = cv2.warpAffine(B, w, (270, 480), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP)
        d = cv2.GaussianBlur(np.abs(A - Bw), (0, 0), 2) * msk
        d[:8], d[-8:], d[:, :8], d[:, -8:] = 0, 0, 0, 0
        out.append(round(float((d > 12).mean() * 100), 1))
    return out


def heard_same(job, ep):
    from shopping_shorts import asr_check
    w = []
    for _ in range(3):                      # 받아쓰기 실패(빈 답)를 '대본과 다름'으로 치지 않는다 — 다시 시도, 끝내 안 되면 이유를 띄운다
        w = asr_check.transcribe_words(str(Path(job) / "narr.wav")) or []
        if w:
            break
    if not w:
        raise RuntimeError("다시 받아쓰기 실패: %s" % getattr(asr_check._LAST, "error", "?"))
    heard = re.sub(r"[\s\.,\?!]", "", "".join(x.get("word", x.get("w", "")) for x in w))
    want = re.sub(r"[\s\.,\?!]", "", "".join(l["text"] for l in ep["lines"]))
    import difflib
    diffs = ["%s→%s" % (want[a:b], heard[c:d]) for op, a, b, c, d in difflib.SequenceMatcher(None, want, heard).get_opcodes() if op != "equal"]
    # 한 글자씩 2곳까지는 받아쓰기 잡음일 수 있다(실측: 같은 음성을 두 번 받아써도 '수영장→소영장') — 통과시키되 귀로 들을 곳으로 남긴다
    small = all(max(len(x.split("→")[0]), len(x.split("→")[1])) <= 1 for x in diffs)
    return (not diffs) or (len(diffs) <= 2 and small), ", ".join(diffs)


def video_report(job, ep, ref):
    job = Path(job)
    plan = json.loads((job / "plan.json").read_text(encoding="utf-8"))
    out = job / "out.mp4"
    m = ref["measured"]
    lens = [round(b - a, 2) for a, b, *_ in plan["cuts"]]
    chars = sum(len(l["text"].replace(" ", "")) for l in ep["lines"])
    dur = _probe(out)
    same, heard = heard_same(job, ep)
    px = parallax(out, plan["cuts"])
    rows = [
        ("길이", "%.2f초" % dur, "%.1f초" % m["total_s"], abs(dur - m["total_s"]) <= m["total_s"] * 0.12),
        ("컷 수", str(len(lens)), str(len(m["cut_s"])), abs(len(lens) - len(m["cut_s"])) <= 2),
        ("컷 길이", "%.2f~%.2f" % (min(lens), max(lens)), "%.1f~%.1f" % (min(m["cut_s"]), max(m["cut_s"])), min(lens) >= min(m["cut_s"]) * 0.85 and max(lens) <= max(m["cut_s"]) * 1.15),   # 원본 최단·최장 ±15%
        ("말 속도", "%.1f자/초" % (chars / (dur - m["thumb_s"])), "%.1f자/초" % (m["chars"] / (m["total_s"] - m["thumb_s"])),
         abs(chars / (dur - m["thumb_s"]) - m["chars"] / (m["total_s"] - m["thumb_s"])) <= 1.2),
        ("소리 크기", "%.1f LUFS" % (lufs(out) or 0), "%.1f LUFS" % m["lufs"], abs((lufs(out) or 0) - m["lufs"]) <= 1.0),
        ("다시 받아쓰기", "일치" if not heard else "다른 곳: " + heard + (" (귀로 확인)" if same else ""), "대본 그대로", same),
        ("입체 움직임", "%s%%" % "~".join(str(x) for x in (min(p for p in px if p is not None), max(p for p in px if p is not None))), "26~53%", None),
    ]
    rep = {"rows": [{"항목": a, "우리": b, "원본": c, "통과": d} for a, b, c, d in rows], "parallax": px, "cut_s": lens}
    (job / "check.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return rep
