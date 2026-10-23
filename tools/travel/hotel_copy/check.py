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
CUT_MAX_K = 1.15       # 컷 길이 기준 = 원본 최단×0.85 ~ 최장×1.15 (engine.s_shots 가 컷 수를 정할 때도 이 값을 쓴다)
CUT_MIN_K = 0.85
# 받아쓰기가 소리는 같은데 글자를 다르게 적는 것 — 다름으로 치지 않고 '(발음 같음)'으로만 남긴다. 근거 없는 건 넣지 않는다
ASR_SAME = {"촌→총": "원본 AVo84VRq55k 도 '총캉스'로 받아씀(2026-10-23 실측)",
            "솥→소": "솥뚜껑 표준 발음 [솓뚜껑] — 받침이 안 들린다",
            "촌이→초니": "연음 — 표준 발음 [초니](상주견 이름 '촌이')"}


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
            out.append("%d줄 자막 조각이 9자를 넘는다(원본 자막 조각은 최대 9자)" % i)
        if len(ln.get("shot_hints") or []) < r["shots"]:          # 많은 건 괜찮다 — 말이 원본보다 길면 shots 단계가 컷을 더한다
            out.append("%d줄 사진 %d장 — 원본 %d컷" % (i, len(ln.get("shot_hints") or []), r["shots"]))
        for num in NUM.findall(t):
            if num.rstrip(".,") not in facts_text:
                out.append("%d줄 숫자 '%s' 가 자료(facts)에 없다 — 지어낸 숫자 금지" % (i, num))
    if ref.get("script_doc"):
        out += doc_issues(ep, ref["script_doc"], facts_text)
    return out


def _script_frame():
    """다른 채널 대본 설명서 검사기(주인 = 칼카피숏템엔진 tools/calcopy/engine/script_frame). main 에 아직 없으면 옆 트랙 폴더에서 읽는다."""
    import importlib.util
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    for base in (root, root.parent / "칼카피숏템엔진"):
        f = base / "tools/calcopy/engine/script_frame.py"
        if f.exists():          # 파일 경로로 읽는다(이 트랙의 tools 패키지가 먼저 잡혀 이름으로는 옆 트랙 것을 못 부른다 — 실측 ImportError)
            spec = importlib.util.spec_from_file_location("hotel_copy_script_frame", f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod, base / "channel"
    raise RuntimeError("대본 설명서 검사기(tools/calcopy/engine/script_frame.py)를 못 찾음 — 칼카피숏템엔진 트랙이 필요")


def doc_issues(ep, doc, facts_text):
    """refs 의 script_doc(예: homedesignnote) 설명서 검사 — 첫 문장 공식·잉?/와우·판별·근거. 걸린 것 = 고칠 말 목록(대본 단계가 다시 쓰게)."""
    import json
    SF, ch = _script_frame()
    D = ch / doc / "대본설명서"
    rd = lambda n: json.loads((D / n).read_text(encoding="utf-8"))
    frame, hf, pc = rd("script_frame.json"), rd("hook_formula.json"), rd("points.json")
    L = ep["lines"]
    txt = " ".join(l["text"] for l in L)
    # 근거 = 줄마다 'facts'(자료에서 그대로 옮긴 짧은 말). 자료에 글자 그대로 있는 것만 근거로 친다
    ok_facts = {f for l in L for f in l.get("facts") or [] if f and f.replace(" ", "") in facts_text.replace(" ", "")}
    out = []
    h = SF.hook_formula_check(L[0]["text"], hf, txt)
    if h and not h["ok"]:
        out.append("첫 문장 공식 미달(%s) — [누가]+[무엇이 귀찮아서 등 계기]+[~해버렸더라고요/대요]" % "; ".join(h["why"]))
    p = SF.points_check(L, pc, ok_facts)
    if p and not p["ok"]:
        out.append("잉?·와우 미달: %s" % "; ".join(p["why"]))
    j = SF.judge_like(txt, frame)
    if not j["pass"]:
        out.append("설명서 판별 %.2f(기준 %s) 미달 %s — 이 채널 말투(체험담 ~더라고요)로" % (j["score"], j.get("threshold"), j["hard_fail"]))
    for i, (g, l) in enumerate(zip(SF.grounding_audit([l["text"] for l in L]), L), 1):
        if g["needs_ground"] and not set(l.get("facts") or []) & ok_facts:
            out.append("%d줄 %s — 근거 필요한 말인데 facts(자료 그대로 옮긴 말)가 없다" % (i, "/".join(g["tags"])))
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
    allx = ["%s→%s" % (want[a:b], heard[c:d]) for op, a, b, c, d in difflib.SequenceMatcher(None, want, heard).get_opcodes() if op != "equal"]
    diffs = [x for x in allx if x not in ASR_SAME]
    same_sound = [x for x in allx if x in ASR_SAME]
    # 한 글자씩 2곳까지는 받아쓰기 잡음일 수 있다(실측: 같은 음성을 두 번 받아써도 '수영장→소영장') — 통과시키되 귀로 들을 곳으로 남긴다
    small = all(max(len(x.split("→")[0]), len(x.split("→")[1])) <= 1 for x in diffs)
    note = ", ".join(diffs) + ((" / " if diffs else "") + "발음 같음: " + ", ".join(same_sound) if same_sound else "")
    return (not diffs) or (len(diffs) <= 2 and small), note


def video_report(job, ep, ref):
    job = Path(job)
    plan = json.loads((job / "plan.json").read_text(encoding="utf-8"))
    out = job / "out.mp4"
    m = ref["measured"]
    lens = [round(b - a, 2) for a, b, *_ in plan["cuts"]]
    chars = sum(len(l["text"].replace(" ", "")) for l in ep["lines"])
    dur = _probe(out)
    rate = m["chars"] / (m["total_s"] - m["thumb_s"] - 0.3)           # 원본 말 속도(자/초) — engine.s_voice 와 같은 식
    want_s = (chars / rate + m["thumb_s"] + 0.3) if m.get("length_from_script") else m["total_s"]
    same, heard = heard_same(job, ep)
    px = parallax(out, plan["cuts"])
    rows = [
        ("길이", "%.2f초" % dur, "%.1f초" % want_s, abs(dur - want_s) <= want_s * 0.12),
        # 길이가 대본을 따르는 틀(length_from_script)은 컷 수 대신 평균 컷 길이로 본다(원본 ±15%) — 30초 대본에 16.6초 원본 컷 수를 대면 안 된다
        (("평균 컷 길이", "%.2f초" % (sum(lens) / len(lens)), "%.2f초" % (sum(m["cut_s"]) / len(m["cut_s"])),
          abs(sum(lens) / len(lens) - sum(m["cut_s"]) / len(m["cut_s"])) <= sum(m["cut_s"]) / len(m["cut_s"]) * 0.15)
         if m.get("length_from_script") else
         ("컷 수", str(len(lens)), str(len(m["cut_s"])), abs(len(lens) - len(m["cut_s"])) <= 2)),
        ("컷 길이", "%.2f~%.2f" % (min(lens), max(lens)), "%.1f~%.1f" % (min(m["cut_s"]), max(m["cut_s"])), min(lens) >= min(m["cut_s"]) * CUT_MIN_K and max(lens) <= max(m["cut_s"]) * CUT_MAX_K),   # 원본 최단·최장 ±15%
        ("말 속도", "%.1f자/초" % (chars / (dur - m["thumb_s"])), "%.1f자/초" % (m["chars"] / (m["total_s"] - m["thumb_s"])),
         abs(chars / (dur - m["thumb_s"]) - m["chars"] / (m["total_s"] - m["thumb_s"])) <= 1.2),
        ("소리 크기", "%.1f LUFS" % (lufs(out) or 0), "%.1f LUFS" % m["lufs"], abs((lufs(out) or 0) - m["lufs"]) <= 1.0),
        ("다시 받아쓰기", "일치" if not heard else "다른 곳: " + heard + (" (귀로 확인)" if same and "→" in heard.split("발음 같음")[0] else ""), "대본 그대로", same),
        ("입체 움직임", "%s%%" % "~".join(str(x) for x in (min(p for p in px if p is not None), max(p for p in px if p is not None))), "26~53%", None),
    ]
    rep = {"rows": [{"항목": a, "우리": b, "원본": c, "통과": d} for a, b, c, d in rows], "parallax": px, "cut_s": lens}
    (job / "check.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return rep
