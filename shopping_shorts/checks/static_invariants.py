"""L0 정적 불변식 - 브라우저.서버 없이 파일만 읽어 판정한다(설계 B-58~62.B-70).
실행 전 코드 상태를 보는 것이므로 게이트에서도 항상 돈다.

판단 불가는 GRAY다(RED 아님) - 패턴을 못 찾았다고 빨강을 내면 거짓 경보가 된다.
"""
import re
from pathlib import Path

from shopping_shorts.checks.verdict import GREEN, RED, GRAY, Result

_ARR = ("STEP_LABELS", "STEP_SHORT", "STEP_COLORS", "STEP_ICONS")


def _extract_js_array_src(html, name):
    """`const NAME = [ ... ];` 원문을 대괄호 깊이를 세어 정확히 뽑는다.

    단순 비탐욕 정규식(.*?];)은 STEP_ICONS(SVG 문자열 안 내용)에서 잘못된 위치에서
    끊길 위험이 있어, 문자열 리터럴을 건너뛰며 대괄호 깊이가 0으로 돌아오는 지점을 찾는다.
    """
    m = re.search(r"const\s+" + re.escape(name) + r"\s*=\s*\[", html)
    if not m:
        return None
    start = m.end() - 1  # '[' 위치
    depth = 0
    i = start
    in_str = None
    esc = False
    while i < len(html):
        ch = html[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == in_str:
                in_str = None
        else:
            if ch in ("'", '"', "`"):
                in_str = ch
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return html[start:i + 1]
        i += 1
    return None


def _count_top_level_items(arr_src):
    """대괄호 원문에서 최상위 콤마로만 나눠 항목 수를 센다(문자열 안 콤마.중첩 배열은 무시)."""
    inner = arr_src.strip()
    if inner.startswith("["):
        inner = inner[1:]
    if inner.endswith("]"):
        inner = inner[:-1]
    depth = 0
    in_str = None
    esc = False
    items = 0
    cur_has_content = False
    i = 0
    n = len(inner)
    while i < n:
        ch = inner[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == in_str:
                in_str = None
            cur_has_content = True
            i += 1
            continue
        # 문자열 밖: 주석은 항목이 아니므로 건너뛴다(트레일링 콤마 뒤 // 코멘트가
        # "유령 항목"으로 잡혀 개수를 부풀리는 함정을 막는다).
        if ch == "/" and i + 1 < n and inner[i + 1] == "/":
            j = inner.find("\n", i)
            i = n if j == -1 else j
            continue
        if ch == "/" and i + 1 < n and inner[i + 1] == "*":
            j = inner.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        if ch in ("'", '"', "`"):
            in_str = ch
            cur_has_content = True
        elif ch in "[{(":
            depth += 1
            cur_has_content = True
        elif ch in "]})":
            depth -= 1
            cur_has_content = True
        elif ch == "," and depth == 0:
            if cur_has_content:
                items += 1
            cur_has_content = False
        elif not ch.isspace():
            cur_has_content = True
        i += 1
    if cur_has_content:
        items += 1
    return items


def _js_array_len(html, name):
    src = _extract_js_array_src(html, name)
    if src is None:
        return None
    return _count_top_level_items(src)


def check_step_arrays(html):
    lens = {a: _js_array_len(html, a) for a in _ARR}
    if any(v is None for v in lens.values()):
        missing = [a for a, v in lens.items() if v is None]
        return Result("L0", "단계바 배열 4개 길이 일치", GRAY,
                       reason="배열 못 찾음 %s (전체 %s)" % (missing, lens), signature="L0:step_arrays")
    if len(set(lens.values())) == 1:
        return Result("L0", "단계바 배열 4개 길이 일치", GREEN, reason=str(lens), signature="L0:step_arrays")
    ref = lens["STEP_LABELS"]
    bad = [a for a, n in lens.items() if n != ref]
    return Result("L0", "단계바 배열 4개 길이 일치", RED,
                   reason="%s 길이가 다름 %s" % (bad, lens), signature="L0:step_arrays")


def check_orb_permutation(html):
    """ORB_TO_PANEL이 0..N-1의 순열인지, PANEL_BY_KEY 값 집합과 일치하는지 본다."""
    m = re.search(r"const\s+ORB_TO_PANEL\s*=\s*\[([^\]]*)\]", html)
    k = re.search(r"const\s+PANEL_BY_KEY\s*=\s*\{([^}]*)\}", html)
    if not m or not k:
        return Result("L0", "오브-패널 매핑 순열", GRAY, reason="상수 못 찾음", signature="L0:orb_permutation")
    orb = [int(x) for x in re.findall(r"-?\d+", m.group(1))]
    keys = [int(x) for x in re.findall(r":\s*(-?\d+)", k.group(1))]
    if not orb or not keys:
        return Result("L0", "오브-패널 매핑 순열", GRAY, reason="상수는 찾았지만 값이 비어있음", signature="L0:orb_permutation")
    is_perm = sorted(orb) == list(range(len(orb)))
    keys_match = sorted(keys) == sorted(orb)
    ok = is_perm and keys_match
    reason = "ORB_TO_PANEL=%s(순열=%s) PANEL_BY_KEY값=%s(일치=%s)" % (orb, is_perm, sorted(keys), keys_match)
    return Result("L0", "오브-패널 매핑 순열", GREEN if ok else RED, reason=reason, signature="L0:orb_permutation")


def check_reap_vs_deploy(store_src, deploy_src):
    """store.reap_stale(기본값)과 deploy의 배포-진행중 판정(worker busy) 분(分) 값을 비교한다.

    prewarm_busy(2분)은 다른 목적(담기분석)이라 대상이 아니다. 'task IN (...'mix'...)' 블록만 본다.
    """
    r = re.search(r"def\s+reap_stale\(self,\s*minutes\s*=\s*(\d+)", store_src)
    d = re.search(r"task\s+IN\s*\([^)]*'mix'[^)]*\).*?-(\d+)\s*minutes", deploy_src, re.S)
    if not r or not d:
        return Result("L0", "reap_stale < 배포 busy(worker) 대기시간", GRAY,
                       reason="상수 못 찾음", signature="L0:reap_vs_deploy")
    reap, busy = int(r.group(1)), int(d.group(1))
    ok = reap < busy
    return Result("L0", "reap_stale < 배포 busy(worker) 대기시간", GREEN if ok else RED,
                  reason="reap_stale=%s분 busy=%s분" % (reap, busy), signature="L0:reap_vs_deploy")


_SPEECH_RATE_DEF = re.compile(r"^_SYLLABLES_PER_SEC\s*=\s*5\.7\s*(?:#.*)?$", re.M)


def check_speech_rate_single(py_sources):
    """말속도 정본 상수(`_SYLLABLES_PER_SEC = 5.7`) 정의가 한 곳(edit_plan.py)뿐인지 본다.

    문자열 리터럴.주석 안의 '5.7'(예: "5.7 x 1.44" 설명문)은 정의가 아니므로 세지 않는다.
    실제 대입문(줄 시작이 `_SYLLABLES_PER_SEC = 5.7`)만 앵커로 매칭한다.
    """
    hits = [f for f, src in py_sources.items() if _SPEECH_RATE_DEF.search(src)]
    if not hits:
        return Result("L0", "말속도 상수 정의가 한 곳뿐인가", GRAY,
                       reason="정의를 못 찾음(상수명이 바뀌었을 수 있음)", signature="L0:speech_rate_single")
    ok = len(hits) == 1
    return Result("L0", "말속도 상수 정의가 한 곳뿐인가", GREEN if ok else RED,
                  reason="정의처 %s" % sorted(hits), signature="L0:speech_rate_single")


_TTS_PATH_DEF = re.compile(r"^def\s+_beat_tts_path\(", re.M)


def check_tts_path_single(py_sources):
    """TTS 파일명 판단 함수(`_beat_tts_path`) 정의가 한 곳뿐인지 본다."""
    hits = [f for f, src in py_sources.items() if _TTS_PATH_DEF.search(src)]
    if not hits:
        return Result("L0", "TTS 파일명 판단처가 한 곳뿐인가", GRAY,
                       reason="정의를 못 찾음(함수명이 바뀌었을 수 있음)", signature="L0:tts_path_single")
    ok = len(hits) == 1
    return Result("L0", "TTS 파일명 판단처가 한 곳뿐인가", GREEN if ok else RED,
                  reason="정의처 %s" % sorted(hits), signature="L0:tts_path_single")


def check_cut_count_rule(plan):
    """컷 수 = 구절(beats) 수 = 자막(captions) 줄 수. 셋 중 하나가 없으면 판단 불가(회색)."""
    if plan is None:
        return Result("L0", "컷 수 = 구절 수 = 자막 줄 수", GRAY,
                       reason="관측 대상 없음 — mix_jobs.edit_plan_json에는 beats만 있고 "
                              "cuts·captions에 대응하는 필드가 이 코드베이스에 없다(2026-09-07 실측). "
                              "실제 plan을 물릴 수 있게 되기 전까지는 항상 회색.",
                       signature="L0:cut_count_rule")
    if not isinstance(plan, dict):
        return Result("L0", "컷 수 = 구절 수 = 자막 줄 수", GRAY, reason="plan이 dict가 아님", signature="L0:cut_count_rule")
    beats, cuts, caps = plan.get("beats"), plan.get("cuts"), plan.get("captions")
    if beats is None or cuts is None or caps is None:
        missing = [k for k, v in (("beats", beats), ("cuts", cuts), ("captions", caps)) if v is None]
        return Result("L0", "컷 수 = 구절 수 = 자막 줄 수", GRAY,
                       reason="필드 없음 %s" % missing, signature="L0:cut_count_rule")
    nb, nc, ncap = len(beats), len(cuts), len(caps)
    ok = nb == nc == ncap
    return Result("L0", "컷 수 = 구절 수 = 자막 줄 수", GREEN if ok else RED,
                  reason="beats=%s cuts=%s captions=%s" % (nb, nc, ncap), signature="L0:cut_count_rule")


def run_all(repo):
    """실제 저장소 파일을 읽어 6개 정적 불변식을 전부 돌린다."""
    repo = Path(repo)
    html = (repo / "shopping_shorts/static/produce.html").read_text(encoding="utf-8")
    store = (repo / "shopping_shorts/store.py").read_text(encoding="utf-8")
    dep = (repo / "deploy/auto_deploy.sh").read_text(encoding="utf-8")
    py_sources = {}
    for p in (repo / "shopping_shorts").glob("*.py"):
        try:
            py_sources[str(p.relative_to(repo)).replace("\\", "/")] = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

    # ★리뷰 지적(2026-09-07): 커밋된 픽스처(fixtures/plan_min.json, beats=cuts=captions=2)를
    # 매 run 그대로 물리면 실제 렌더 결과를 절대 관측하지 않아 이 검사가 구조적으로 영원히
    # 초록이다. cuts·captions에 대응하는 실필드가 이 코드베이스에 없어(store.py·edit_plan.py
    # 전수 확인) 지금은 진짜 plan을 물릴 수 없다 — 가짜 초록보다 이유 있는 회색이 낫다(check_cut_count_rule(None)).
    plan = None

    return [
        check_step_arrays(html),
        check_orb_permutation(html),
        check_reap_vs_deploy(store, dep),
        check_speech_rate_single(py_sources),
        check_tts_path_single(py_sources),
        check_cut_count_rule(plan),
    ]
