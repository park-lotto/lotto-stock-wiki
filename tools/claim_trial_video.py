"""주장 번호 태깅 시험 2단계 — 원본 영상을 보고 처음부터(2026-10-01 사장님 "원본으로 해서 안본 영상으로 하나 해봐").

1단계(claim_trial.py)는 이미 적힌 태그 글만 넣었다 → 글이 틀리면 따라 틀렸다(6.7초 균등 조각에 "구매 링크 안내").
여기서는 분석 단계와 같은 부품으로 영상을 본다:
  컷 경계 = frame_script._default_boundaries + merge_slivers (종전 B1과 같다)
  컷마다 시작·중간·끝 띠 = frame_script.frame_times / frames_for_span / make_strip (번호 박힘)
호출(버텍스): ①주장 목록 — 컷 대표 격자 이미지 + 자막 ②컷 태깅 12컷씩 ③기존 대본 줄 → 주장 번호.
★주장 목록은 넓게 — 1단계에서 '기능'만 뽑게 해 외관·맛·활용 예시가 빠지자 "재료에 없는 주장" 오판이 났다.

서버에서(읽기 전용 — DB mode=ro, 산출물은 /tmp/claimv_<job>/ 만):
  set -a && . /etc/shopping-shorts.env && set +a
  cd /home/ubuntu/lotto-stock-wiki && PYTHONPATH=/tmp:. python3 /tmp/claim_trial_video.py <job>
"""
import glob
import json
import os
import subprocess
import sys
import time

DB = "file:/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db?mode=ro"
MIX = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/mix_jobs"
BATCH = 12

CLAIM_PROMPT = """너는 쇼핑 쇼츠 편집자다. 이미지는 한 제품을 찍은 소스 영상들의 **컷 대표 프레임 격자**다
(칸 왼쪽 위 숫자 = 컷 번호, 예 "12.0s"는 12번 컷). 아래 자막/말은 참고용이다 — 화면이 우선이다.

이 재료로 **대본에 쓸 수 있는 주장 목록**을 만든다. 대본이 말할 만한 것은 전부 — 기능·특징·장점·효과만이
아니라 **외관(색·재질·크기)·사용 장면·활용 예시·맛/질감·구성품·전후 변화**도 포함한다.
★조건: **화면으로 실제 보이는 것만**. 말로만 나오고 화면에 안 보이는 건 빼라.
각 주장은 대본에 그대로 쓸 짧은 한국어 구(8~20자). 같은 뜻은 하나로. 6~14개.

출력 JSON만: {"product":"제품명","claims":[{"id":"C1","text":"...","kind":"기능|특징|장점|효과|외관|활용|맛질감|구성|전후"}]}

[자막/말(참고)]
%s
"""

TAG_PROMPT = """아래 이미지는 컷 하나당 한 장이고, 각 이미지는 그 컷의 시작→끝 프레임을 왼쪽부터 이어붙인 띠다.
띠 왼쪽 위의 # 번호가 컷 번호다(세지 말고 읽어라).
컷마다: scene_desc(무엇이 보이고 어떻게 바뀌나, 40자 안팎), label(이 컷이 하는 일 12자 이내),
claims(그 컷이 **화면으로 증명하는** 주장 번호 — 여러 개 가능, 없으면 []).
★띠 안에서 실제로 보이는 것만. 도입·인물·포장·링크 안내처럼 주장을 증명 못 하면 [].

[주장 목록]
%s

[이번 컷]
%s

출력 JSON만: {"tags":[{"no":1,"scene_desc":"...","label":"...","claims":["C1"]}]} — 컷을 빠짐없이.
"""

LINE_PROMPT = """아래는 한 쇼츠 대본의 줄들과, 이 제품 재료에서 뽑은 주장 목록이다.
줄마다 그 줄이 말하는 주장 번호를 단다(여러 개 가능). 훅·감정·연결·가격·CTA처럼 화면을 요구하지 않는 줄은
빈 배열 + needs_scene=false. 목록에 없는 제품 주장을 말하면 빈 배열 + needs_scene=true + unlisted에 그 주장.
출력 JSON만: {"lines":[{"i":0,"claims":["C2"],"needs_scene":true,"unlisted":""}]} — 줄을 빠짐없이.

[주장 목록]
%s

[대본 줄]
%s
"""


def _loads(t):
    t = (t or "").strip()
    return json.loads(t[t.find("{"):t.rfind("}") + 1])


def _call(parts):
    from google.genai import types
    from shopping_shorts import vertex_route
    cl, m = vertex_route.client(0), vertex_route.model()
    cfg = types.GenerateContentConfig(response_mime_type="application/json")
    for n in range(4):
        try:
            return _loads(cl.models.generate_content(model=m, contents=parts, config=cfg).text), m
        except Exception as e:      # noqa: BLE001
            print("  재시도", n + 1, repr(e)[:120], flush=True)
            time.sleep(6 * (n + 1))
    raise RuntimeError("버텍스 4회 실패")


def _img(path):
    from google.genai import types
    with open(path, "rb") as f:
        return types.Part.from_bytes(data=f.read(), mime_type="image/jpeg")


def _grab(video, t, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "%.3f" % t, "-i", video, "-frames:v", "1",
                    "-vf", "scale=-2:360", out], check=False)
    return out if os.path.exists(out) else None


def cut_and_strip(jid, work):
    """소스마다 컷 경계 → 컷별 띠. [{no, src, start, end, strip, mid}]"""
    from shopping_shorts import frame_script as fs
    cuts, no = [], 0
    for sdir in sorted(glob.glob(os.path.join(MIX, jid, "s[0-9]*"))):
        vids = sorted(glob.glob(os.path.join(sdir, "*.mp4")))
        if not vids:
            continue
        src = os.path.basename(sdir)
        b = fs.merge_slivers(fs._default_boundaries(vids[0]))
        for a, e in zip(b, b[1:]):
            no += 1
            ts = fs.frame_times(a, e, k=fs.frames_for_span(e - a))
            paths = [_grab(vids[0], t, os.path.join(work, "c%03d_%d.jpg" % (no, k))) for k, t in enumerate(ts)]
            paths = [p for p in paths if p]
            strip = fs.make_strip(paths, os.path.join(work, "strip_%03d.jpg" % no), label="#%d" % no) \
                if len(paths) > 1 else (paths[0] if paths else None)
            cuts.append({"no": no, "src": src, "start": round(a, 2), "end": round(e, 2), "strip": strip,
                         "mid": paths[len(paths) // 2] if paths else None})
    return cuts


def run(jid):
    import sqlite3
    from shopping_shorts import frame_script as fs
    work = "/tmp/claimv_%s" % jid
    os.makedirs(work, exist_ok=True)
    db = sqlite3.connect(DB, uri=True)
    ej, ep = db.execute("select extract_json, edit_plan_json from mix_jobs where job_id=?", (jid,)).fetchone()
    ext, plan = json.loads(ej), json.loads(ep)
    speech = "\n".join("%s: %s" % (k, (s.get("full_text") or "")[:300]) for k, s in ext.items() if isinstance(s, dict))
    t0 = time.time()
    cuts = cut_and_strip(jid, work)
    print("컷", len(cuts), "개 (%.0fs)" % (time.time() - t0), flush=True)
    calls = 0
    # ① 주장 목록 — 격자(40칸씩)
    grids = []
    for g0 in range(0, len(cuts), fs.GRID_MAX):
        part = cuts[g0:g0 + fs.GRID_MAX]
        p = fs.make_grid([c["mid"] for c in part], os.path.join(work, "grid_%d.jpg" % g0),
                         times=[c["no"] for c in part])       # 칸 라벨 = 컷 번호(시각 대신)
        if p:
            grids.append(_img(p))
    a, model = _call([CLAIM_PROMPT % speech[:3000]] + grids)
    calls += 1
    claims = a.get("claims") or []
    claims_txt = "\n".join("%s %s (%s)" % (c.get("id"), c.get("text"), c.get("kind")) for c in claims)
    # ② 컷 태깅
    tags = {}
    for b0 in range(0, len(cuts), BATCH):
        part = [c for c in cuts[b0:b0 + BATCH] if c["strip"]]
        lines = "\n".join("#%d %s %.1f~%.1f초" % (c["no"], c["src"], c["start"], c["end"]) for c in part)
        r, _ = _call([TAG_PROMPT % (claims_txt, lines)] + [_img(c["strip"]) for c in part])
        calls += 1
        for t in r.get("tags") or []:
            try:
                tags[int(t.get("no"))] = t
            except (TypeError, ValueError):
                pass
    for c in cuts:
        t = tags.get(c["no"]) or {}
        c.update(scene_desc=t.get("scene_desc", ""), label=t.get("label", ""), claims=t.get("claims") or [])
    # ③ 기존 대본 줄
    beats = []
    for b in plan.get("beats") or []:
        p = b.get("primary") or {}
        beats.append({"text": b.get("narration") or "", "role": b.get("role"),
                      "need": round(sum(b.get("cap_durs") or []) or float(b.get("target_seconds") or 0), 2),
                      "cur_seg": p.get("seg_id"), "cur_src": p.get("video_id"),
                      "cur_start": p.get("start"), "cur_end": p.get("end")})
    r, _ = _call(LINE_PROMPT % (claims_txt, "\n".join("%d: %s" % (k, b["text"]) for k, b in enumerate(beats))))
    calls += 1
    out = {"job": jid, "model": model, "calls": calls, "secs": round(time.time() - t0, 1),
           "product": a.get("product"), "claims": claims, "cuts": cuts, "beats": beats, "lines": r.get("lines") or []}
    with open(os.path.join(work, "result.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("완료", jid, model, "호출", calls, "주장", len(claims), "컷", len(cuts),
          "주장 붙은 컷", sum(1 for c in cuts if c["claims"]), "%.0fs" % (time.time() - t0))


if __name__ == "__main__":
    run(sys.argv[1])
