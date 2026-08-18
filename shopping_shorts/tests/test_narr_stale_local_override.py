# -*- coding: utf-8 -*-
"""저장한 대본이 새로고침하면 옛 문장으로 되돌아가던 것 (2026-08-19 사장님 제보 2차).

증상: [✏ 대본수정]으로 고쳐 저장하면 "✅ 칸 1 대본·음성·자막 반영 완료"까지 떴는데,
      화면의 문장과 자막은 **옛것 그대로**다. 새로고침해도 옛 문장이 돌아온다.

★근본 원인(코드 실측):
  · 화면 문장은 narrOf(i) → `NARR[i] != null ? NARR[i] : DATA.beats[i].narration`
    = **로컬 오버라이드(NARR)가 서버 값을 이긴다.**
  · saveNarr()는 저장 성공 시 `delete NARR[i]`를 하지만, 그 전에 이미
    saveWork()가 NARR을 localStorage(`narr`)에 적어둔 적이 있다.
  · 새로고침 → loadWork()가 `Object.assign(NARR, w.narr)`로 **옛 문장을 되살린다**
    → 서버에 저장된 새 문장이 화면에서 영원히 가려진다(자막은 서버 것이라 짝이 안 맞는다).

계약: 서버 문장(DATA.beats[i].narration)이 진실이다. 로컬 NARR 항목이 서버와 다르면
      **이미 서버에 반영된 것**이므로 되살리지 않는다(=버린다).
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parents[1] / "static" / "scene_lab.html"
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node 없음")


def _grab(pat, src, what):
    m = re.search(pat, src, re.S)
    assert m, f"{what} 를 scene_lab.html에서 못 찾았다 — 이름이 바뀌었나?"
    return m.group(0)


def _harness(body):
    lab = LAB.read_text(encoding="utf-8")
    keep = [
        _grab(r"function _pruneStaleNarr\([^)]*\)\{.*?\n\}", lab, "_pruneStaleNarr"),
        _grab(r"function narrOf\(i\)\{.*?\n\}", lab, "narrOf"),
    ]
    pre = """
const NARR = {};
let DATA = {beats:[{narration:'서버-새문장'},{narration:'둘째-서버'}]};
"""
    code = pre + "\n".join(keep) + "\n" + body
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(code)
        path = fh.name
    # ★encoding 명시 — 안 주면 윈도우 기본 cp949로 읽어 한글 출력에서 UnicodeDecodeError.
    r = subprocess.run(["node", path], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, (r.stderr or r.stdout)
    return (r.stdout or "").strip()


def test_서버와_다른_옛_로컬문장은_버린다():
    """이게 깨지면 저장한 대본이 새로고침마다 옛 문장으로 되돌아간다(제보의 본체)."""
    out = _harness("""
      NARR[0] = '옛-로컬문장';          // localStorage에서 되살아난 값
      _pruneStaleNarr();
      console.log(JSON.stringify({shown: narrOf(0), has: (0 in NARR)}));
    """)
    d = __import__("json").loads(out)
    assert d["shown"] == "서버-새문장", "옛 로컬문장이 서버 문장을 계속 가린다"
    assert d["has"] is False, "옛 NARR 항목이 남아 다음 저장에도 되살아난다"


def test_서버와_같은_값은_지워도_무해하다():
    out = _harness("""
      NARR[0] = '서버-새문장';
      _pruneStaleNarr();
      console.log(JSON.stringify({shown: narrOf(0)}));
    """)
    assert __import__("json").loads(out)["shown"] == "서버-새문장"


def test_칸이_여러개여도_각각_판정한다():
    out = _harness("""
      NARR[0] = '옛-로컬0';
      NARR[1] = '옛-로컬1';
      _pruneStaleNarr();
      console.log(JSON.stringify({a: narrOf(0), b: narrOf(1)}));
    """)
    d = __import__("json").loads(out)
    assert d["a"] == "서버-새문장" and d["b"] == "둘째-서버"


def test_없는_칸_인덱스에도_죽지_않는다():
    """옛 저장본이 칸 수가 다른 job의 것일 수 있다 — 죽으면 화면이 통째로 안 뜬다."""
    out = _harness("""
      NARR[9] = '없는칸';
      _pruneStaleNarr();
      console.log(JSON.stringify({ok:true, has:(9 in NARR)}));
    """)
    d = __import__("json").loads(out)
    assert d["ok"] is True


def test_loadWork가_되살린_직후_반드시_정리한다():
    """정리 함수가 있어도 loadWork/loadSaved가 안 부르면 의미가 없다(배선 검사)."""
    src = LAB.read_text(encoding="utf-8")
    for fn in ("loadWork", "loadSaved"):
        m = re.search(r"function " + fn + r"\(\)\{.*?\n\}", src, re.S)
        assert m, f"{fn} 을 못 찾았다"
        assert "_pruneStaleNarr" in m.group(0), \
            f"{fn} 가 NARR을 되살린 뒤 _pruneStaleNarr()를 안 부른다"
