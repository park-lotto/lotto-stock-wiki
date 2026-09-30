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
SPLIT_MAX = 3.0        # 컷 없는 긴 구간은 3초 이하로(대본 한 줄 3~5초 — 6.8초 한 태그면 동작이 뭉개졌다)

CLAIM_PROMPT = """너는 쇼핑 쇼츠 편집자다. 이미지는 한 제품을 찍은 소스 영상들의 **컷 대표 프레임 격자**다
(칸 왼쪽 위 숫자 = 컷 번호, 예 "12.0s"는 12번 컷). 아래 자막/말은 참고용이다 — 화면이 우선이다.

이 재료로 **대본에 쓸 수 있는 주장 목록**을 만든다. 대본이 말할 만한 것은 전부 — 기능·특징·장점·효과만이
아니라 **외관(색·재질·크기)·사용 장면·활용 예시·맛/질감·구성품·전후 변화**도 포함한다.
★**문제(제품 쓰기 전의 불편·지저분함·실패 장면)**도 주장으로 뽑아라(kind=문제) — 대본의 문제 제기 줄이 쓴다.
★조건: **화면으로 실제 보이는 것만**. 말로만 나오고 화면에 안 보이는 건 빼라.
각 주장은 대본에 그대로 쓸 짧은 한국어 구(8~20자). 같은 뜻은 하나로. 8~16개.

출력 JSON만: {"product":"제품명","claims":[{"id":"C1","text":"...","kind":"문제|기능|특징|장점|효과|외관|활용|맛질감|구성|전후"}]}

[자막/말(참고)]
%s
"""

TAG_PROMPT = """아래 이미지는 컷 하나당 한 장이고, 각 이미지는 그 컷의 시작→끝 프레임을 왼쪽부터 이어붙인 띠다.
띠 왼쪽 위의 # 번호가 컷 번호다(세지 말고 읽어라).
컷마다: scene_desc(무엇이 보이고 어떻게 바뀌나, 40자 안팎), label(이 컷이 하는 일 12자 이내),
claims(그 컷이 **화면으로 증명하는** 주장 번호 — 여러 개 가능, 없으면 []).
★띠 안에서 실제로 보이는 것만. 문제 장면(쓰기 전 불편)은 문제 주장 번호를 단다.
도입·인물·포장·링크 안내처럼 어떤 주장도 보여주지 못하면 [].

[주장 목록]
%s

[이번 컷]
%s

출력 JSON만: {"tags":[{"no":1,"scene_desc":"...","label":"...","claims":["C1"]}]} — 컷을 빠짐없이.
"""

LINE_PROMPT = """아래는 한 쇼츠 대본의 줄 목록(자막 단위로 쪼개져 있다)과, 이 제품 재료의 주장 목록·컷 목록이다.
1) 줄을 **문장 단위로 묶어라**(한 문장이 여러 줄에 걸쳐 있으면 한 묶음). 묶음은 줄 순서대로 빠짐없이.
2) 묶음마다 그 문장이 말하는 주장 번호(claims)를 단다. 훅·감정·연결·가격·CTA처럼 특정 화면이 필요 없으면
   claims=[] + needs_scene=false.
3) 주장 번호로 딱 맞는 게 없으면 **컷 목록에서 그 문장을 보여주는 컷 번호를 직접 찾아** cuts에 적어라.
   주장 목록에도 컷 목록에도 없을 때만 unlisted에 그 주장을 적는다(재료에 진짜 없는 말).
출력 JSON만: {"sentences":[{"lines":[0,1],"claims":["C2"],"cuts":[],"needs_scene":true,"unlisted":""}]}

[주장 목록]
%s

[컷 목록]
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
        b = fs.merge_slivers(fs.split_long_spans(fs._default_boundaries(vids[0]), max_span=SPLIT_MAX))
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
    cut_txt = "\n".join("#%d %s %.1f~%.1f초 %s | %s" % (c["no"], c["src"], c["start"], c["end"], c["claims"],
                                                        c["scene_desc"][:50]) for c in cuts)
    r, _ = _call(LINE_PROMPT % (claims_txt, cut_txt,
                                "\n".join("%d: %s" % (k, b["text"]) for k, b in enumerate(beats))))
    calls += 1
    sents = r.get("sentences") or []
    # ④ 문장마다 후보 고르기(꼬다리 규칙) + 완성본과 A/B 판정
    judged = judge(jid, work, cuts, beats, sents)
    calls += 1 if any(x.get("verdict") for x in judged) else 0
    out = {"job": jid, "model": model, "calls": calls, "secs": round(time.time() - t0, 1),
           "product": a.get("product"), "claims": claims, "cuts": cuts, "beats": beats, "sentences": sents,
           "judged": judged}
    with open(os.path.join(work, "result.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("완료", jid, model, "호출", calls, "주장", len(claims), "컷", len(cuts),
          "주장 붙은 컷", sum(1 for c in cuts if c["claims"]), "%.0fs" % (time.time() - t0))


SLOW_MAX = 1.2

JUDGE_PROMPT = """너는 쇼핑 쇼츠 편집 검수자다. 문장마다 이미지 두 장(A, B)이 있다 — 각각 그 문장이 읽히는 동안
화면에 나올 영상의 프레임을 왼쪽부터 이어붙인 띠다. **문장 내용을 화면이 더 잘 보여주는 쪽**을 골라라.
화면에 박힌 글자·자막은 무시하고 장면 내용만 본다. 차이가 없으면 "같음".
출력 JSON만: {"verdicts":[{"k":0,"pick":"A|B|같음","why":"20자 안팎"}]}
문장·이미지는 아래 순서대로다.
"""


def pick_scene(sent, beats, cuts):
    """문장 → (고른 컷 번호 목록, 해결 단계, 필요 초). 판단 순서 = 꼬다리 규칙:
    1한컷 → 2같은소스 다음 컷 잇기(같은 주장일 때만) → 3고르게 늦추기(1.2배 이내) → 4다른 소스 같은 주장 합치기 → 5부족"""
    need = sum(beats[i]["need"] for i in sent.get("lines") or [] if isinstance(i, int) and 0 <= i < len(beats))
    want = set(sent.get("claims") or [])
    direct = {int(x) for x in (sent.get("cuts") or []) if str(x).lstrip("#").isdigit() for x in [str(x).lstrip("#")]}

    def ok(c):
        return bool(set(c["claims"]) & want) or c["no"] in direct

    def L(c):
        return c["end"] - c["start"]

    cands = [c for c in cuts if ok(c)]
    if not cands or need <= 0:
        return [], "후보없음", need
    cands.sort(key=lambda c: (len(set(c["claims"]) & want) + (2 if c["no"] in direct else 0), L(c)), reverse=True)
    best = cands[0]
    if L(best) >= need:
        return [best["no"]], "1한컷", need
    for c in cands:                                   # 같은 소스 바로 다음 컷을 같은 주장인 동안 잇는다
        chain, tot, j = [c], L(c), cuts.index(c)
        while tot < need and j + 1 < len(cuts) and cuts[j + 1]["src"] == c["src"] \
                and cuts[j + 1]["start"] - cuts[j]["end"] < 0.25 and ok(cuts[j + 1]):
            j += 1
            chain.append(cuts[j])
            tot += L(cuts[j])
        if tot >= need:
            return [x["no"] for x in chain], "2이어붙이기", need
    if L(best) * SLOW_MAX >= need:
        return [best["no"]], "3늦추기", need
    chain, tot = [], 0.0
    for c in cands:
        chain.append(c)
        tot += L(c)
        if tot >= need:
            return [x["no"] for x in chain], "4다른소스합치기", need
    return [x["no"] for x in chain], "5부족", need


def _hstrip(paths, out, h=300):
    from PIL import Image
    ims = [Image.open(p).convert("RGB") for p in paths if p and os.path.exists(p)]
    if not ims:
        return None
    ims = [im.resize((max(1, int(im.width * h / im.height)), h)) for im in ims]
    st = Image.new("RGB", (sum(im.width + 4 for im in ims), h), "white")
    x = 0
    for im in ims:
        st.paste(im, (x, 0))
        x += im.width + 4
    st.save(out, "JPEG", quality=85)
    return out


def judge(jid, work, cuts, beats, sents):
    """완성본(final.mp4)의 그 문장 구간 vs 후보 컷. A/B는 무작위(편향 방지). 반환: 문장별 기록."""
    import random
    final = os.path.join(MIX, jid, "final.mp4")
    if not os.path.exists(final):
        return []
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                final], capture_output=True, text=True).stdout or 0)
    total = sum(b["need"] for b in beats) or 1.0
    scale = dur / total                                # 줄 길이 합 ↔ 완성본 길이(여백 차이) 비례 보정
    starts, t = [], 0.0
    for b in beats:
        starts.append(t)
        t += b["need"]
    byno = {c["no"]: c for c in cuts}
    rng = random.Random(jid)
    rows, parts = [], []
    for k, s in enumerate(sents):
        if not s.get("needs_scene", True):
            continue
        ln = [i for i in s.get("lines") or [] if isinstance(i, int) and 0 <= i < len(beats)]
        if not ln:
            continue
        nos, how, need = pick_scene(s, beats, cuts)
        a0, a1 = starts[ln[0]] * scale, (starts[ln[-1]] + beats[ln[-1]]["need"]) * scale
        fin = [_grab(final, a0 + (a1 - a0) * (q + 0.5) / 4, os.path.join(work, "fin_%d_%d.jpg" % (k, q)))
               for q in range(4)]
        fstrip = _hstrip(fin, os.path.join(work, "finstrip_%d.jpg" % k))
        cstrip = None
        if nos:
            cp = []
            for n in nos[:4]:
                fr = sorted(glob.glob(os.path.join(work, "c%03d_*.jpg" % n)))
                cp += fr if len(nos) == 1 else fr[len(fr) // 2:len(fr) // 2 + 1]
            cstrip = _hstrip(cp[:5], os.path.join(work, "candstrip_%d.jpg" % k))
        text = " ".join(beats[i]["text"] for i in ln)
        row = {"k": k, "text": text, "need": round(need, 2), "cand": nos, "how": how,
               "cand_desc": [byno[n]["scene_desc"] for n in nos[:3] if n in byno], "unlisted": s.get("unlisted", ""),
               "final_strip": fstrip, "cand_strip": cstrip}
        rows.append(row)
        if fstrip and cstrip:
            flip = rng.random() < 0.5                  # True면 A=후보
            row["a_is"] = "후보" if flip else "완성본"
            A, B = (cstrip, fstrip) if flip else (fstrip, cstrip)
            parts += ["[문장 %d] %s — A:" % (k, text), _img(A), "B:", _img(B)]
    if not parts:
        return rows
    r, _ = _call([JUDGE_PROMPT] + parts)
    vd = {}
    for v in r.get("verdicts") or []:
        try:
            vd[int(v.get("k"))] = v
        except (TypeError, ValueError, AttributeError):
            pass
    for row in rows:
        v = vd.get(row["k"])
        if v and row.get("a_is"):
            p = v.get("pick")
            row["verdict"] = "같음" if p == "같음" else (
                "후보" if (p == "A") == (row["a_is"] == "후보") else "완성본")
            row["why"] = v.get("why", "")
    return rows


if __name__ == "__main__":
    for j in sys.argv[1:]:
        try:
            run(j)
        except Exception as e:      # noqa: BLE001 — 한 job 실패가 나머지를 막지 않게(이유는 출력)
            print("실패", j, repr(e)[:200], flush=True)
