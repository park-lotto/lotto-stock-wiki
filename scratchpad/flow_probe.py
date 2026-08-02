"""소스 전환 지점에서 대사가 끊기는가 — 두 컷 묶기가 흐름을 해치는지 실측.

사장님 우려(2026-08-02): "a1 a2는 기능설명하다가 안 끝났는데 b1 b2는 흐름 안 이어지게
다른 얘기하고 그런 건 없을까?"

재는 것 — 소스가 바뀌는 지점(A→B)과 안 바뀌는 지점(A→A)을 갈라서:
  ① 접속 관계: 뒷 문장이 앞 문장을 받는가(지시어·접속어·주어 생략)
  ② 화제 연속: 앞뒤 문장이 낱말을 공유하는가
  ③ 미완결: 앞 문장이 끝맺지 못하고 잘렸는가

★비교 기준이 있어야 판정이 된다 — 전환 지점이 비전환 지점보다 **나쁘면** 문제고,
  비슷하면 두 컷 묶기 자체는 무해하다(대사는 모델이 전체를 보고 쓰므로).
"""
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shopping_shorts import mix_pipeline, bank_assemble, edit_plan as ep   # noqa: E402
from shopping_shorts.store import Store                                    # noqa: E402
from shopping_shorts.config import DB_PATH                                 # noqa: E402

# 앞 문장을 받는 신호 — 이게 있으면 '이어진다'
_LINKERS = ("그래서", "그러니까", "그런데", "근데", "게다가", "심지어", "덕분에",
            "그리고", "또", "이렇게", "이런", "이게", "이건", "이거", "저는", "여기",
            "그러다", "그랬더니", "하니까", "니까")
# 문장이 끝맺음 없이 잘린 흔적
_UNFINISHED = ("는데", "하고", "라서", "면서", "지만", "고요", "인데")


def _words(txt):
    return {w for w in re.findall(r"[가-힣]{2,}", txt or "")}


def _score_pair(prev, cur):
    """(접속신호, 낱말공유, 미완결) — 각각 0/1."""
    link = 1 if any(cur.strip().startswith(x) or f" {x}" in cur[:14] for x in _LINKERS) else 0
    share = 1 if len(_words(prev) & _words(cur)) >= 1 else 0
    unfin = 1 if prev.rstrip().rstrip(".!?").endswith(_UNFINISHED) else 0
    return link, share, unfin


def _live_args(store, ss):
    return dict(ping_pong=store.get_setting("ping_pong_enabled", "") == "1",
                backbone_base=store.get_setting("backbone_base_enabled", "") == "1",
                judge=True, bank_context=bank_assemble.parts_block(store),
                is_recipe=mix_pipeline._sources_is_recipe(ss))


def main():
    fixtures = sys.argv[1:] or ["scratchpad/fixture_live.json"]
    store = Store(DB_PATH)
    agg = {"switch": [0, 0, 0, 0], "same": [0, 0, 0, 0]}   # [건수, link, share, unfin]

    for fx in fixtures:
        raw = json.load(open(fx, encoding="utf-8"))
        ss = list(raw.values())
        res = ep.build_scene_first_plan(ss, "", 30, n_candidates=3, video_type=None,
                                        **_live_args(store, ss))
        cands = res.get("candidates") or []
        if not cands:
            print(f"[x] {os.path.basename(fx)} 후보 0개 — 건너뜀")
            continue
        print(f"\n=== {os.path.basename(fx)} ===")
        for ci, cd in enumerate(cands):
            beats = cd["plan"].get("beats") or []
            print(f"  후보{ci} [{cd['plan'].get('slot_variant','-')}]")
            for j in range(1, len(beats)):
                prev_id = (beats[j - 1].get("primary") or {}).get("seg_id") or ""
                cur_id = (beats[j].get("primary") or {}).get("seg_id") or ""
                prev_src = prev_id.rsplit("-", 1)[0]
                cur_src = cur_id.rsplit("-", 1)[0]
                switched = prev_src != cur_src
                prev_n = beats[j - 1].get("narration") or ""
                cur_n = beats[j].get("narration") or ""
                link, share, unfin = _score_pair(prev_n, cur_n)
                key = "switch" if switched else "same"
                agg[key][0] += 1
                agg[key][1] += link
                agg[key][2] += share
                agg[key][3] += unfin
                mark = "소스전환" if switched else "        "
                flag = " ★끊김의심" if (unfin and not link and not share) else ""
                print(f"    {mark} 접속{link} 공유{share} 미완결{unfin}{flag}")
                print(f"       앞: {prev_n[:40]}")
                print(f"       뒤: {cur_n[:40]}")

    print("\n=== 종합 ===")
    for key, label in (("switch", "소스 전환 지점"), ("same", "같은 소스 연속")):
        n, link, share, unfin = agg[key]
        if not n:
            print(f"{label}: 표본 0")
            continue
        print(f"{label}: {n}건 · 접속신호 {link}/{n}({link/n:.0%}) · "
              f"낱말공유 {share}/{n}({share/n:.0%}) · 미완결 {unfin}/{n}({unfin/n:.0%})")
    sw, sm = agg["switch"], agg["same"]
    if sw[0] and sm[0]:
        sw_ok = (sw[1] + sw[2]) / (2 * sw[0])
        sm_ok = (sm[1] + sm[2]) / (2 * sm[0])
        print(f"\n연결성 점수: 전환 {sw_ok:.2f} vs 연속 {sm_ok:.2f}")
        if sw_ok < sm_ok - 0.15:
            print("→ [NG] 소스가 바뀌는 지점에서 눈에 띄게 끊긴다. 두 컷 묶기를 재고할 것.")
        else:
            print("→ [OK] 전환 지점이 연속 지점보다 나쁘지 않다 — 대사는 모델이 전체를 "
                  "보고 쓰므로 소스가 바뀌어도 안 끊긴다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
