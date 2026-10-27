# 손 단계 back_plan (98 #182 ②): render_front 를 한 번 돌려 TTS(s_B*.wav)가 생긴 뒤, 실제 문장 길이로 뒤 컷 표를 본다(렌더 안 함).
#  render_front --plan 은 글자 수 ÷ cps_target 추정이라 실제보다 짧게 보여 '컷이 원본 샷보다 길다'를 못 미리 잡는다.
# PYTHONUTF8=1 py channel/hottemreport/현장썰하이브리드/back_plan.py <잇썸홈판 doc 폴더> <hybrid work 폴더>
import sys
from pathlib import Path
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H.parents[2])); sys.path.insert(0, str(H))
import render_front as RF  # noqa: E402
from tools.calcopy.hybrid.common import jload, dur_of  # noqa: E402
doc, work = Path(sys.argv[1]), Path(sys.argv[2])
S, M = jload(doc / "대본.json"), jload(doc / "재료.json")
R = work / "render"
sent = {l["id"]: dur_of(R / f"s_{l['id']}.wav") for l in S["lines"] if (R / f"s_{l['id']}.wav").exists()}
print("문장 길이", sent)
T = RF.b_timeline(S, M, sent)
for c in T["cuts"]:
    print(f"  {c['line']} {c['t0']:6.2f}~{c['t1']:6.2f} {c['dur']:.3f}s max {c['max']} {'넘침 ' + str(c['over']) if c['over'] > 0 else 'ok'} {c['src']}@{c['ss']}")
print("뒤 끝", T["end"])
