# -*- coding: utf-8 -*-
"""이야기 작가 **라이브 연결 점검** — 실제 job 재료로 make_drafts를 돌려 줄별 컷을 대조한다(2026-09-22).

사장님이 짚을 것 → 여기서 먼저 잰다(0순위-A1b):
  ①대본이 읽을 만한가(전문 출력)  ②줄마다 컷이 그 말과 맞나(줄·seg·화면설명 대조)
  ③씨앗 영상 컷이 섞였나  ④고조 줄이 근거 특징 컷을 받았나  ⑤같은 컷 두 번 쓰였나

쓰기:  py tools/seed_analyzer/live_link_check.py <job.json> [스파인id…]
  job.json = {"backbone_main":…, "extract":{…}}  (서버에서 읽기 전용으로 받아 온 것)
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def main():
    from shopping_shorts import story_writer as sw, backbone_assemble as ba
    job = json.load(io.open(sys.argv[1], encoding="utf-8"))
    spines = [{"id": int(x), "name": "스타일 %s" % x, "no_cta": True} for x in sys.argv[2:]]
    srcs = ba.sources_from_extract(job["extract"])
    seed = ba.seed_source(srcs, job.get("backbone_main"))
    idx = ba._seg_index(srcs)
    print("소스 %d편 · 컷 %d개 · 씨앗 %s(%d자)" % (
        len(srcs), len(idx), seed.get("video_id"), len((seed.get("full_text") or ""))))
    print("씨앗 첫 120자: %s\n" % (seed.get("full_text") or "")[:120])
    drafts, why = sw.make_drafts(spines, job, job_id=os.path.basename(sys.argv[1]))
    print("대본 %d편 · 못 만든 이유: %s\n" % (len(drafts), why or "없음"))
    for d in drafts:
        groups = d.get("_groups")
        used = [s for b in d["beats"] for s in b["src_segs"]]
        seed_cuts = [s for s in used if idx.get(s, {}).get("vid") == seed.get("video_id")]
        print("=== %s · %s · %d줄 · %.1f초 ===" % (d["style_name"], d["platform"], len(d["beats"]), d["sec"]))
        print("    컷 %d개(중복 %d) · 씨앗 컷 %d · 컷 없는 줄 %d" % (
            len(used), len(used) - len(set(used)), len(seed_cuts), sum(1 for b in d["beats"] if not b["src_segs"])))
        names = d.get("feat_names") or []
        print("    재료: " + " / ".join("%d.%s" % (i + 1, n) for i, n in enumerate(names)))
        for b, g in zip(d["beats"], d.get("line_groups") or []):
            print("  [%s]%s %s" % (b["role"], (" <재료%d>" % (g + 1)) if g >= 0 else "", b["text"]))
            for s in b["src_segs"]:
                v = idx.get(s, {})
                print("        %-16s %.1fs %s" % (s, v.get("secs") or 0, (v.get("desc") or "")[:60]))
        print()


if __name__ == "__main__":
    main()
