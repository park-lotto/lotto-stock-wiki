# -*- coding: utf-8 -*-
"""2단계 [📢 CTA] 버튼 흐름 점검(관제 45) — produce.html의 **실제 함수**를 떼어 node로 돌린다.

처음 상태(서버 guess_cta_index) → 확정 시 3단계로 가는 cta_line/cta_text → 끄기 → 다른 줄 켜기 →
빈 줄을 건너뛴 번호 → 안 정한 안은 null. 실패하면 rc=1.

    py tools/cta_mark_ui_check.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from shopping_shorts.edit_plan import guess_cta_index  # noqa: E402

SRC = open(os.path.join(ROOT, "shopping_shorts", "static", "produce.html"), encoding="utf-8").read()
NAMES = ["s2Beats", "s2TitleSplitOn", "s2VisualRole", "s2NarrationBeats", "s2VisualSubline", "s2VisualTitle",
         "s2ScriptLines", "s2DraftContract", "s2ApplyDraftContract", "s2EnsureCtaGuess", "s2ToggleCta"]


def fn(name):
    m = re.search(r"\n((?:async )?function " + name + r"\([^)]*\)\{)", SRC)
    assert m, name
    i = m.start(1)
    k = SRC.index("{", i)
    depth = 0
    while True:
        c = SRC[k]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return SRC[i:k + 1]
        k += 1


# 김성현님 3b4111969ac4 마지막 두 칸(라이브 원문, NBSP 포함)
LINES = ["직장인 사이에 난리난 주름 5초컷", "궁금하신 분들은\xa0 '주름'이라고 남겨주세요."]
ROLES = ["반전", "마무리"]
HARNESS = """
let _s2CtaAsking=false; const STATE={}; let renders=0;
const S2={drafts:[{style_id:73,beats:%(beats)s}],curDraft:0};
function s2RenderDrafts(){ renders++; } function saveWork(){} function toast(m){}
const SERVER_IDX=%(idx)s;
global.fetch=async(url,opt)=>({json:async()=>({ok:true,idx:JSON.parse(opt.body).drafts.map(()=>SERVER_IDX)})});
%(code)s
const out={};
(async()=>{
  await s2EnsureCtaGuess(); out.guess=S2.drafts[0].beats.map(b=>b.cta_mark);
  s2ApplyDraftContract(STATE,S2.drafts[0]); out.auto=[STATE.script_cta_line, STATE.script_cta_text];
  s2ToggleCta(0,1); s2ApplyDraftContract(STATE,S2.drafts[0]); out.off=[S2.drafts[0].beats.map(b=>b.cta_mark), STATE.script_cta_line];
  s2ToggleCta(0,0); s2ApplyDraftContract(STATE,S2.drafts[0]); out.first=[STATE.script_cta_line, STATE.script_cta_text];
  await s2EnsureCtaGuess(); out.noreguess=S2.drafts[0].beats.map(b=>b.cta_mark);
  const S3={}; const dr2={beats:[{role:'hook',text:'a',cta_mark:false},{role:'x',text:'',cta_mark:false},{role:'CTA',text:'댓글',cta_mark:true}]};
  s2ApplyDraftContract(S3,dr2); out.skip=[S3.script_cta_line, S3.script];
  const S4={}; s2ApplyDraftContract(S4,{beats:[{role:'hook',text:'a'}]}); out.undecided=S4.script_cta_line;
  console.log(JSON.stringify(out));
})();
"""

EXPECT = {
    "guess": [False, True],
    "auto": [1, LINES[1]],
    "off": [[False, False], -1],
    "first": [0, LINES[0]],
    "noreguess": [True, False],
    "skip": [1, "a\n댓글"],
    "undecided": None,
}


def main():
    beats = [{"role": r, "text": t} for t, r in zip(LINES, ROLES)]
    js = HARNESS % {"beats": json.dumps(beats, ensure_ascii=False),
                    "idx": json.dumps(guess_cta_index(LINES, ROLES)),
                    "code": "\n".join(fn(n) for n in NAMES)}
    f = os.path.join(tempfile.gettempdir(), "cta_mark_ui_check.js")
    open(f, "w", encoding="utf-8").write(js)
    r = subprocess.run(["node", f], capture_output=True, text=True, encoding="utf-8",
                       stdin=subprocess.DEVNULL, timeout=60)
    if r.returncode:
        print("node 실패:", r.stderr[:800])
        return 1
    got = json.loads(r.stdout.strip().splitlines()[-1])
    bad = {k: (got.get(k), v) for k, v in EXPECT.items() if got.get(k) != v}
    for k in EXPECT:
        print(("OK  " if k not in bad else "FAIL"), k, json.dumps(got.get(k), ensure_ascii=False))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
