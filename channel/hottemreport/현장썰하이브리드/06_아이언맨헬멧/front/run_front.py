# -*- coding: utf-8 -*-
"""06 앞 현장썰 렌더 = 현장썰_run.py render 그대로 + 한 가지만: 렌더용 한 문장(대본_render.json)의 '?' 를 뺀다.
왜: 1편 make_render 는 줄을 한 문장으로 이어 narr_video.build 에 넘기는데(쉼표·끝 마침표만 지움), N1 '…아니라고요?' 의 '?' 가
문장 경계로 읽혀 컷이 2개 필요해져 '재료 컷 1개 < 필요한 컷 2개' 로 멈췄다(10-21 실측). TTS 는 이미 '?' 그대로 읽혔고
화면 자막은 caption_events 가 정하므로 렌더용 문장에서만 빼면 된다. 공용 파일은 안 고친다.
    PYTHONUTF8=1 py channel/hottemreport/현장썰하이브리드/06_아이언맨헬멧/front/run_front.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from tools.calcopy import narr_video as nv  # noqa: E402

_orig = nv.build


def _build(plan):
    p = Path(plan["script"])
    S = json.loads(p.read_text(encoding="utf-8"))
    for l in S["final"]["lines"]:
        l["text"] = l["text"].replace("?", "")
    p.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
    return _orig(plan)


nv.build = _build
sys.argv = [str(ROOT / "channel/hottemreport/현장썰_run.py"), "현장썰하이브리드/06_아이언맨헬멧/front", "render"]
import importlib.util  # noqa: E402
spec = importlib.util.spec_from_file_location("hj_run", sys.argv[0])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.main()
