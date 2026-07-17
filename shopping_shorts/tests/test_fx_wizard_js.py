"""고급효과 위저드 JS 검증 — produce.html의 실 <script>를 node로 돌려 확인.
저장소 선례(test_produce_category_race.py) 방식: 실 소스를 잘라 node에 넘긴다."""
import os
import re
import subprocess
import tempfile

HTML = os.path.join(os.path.dirname(__file__), "..", "static", "produce.html")


def _script_src():
    src = open(HTML, encoding="utf-8").read()
    m = re.findall(r"<script>(.*?)</script>", src, re.S)
    assert m, "produce.html <script> 없음"
    return "\n".join(m)


def test_produce_html_script_parses():
    """전체 <script>가 문법오류 없이 파싱된다(위저드 추가로 안 깨졌는지)."""
    js = _script_src()
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
        path = f.name
    try:
        r = subprocess.run(["node", "--check", path], capture_output=True, text=True,
                           stdin=subprocess.DEVNULL)
        assert r.returncode == 0, "node --check 실패:\n" + (r.stderr or "")
    finally:
        os.unlink(path)


def _extract_fn(name):
    src = _script_src()
    m = re.search(r"function %s\s*\([^)]*\)\s*\{.*?\n\}" % re.escape(name), src, re.S)
    assert m, f"{name} 함수 없음"
    return m.group(0)


def test_fx_plan_summary_counts_effects():
    """fxPlanSummary가 테마·효과개수를 정확히 뽑는다."""
    fn = _extract_fn("fxPlanSummary")
    script = fn + '\nconsole.log(JSON.stringify(fxPlanSummary({themeName:"warm",fx:[1,2,3]})));'
    r = subprocess.run(["node", "-e", script], capture_output=True, text=True,
                       stdin=subprocess.DEVNULL)
    assert r.returncode == 0, (r.stderr or "")
    out = r.stdout.strip()
    assert '"theme":"warm"' in out and '"count":3' in out, out


def test_fx_plan_summary_empty_fx():
    """fx 없으면 count 0."""
    fn = _extract_fn("fxPlanSummary")
    script = fn + '\nconsole.log(JSON.stringify(fxPlanSummary({themeName:"tech"})));'
    r = subprocess.run(["node", "-e", script], capture_output=True, text=True,
                       stdin=subprocess.DEVNULL)
    assert r.returncode == 0, (r.stderr or "")
    assert '"count":0' in r.stdout, r.stdout
