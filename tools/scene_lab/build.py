# -*- coding: utf-8 -*-
"""로컬 장면교체 실험 페이지 빌더 (v3 — UI 원본은 제작소 정식 화면과 공유).

data.json(서버 실데이터) + thumbs/*.jpg 를 읽어 자립형 index.html을 만든다.
file://에서 fetch가 막히므로 데이터는 HTML 안에 인라인으로 박는다.

★v3(2026-08-15, 제작소 이식): UI 템플릿은 이제 **shopping_shorts/static/scene_lab.html
하나뿐**이다 — 제작소 2단계(영상대본MIX)가 iframe으로 띄우는 그 파일. 여기는 그 파일을
읽어 <script id="scene-lab-data">null</script> 자리에 데이터만 인라인한다.
같은 화면이 build.py와 static에 두 벌로 있으면 반드시 어긋난다(0순위-B) — UI를 고칠 땐
scene_lab.html만 고치면 로컬 실험실·제작소 둘 다 바뀐다.
"""
import json
import sys
from pathlib import Path

# 인자로 잡 폴더를 받는다(fetch.py가 out/<job_id>를 넘긴다). 없으면 이 파일 옆(옛 방식).
BASE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).parent
ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "shopping_shorts" / "static" / "scene_lab.html"

data = json.loads((BASE / "data.json").read_text(encoding="utf-8"))
# ★사람이 대본을 읽고 직접 고른 배치(선택). picks.json이 있으면 ④번 모드로 노출한다.
#   fetch가 data.json을 덮어써도 이 파일은 남아 배치가 유지된다.
_picks = BASE / "picks.json"
data["picks"] = json.loads(_picks.read_text(encoding="utf-8")) if _picks.exists() else None
# ★PC를 옮겨도 조립이 따라오게(2026-08-14 사장님 "집 가서 하게"). 브라우저 저장(localStorage)은
#   그 PC에만 남는다. tools/scene_lab/saved/<job>.json은 git이 추적하므로 다른 PC에서 받으면
#   그대로 열린다. 그 PC에 더 최근 편집이 있으면 그쪽이 이긴다(loadWork 참조).
_saved = Path(__file__).resolve().parent / "saved" / (BASE.name + ".json")
data["saved"] = json.loads(_saved.read_text(encoding="utf-8")) if _saved.exists() else None
# (자막을 음성 길이에서 잘라 그리는 표시 보정은 scene_lab.html의 normalizeData()가 한다 —
#  예전엔 여기 파이썬에도 같은 클램프가 있었는데 서버 모드가 생기며 한 곳으로 모았다.)

html = TEMPLATE.read_text(encoding="utf-8")
_SLOT = '<script id="scene-lab-data" type="application/json">null</script>'
if _SLOT not in html:
    sys.exit(f"[중단] 데이터 슬롯이 템플릿에 없다: {TEMPLATE}")
# </script>가 JSON 텍스트 안에 있으면 태그가 조기 종료된다 — <를 이스케이프해 봉인.
_payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
html = html.replace(
    _SLOT, '<script id="scene-lab-data" type="application/json">' + _payload + "</script>")

out = BASE / "index.html"
out.write_text(html, encoding="utf-8")
print("wrote", out, len(html), "bytes")
