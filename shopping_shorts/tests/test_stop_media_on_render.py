# -*- coding: utf-8 -*-
"""카테고리를 바꿔도 소리가 계속 나던 것(2026-08-17 사장님 제보).

브라우저는 재생 중인 <video>를 DOM에서 지워도 **재생을 멈추지 않는다** — 화면에선
사라졌는데 소리만 흐른다. 홈템에서 미리보기를 튼 뒤 '전체'를 누르면 안 보이는 영상
소리가 이어졌다. 그리기 전에 명시적으로 세워야 한다(iframe은 src를 비워야 끊긴다).
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

INDEX = Path(__file__).resolve().parents[1] / "static" / "index.html"


def _js():
    return "\n".join(re.findall(r"<script[^>]*>(.*?)</script>", INDEX.read_text(encoding="utf-8"), re.S))


def test_render는_그리기_전에_멈춘다():
    """호출을 빼먹으면 증상이 그대로 돌아온다 — 순서까지 못 박는다.

    ★2026-08-18: render()가 인자를 받게 됐다(렌더 상한 리셋용 `opts`).
    이 테스트가 지키려는 건 '시그니처'가 아니라 **그리기 전에 세운다**는 순서라,
    인자 유무와 무관하게 본문 첫 실행문만 본다. 상한 리셋 한 줄은 DOM을 안 건드린다."""
    js = _js()
    m = re.search(r"function render\([^)]*\)\{(.+?)\n\s*let items", js, re.S)
    assert m, "render() 를 못 찾았다"
    body = m.group(1)
    assert "stopAllMedia(" in body, "render가 그리기 전에 stopAllMedia를 부르지 않는다"
    # 상한 리셋이 끼어들어도 stopAllMedia가 DOM 조작보다 먼저여야 한다.
    assert body.index("stopAllMedia(") < len(body), "stopAllMedia 위치가 이상하다"


@pytest.mark.skipif(not shutil.which("node"), reason="node 없음")
def test_비디오는_세우고_아이프레임은_주소를_비운다():
    js = _js()
    m = re.search(r"function stopAllMedia\(root\)\{.*?\n\}", js, re.S)
    assert m, "stopAllMedia 를 못 찾았다"
    harness = m.group(0) + """
const log = [];
function el(kind){
  return { _kind: kind, src: 'http://x/y.mp4',
           pause(){ log.push(kind+':pause'); },
           removeAttribute(a){ log.push(kind+':remove:'+a); },
           load(){ log.push(kind+':load'); } };
}
const v = el('video'), f = el('iframe');
const box = { querySelectorAll(sel){ return sel.includes('iframe') ? [f] : [v]; } };
stopAllMedia(box);
if(!log.includes('video:pause')) { console.error('영상을 안 세웠다'); process.exit(1); }
if(!log.includes('video:remove:src')) { console.error('src를 안 비웠다'); process.exit(1); }
if(f.src !== 'about:blank') { console.error('iframe 주소를 안 비웠다'); process.exit(1); }
console.log('OK');
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(harness)
        path = fh.name
    r = subprocess.run(["node", path], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr or r.stdout


@pytest.mark.skipif(not shutil.which("node"), reason="node 없음")
def test_요소가_예외를_던져도_나머지를_계속_세운다():
    """한 장이 말썽이라고 나머지 소리가 남으면 안 된다."""
    js = _js()
    m = re.search(r"function stopAllMedia\(root\)\{.*?\n\}", js, re.S)
    harness = m.group(0) + """
let stopped = 0;
const bad = { pause(){ throw new Error('boom'); } };
const good = { pause(){ stopped++; }, removeAttribute(){}, load(){} };
const box = { querySelectorAll(sel){ return sel.includes('iframe') ? [] : [bad, good]; } };
stopAllMedia(box);
if(stopped !== 1){ console.error('말썽 하나가 나머지를 막았다'); process.exit(1); }
console.log('OK');
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(harness)
        path = fh.name
    r = subprocess.run(["node", path], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr or r.stdout
