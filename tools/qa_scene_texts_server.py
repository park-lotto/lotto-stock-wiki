# -*- coding: utf-8 -*-
"""관제 219 서버 점검 — 배포본 서버에서 **실제 job** 의 장면꾸미기 레이어를 렌더·캡컷·썸네일과 같은 함수로 뽑아 대조한다.

서버에서 돌린다(읽기 전용: DB 는 ro 로 열고, 그림은 /tmp 아래에만 쓴다 — job·작업은 안 바뀐다):
    python3 tools/qa_scene_texts_server.py <job_id>

재는 것: 저장값에 sceneTexts["<글 있는 칸>:<i>"] 하나만 더했을 때
  ① render_layers(완성본 compose·캡컷 공용) — i번 장면 그림만 달라지고 나머지 장면은 픽셀까지 그대로
  ② render_layer_one(썸네일) — i번 장면이 ①과 같은 그림
"""
import copy
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(os.environ.get("QA_ROOT") or Path(__file__).resolve().parents[1])   # 서버 /tmp 에서 돌릴 때 QA_ROOT=저장소
sys.path.insert(0, str(ROOT))
from shopping_shorts import scene_style, video_assemble  # noqa: E402
from shopping_shorts.scene_style_lab import _tts_paths  # noqa: E402

DB = ROOT / "shopping_shorts/data/reference.db"


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def main(job_id):
    c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    row = c.execute("select edit_plan_json, deco_json, headcopy_json from mix_jobs where job_id=?", (job_id,)).fetchone()
    if not row:
        print("job 없음"); return 1
    plan = json.loads(row[0] or "{}"); deco = json.loads(row[1] or "{}"); hc = json.loads(row[2] or "null")
    snap = (deco or {}).get("scene_style")
    if not snap:
        print("이 job 은 장면꾸미기 저장값이 없다"); return 1
    timeline = video_assemble._beat_timeline(plan, _tts_paths(plan))
    ctx = scene_style.context_for(timeline, hc, scene_style.validate_snapshot(copy.deepcopy(snap)), job_id)
    kinds = [s.get("kind") for s in ctx["scenes"]]
    # 고칠 칸 = 이 job 틀에 실제로 글이 있는 칸(고정형은 bodyTitle 이 없다 — 없는 칸을 고치면 아무것도 안 잰다)
    text = (snap.get("text") or {})
    bind = next((b for b in ("bodyTitle", "hook1", "hook2", "channel") if str(text.get(b) or "").strip()), None)
    if not bind:
        print("제목·채널명 글이 하나도 없는 job"); return 1
    target = next((i for i, k in enumerate(kinds) if k == "body"), min(1, len(kinds) - 1))
    other = [i for i in range(len(kinds)) if i != target]
    base = Path("/tmp/qa_scene_texts") / job_id
    a_dir, b_dir, t_dir = base / "before", base / "after", base / "thumb"
    for d in (a_dir, b_dir, t_dir):
        d.mkdir(parents=True, exist_ok=True)
    marked = copy.deepcopy(snap)
    marked["sceneTexts"] = {"%s:%d" % (bind, target): "장면별 검사"}
    la = scene_style.render_layers(timeline, copy.deepcopy(snap), a_dir, hc, job_id)
    lb = scene_style.render_layers(timeline, marked, b_dir, hc, job_id)
    one = scene_style.render_layer_one(timeline, marked, t_dir, target, hc, job_id)
    fails = []
    if md5(a_dir / la[target]["file"]) == md5(b_dir / lb[target]["file"]):
        fails.append("%d번 장면 그림이 안 바뀜(장면별 글이 렌더에 안 들어감)" % target)
    changed = [i for i in other if md5(a_dir / la[i]["file"]) != md5(b_dir / lb[i]["file"])]
    if changed:
        fails.append("다른 장면 그림이 바뀜: %s" % changed)
    if md5(one) != md5(b_dir / lb[target]["file"]):
        fails.append("썸네일(render_layer_one) 그림이 렌더 레이어와 다름")
    print(json.dumps({"job": job_id, "bind": bind, "scenes": len(kinds), "target": target, "other_unchanged": len(other) - len(changed),
                      "layer_before": str(a_dir / la[target]["file"]), "layer_after": str(b_dir / lb[target]["file"])}, ensure_ascii=False))
    print("통과" if not fails else "실패 %d\n- " % len(fails) + "\n- ".join(fails))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
