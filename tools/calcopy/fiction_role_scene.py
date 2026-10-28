# -*- coding: utf-8 -*-
"""픽션 썰 역할 대사 줄 = 한 장면 + 한 효과 + 자막은 한 화면에 어절씩 쌓이게(시험 렌더용, 라이브 코드 무변경).
서버에서(환경파일 실어서):
  python3 fiction_role_scene.py <작업> <줄번호>=<seg_id>:<효과> ... [--render]
    효과: dim(어둡게+흑백, 줄 내내) | zoom(첫 어절에 0.5초 확대 뒤 그대로 유지) | none
  예) python3 fiction_role_scene.py 4f10753a7940 4=grab_youtube_51d3b4268b65-3:dim 6=grab_youtube_dd54ae37a5f6-7:zoom --render

하는 일
  ① 그 줄의 장면을 seg 하나로 고정(primary·scene_override·pinned, 대체 컷 없음)
  ② caption_lines 를 어절 하나씩으로 나누고(나레이션과 글이 같아야 시간표가 받는다), 장면별 자막 글(captionTexts)에
     앞 어절까지 쌓은 문장을 넣는다 → 한 화면에 단어가 하나씩 붙는다(구절 길이는 글자수 비례로 어절에 나눔)
  ③ deco.scene_style.effects 를 새 장면 번호로 다시 짠다 — 이전 작업에서 복사된 번호별 효과는 장면 번호가 달라
     엉뚱한 구절에 걸리므로(10-09 실측: 13번 어둡게+흑백이 사장 줄 마지막 구절 하나에만) 훅 첫 장면·마지막 줄 구매 배지만 옮기고 버린다
  ④ 자막 등장효과(motionPack)는 끈다 — 누적 자막이 어절마다 다시 튀어나오지 않게
"""
import sys, json, copy
sys.path.insert(0, "/home/ubuntu/lotto-stock-wiki")
from pathlib import Path
from shopping_shorts.store import Store
from shopping_shorts import config, mix_pipeline, video_assemble, scene_style

st = Store(config.DB_PATH)
WORK = Path(config.DB_PATH).parent / "mix_jobs"
DIM = {"dim": {"level": 0.32, "sec": 0}, "shock": True}


def _segs(job):
    return {s["seg_id"]: dict(video_id=k, seg_id=s["seg_id"], start=s["start"], end=s["end"], scene_desc=s.get("scene_desc") or "")
            for k, v in (job.get("extract") or {}).items() if isinstance(v, dict) for s in v.get("segments") or [] if s.get("seg_id")}


def word_split(narration, lines, durs):
    """구절 길이를 어절에 글자수 비례로 나눈다. 이미 어절 단위면 그대로."""
    words = narration.split()
    if len(durs) == len(words):
        return words, list(durs)
    wd = []
    for ln, d in zip(lines, durs):
        ws = ln.split()
        tot = sum(len(w) + 1 for w in ws)
        wd += [d * (len(w) + 1) / tot for w in ws]
    assert len(wd) == len(words), (len(wd), len(words))
    return words, wd


def main(job_id, specs, render):
    job = st.get_mix_job(job_id)
    plan, segs = job["edit_plan"], _segs(job)
    fx_of = {}
    for spec in specs:
        bi, rest = spec.split("=", 1)
        sid, fx = rest.split(":")
        b = plan["beats"][int(bi)]
        seg = segs[sid]
        b.update(primary=seg, alternates=[], scene_override=[seg], pinned=True)
        lines = b.get("caption_lines") or [b["narration"]]
        b["caption_lines"], b["cap_durs"] = word_split(b["narration"], lines, b["cap_durs"])
        fx_of[int(bi)] = fx
        print("줄", bi, sid, "%.1f초" % (seg["end"] - seg["start"]), "어절", len(b["caption_lines"]))
    deco = copy.deepcopy(job.get("deco") or {})
    ss = deco.setdefault("scene_style", {})
    old = ss.get("effects") or {}
    tts = {b["beat_idx"]: b["tts_path"] for b in plan["beats"] if b.get("tts_path")}
    scenes = scene_style.context_for(video_assemble._beat_timeline(plan, tts), job.get("headcopy") or {}, ss, job_id)["scenes"]
    last_beat = max(s["beat_idx"] for s in scenes)
    badge = next((e for e in old.values() if any(m.get("kind") == "badge" for m in e.get("masks") or [])), None)
    # 장면별 자막 자리·모양도 이전 작업 번호로 복사돼 있다 — 0번 것을 새 장면 전부에 고르게 깐다(특정 번호에만 있던 흰 상자 같은 것은 버린다)
    pre = "%s:%s:" % (ss.get("presetId"), ss.get("mode"))
    for name in ("captionDrags", "captionLayouts"):
        base = (ss.get(name) or {}).get(pre + "0:caption")
        ss[name] = {pre + "%d:caption" % i: base for i in range(len(scenes))} if base else {}
    texts, acc = {}, {}
    eff, seen = {}, set()
    for i, s in enumerate(scenes):
        bi = s["beat_idx"]
        if bi in fx_of and s.get("caption"):
            acc[bi] = (acc.get(bi, "") + " " + s["caption"]).strip()
            texts[pre + "%d:caption" % i] = acc[bi]          # 한 화면에 어절이 하나씩 붙는다
        if i == 0 and "0" in old:
            eff["0"] = old["0"]
        fx = fx_of.get(bi)
        if fx == "dim":
            eff[str(i)] = dict(DIM)
        elif fx == "zoom":
            eff[str(i)] = {"zoom": 1.3, "fxAuto": "emph"} if bi in seen else {"zoom": 1.3, "fxAuto": "emph", "zoomIn": 0.5}
        if bi == last_beat and badge and s.get("caption"):
            eff[str(i)] = badge
        seen.add(bi)
    ss["captionTexts"] = texts
    ss["effects"] = eff
    ss["motionPack"] = "off"
    st.update_mix_job(job_id, edit_plan=plan, deco=deco)
    print("장면", len(scenes), "효과 칸", sorted(eff, key=int))
    for i, s in enumerate(scenes):
        if s["beat_idx"] in fx_of:
            print("  ", i, s["beat_idx"], round(s["start"], 2), round(s["end"], 2), texts.get(pre + "%d:caption" % i, "(빈 칸)"))
    if render:
        print(mix_pipeline.run_render(job_id, config.DB_PATH, WORK, skip_clean=True))


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x != "--render"]
    main(a[0], a[1:], "--render" in sys.argv)
