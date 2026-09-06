# -*- coding: utf-8 -*-
"""✋ 수동 길이가 **다른 컷을 죽이지 않는다** + 잘라낸 만큼 다음 컷이 앞당겨진다.

★버그 3건(2026-09-06 사장님 실사용 제보):
  ① ✋를 2.5초 이상으로 잡으면 나머지 컷이 0.3초로 눌려 화면에 0.0으로 뜬다
     — 조각이 통째로 사라진 것처럼 보였다. 오늘 MANUAL_MIN(0.3)을 **나머지 컷 몫**
     에까지 쓴 탓이다(종전 MIN_CLIP 0.8). "수동 존중"이 남의 컷을 죽였다.
  ② setFix가 구절맞춤을 말없이 꺼서 컷 배분 규칙이 통째로 바뀌었다.
  ③ 앞 컷을 줄여도 다음 컷의 start가 그대로라 **잘라낸 화면이 다음 컷 앞에 남는다**
     ("여전히 같은 장면이 나온다").

규칙: ✋로 정한 컷은 0.3초까지 짧아질 수 있지만(사장님 요청 유지),
      **손대지 않은 컷**은 FREE_MIN(0.6초)을 보장받는다.
"""
import json
import re
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "static" / "scene_play.js"


def _fn_src(name):
    """`function <name>(`부터 그 함수를 닫는 최상위 `}`까지 — 중괄호를 세어 정확히 뗀다.
    ★마커 문자열로 자르면 블록 중간이 잘려 SyntaxError가 난다(실제로 겪었다)."""
    lines = JS.read_text(encoding="utf-8").splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith(f"function {name}("):
            # ★한 줄 함수(`function f(){ ... }`)는 그 줄에서 depth가 0으로 돌아온다.
            #   `j > i` 조건을 걸면 그 줄을 놓치고 **다음 함수까지 삼켜** 중복 선언이 된다.
            depth, opened = 0, False
            for j in range(i, len(lines)):
                depth += lines[j].count("{") - lines[j].count("}")
                if lines[j].count("{"):
                    opened = True
                if opened and depth == 0:
                    return "\n".join(lines[i:j + 1])
            raise AssertionError(f"{name}의 끝을 못 찾았다")
    raise AssertionError(f"{name}을 못 찾았다 — 이름이 바뀌었으면 이 테스트부터 고쳐라")


def _consts():
    """계산에 필요한 최상위 상수 선언만(함수 밖, 파일 앞부분).
    ★줄 끝 주석을 떼어낸다 — 한글 주석이 붙은 채로 슬라이스하면 SyntaxError가 난다."""
    out = []
    for ln in JS.read_text(encoding="utf-8").splitlines()[:40]:
        if not ln.startswith("const ") or "=" not in ln:
            continue
        bare = re.sub(r"\s*//.*$", "", ln).rstrip()
        # ★한 줄로 끝나는 선언만(`const SL = {` 처럼 블록을 여는 줄은 제외).
        if bare.endswith(";"):
            out.append(bare)
    return "\n".join(out)


def run_js(script):
    """★node -e 대신 파일로 넘긴다 — 윈도우 명령줄 상한(32,767자)에 걸린다."""
    tmp = Path(__file__).parent / "_tmp_fixlen.mjs"
    tmp.write_text(script, encoding="utf-8")
    try:
        r = subprocess.run(["node", str(tmp)], capture_output=True, text=True,
                           encoding="utf-8", timeout=60)
        assert r.returncode == 0, r.stderr[-800:]
        return json.loads(r.stdout)
    finally:
        tmp.unlink(missing_ok=True)


def _harness(cases):
    """scene_play.js의 상수 + applyFixedLens를 떼어와 케이스를 돌린다."""
    # ★한 줄짜리 함수는 그 줄 자체가 완결이라 _fn_src가 같은 줄을 두 번 담을 수 있다
    #   → 중복 선언(SyntaxError). 순서를 지키며 겹치는 조각을 걷어낸다.
    chunks, seen = [], set()
    for name in ("fixKey", "getFix", "applyFixedLens"):
        src = _fn_src(name)
        if src in seen:
            continue
        seen.add(src)
        chunks.append(src)
    parts = "\n".join([_consts(), "const FIXLEN = {};"] + chunks)
    return run_js(f"""
{parts}
const CASES = {json.dumps(cases)};
const out = CASES.map(cs => {{
  for (const k of Object.keys(FIXLEN)) delete FIXLEN[k];
  for (const [sid, v] of Object.entries(cs.fix)) FIXLEN['0:' + sid] = v;
  const clips = cs.clips.map(c => ({{...c}}));
  applyFixedLens(clips, 0, cs.tts);
  return clips.map(c => ({{seg_id: c.seg_id, dur: +c.dur.toFixed(3),
                          start: +(c.start ?? 0).toFixed(3)}}));
}});
console.log(JSON.stringify(out));
""")


BASE = [{"seg_id": "6-2", "dur": 1.2, "start": 0.0},
        {"seg_id": "6-4", "dur": 1.6, "start": 5.0}]


class Test다른컷이_사라지지않는다:
    @pytest.mark.parametrize("fix", [2.0, 2.4, 2.5, 2.8, 3.5])
    def test_손대지않은_컷은_보이는_길이를_지킨다(self, fix):
        """★이게 제보의 핵심 — ✋를 크게 잡아도 남의 컷이 0.0이 되면 안 된다."""
        out = _harness([{"tts": 2.8, "fix": {"6-4": fix}, "clips": BASE}])[0]
        free = next(c for c in out if c["seg_id"] == "6-2")
        assert free["dur"] >= 0.6 - 1e-6, f"✋{fix}초에서 남의 컷이 {free['dur']}초로 눌렸다"

    def test_합계는_칸_길이를_지킨다(self):
        for fix in (1.0, 2.0, 2.5, 3.5):
            out = _harness([{"tts": 2.8, "fix": {"6-4": fix}, "clips": BASE}])[0]
            assert sum(c["dur"] for c in out) == pytest.approx(2.8, abs=1e-6)

    def test_수동_컷은_여전히_짧게_지정할_수_있다(self):
        """사장님 요청(1초 미만 수동 허용)은 그대로 살아 있어야 한다."""
        out = _harness([{"tts": 2.8, "fix": {"6-2": 0.5}, "clips": BASE}])[0]
        fixed = next(c for c in out if c["seg_id"] == "6-2")
        assert fixed["dur"] == pytest.approx(0.5, abs=1e-6)


class Test잘라낸만큼_다음컷이_앞당겨진다:
    def test_앞컷을_줄이면_다음컷_start가_당겨진다(self):
        """③ 종전엔 dur만 고치고 start를 그대로 둬 잘라낸 화면이 다음 컷 앞에 남았다.
        같은 소스에서 이어지는 컷이면 start도 따라와야 한다."""
        clips = [{"seg_id": "a", "video_id": "v", "dur": 1.5, "start": 0.0},
                 {"seg_id": "a", "video_id": "v", "dur": 1.3, "start": 1.5}]
        out = _harness([{"tts": 2.8, "fix": {"a": 1.0}, "clips": clips}])[0]
        # 앞 컷이 1.0초로 줄었으면 다음 컷은 1.0초 지점에서 시작해야 한다
        assert out[1]["start"] == pytest.approx(1.0, abs=1e-6), \
            f"start가 {out[1]['start']} — 잘라낸 0.5초가 다음 컷 앞에 그대로 남는다"

    def test_다른_소스면_start를_건드리지_않는다(self):
        """이어지지 않는 조각은 제 시작점을 지켜야 한다(엉뚱한 데서 재생되면 안 된다)."""
        out = _harness([{"tts": 2.8, "fix": {"6-4": 2.0}, "clips": BASE}])[0]
        assert next(c for c in out if c["seg_id"] == "6-4")["start"] == pytest.approx(5.0)


def test_setFix가_구절맞춤을_말없이_끄지_않는다():
    """② ✋를 만졌다고 컷 배분 규칙 전체가 바뀌면 사용자가 이유를 알 수 없다."""
    src = JS.read_text(encoding="utf-8")
    body = src[src.index("function setFix("):]
    body = body[:body.index("\n}")]
    code = "\n".join(re.sub(r"//.*$", "", ln) for ln in body.splitlines())
    assert "PHRASE_SYNC" not in code, \
        "setFix가 아직 구절맞춤을 끈다 — ✋는 길이만 정해야 한다"
