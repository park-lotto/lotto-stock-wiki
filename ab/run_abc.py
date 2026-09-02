# -*- coding: utf-8 -*-
"""실험3 — 매칭을 **어떻게 물어보느냐**가 결과를 바꾸는가.

사장님 질문: "프롬프트대로 매칭하는 것과, 3단계에서 대화하듯 '이 훅 대본에 아래
영상소스 조각들이 많이 있는데 캡션 내용과 이미지를 보고 대본에 맞는 걸 매칭해봐'
이렇게 하는 게 똑같이 되는 건가?"

→ 지금 프로덕션은 **이미지를 한 장도 안 본다.** 1단계가 만들어둔 scene_desc(텍스트)만
   읽고, 게다가 `역할:problem → 결 before·문제 우선` 같은 **정해진 축을 강제**한다.
   사장님이 말한 방식과 다르다. 그래서 세 방식을 같은 비트에 돌려 비교한다.

  A(prod)  현재 그대로 — 텍스트 scene_desc + 역할축 강제
  B(free)  텍스트만, **축 없이** "대본에 맞는 걸 골라라"
  C(image) **실제 프레임 이미지** + 캡션을 보고 고르기

★채점 주의: B·C는 축을 안 줬으므로 축(`beat_role_mismatch`)으로 재면 불리하다.
  기계 채점은 참고로만 싣고, **진짜 판단은 사장님이 화면을 눈으로 보는 것**이다.
  → 그래서 결과를 나란히 놓은 HTML(비교표.html)을 만든다.
"""
import base64
import io
import json
import os
import subprocess
import sys
import time
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = r"C:/Users/CH/Desktop/로또의 주식"
sys.path.insert(0, _ROOT)
sys.path.insert(0, _HERE)
os.chdir(_ROOT)

from shopping_shorts import edit_plan  # noqa: E402
from run_ab import load_job, score  # noqa: E402
from ab_repick import _extract_json, make_claude_call, make_gemini_call  # noqa: E402

FRAMES = os.path.join(_HERE, "frames")
LOG = os.path.join(_HERE, "logs_abc")
os.makedirs(LOG, exist_ok=True)
OUT = os.path.join(_HERE, "abc_results.json")
PROG = os.path.join(_HERE, "abc_progress.json")

_SCHEMA = {
    "type": "object",
    "properties": {
        "picks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "beat_idx": {"type": "integer"},
                    "seg_id": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["beat_idx", "seg_id"],
            },
        }
    },
    "required": ["picks"],
}


def _cand_lines(seg_map, pool, with_role):
    out = []
    for sid in pool:
        s = seg_map[sid]
        role = (" 결:%s" % s.get("shot_role")) if (with_role and s.get("shot_role")) else ""
        say = (" | 말:%s" % (s.get("text") or "")[:40]) if s.get("text") else ""
        out.append("[%s]%s 화면:%s%s" % (sid, role, (s.get("scene_desc") or "")[:60], say))
    return "\n".join(out)


def _beat_lines(beats, with_role_hint):
    out = []
    for b in beats:
        tail = ""
        if with_role_hint:
            shots, why = edit_plan._want_shots_for_role(b.get("role"))
            if shots:
                tail = " [역할:%s — %s. 결 %s 우선]" % (b.get("role"), why, "·".join(shots))
        out.append("[%s] 대사:%s%s" % (b["beat_idx"], b.get("narration", ""), tail))
    return "\n".join(out)


# ── A: 프로덕션 그대로 ───────────────────────────────────────────────
def run_prod(beats, seg_map, model, tag):
    cb = [dict(b, fit=1) for b in beats]      # 문을 열어 모델이 실제로 돌게 한다
    call = (make_claude_call(model, LOG, tag) if model != "gemini"
            else make_gemini_call(LOG, tag))
    out = edit_plan._repick_weak_beats([dict(b) for b in cb], seg_map, call=call)
    return {b["beat_idx"]: (b.get("primary") or {}).get("seg_id") for b in out}


# ── B: 축 없이 자유롭게 ──────────────────────────────────────────────
def _free_prompt(beats, seg_map, pool):
    return (
        "아래는 숏폼 영상의 나레이션 대본이다. 각 비트(대사)에 가장 어울리는 영상 조각을\n"
        "후보에서 하나씩 골라라. 대사가 말하는 장면·감정·흐름에 맞는 것을 고르면 된다.\n"
        "- 같은 조각을 두 비트에 쓰지 마라.\n"
        "- why에 왜 그걸 골랐는지 한 줄로 적어라.\n\n"
        "[대본]\n%s\n\n[후보 영상 조각]\n%s\n\npicks 배열의 JSON만 출력해라."
        % (_beat_lines(beats, False), _cand_lines(seg_map, pool, False)))


def run_free(beats, seg_map, pool, model, tag):
    prompt = _free_prompt(beats, seg_map, pool)
    call = (make_claude_call(model, LOG, tag) if model != "gemini"
            else make_gemini_call(LOG, tag))
    raw = call(prompt, _SCHEMA)
    return _picks_to_map(raw, beats, seg_map)


# ── C: 실제 이미지를 보고 ────────────────────────────────────────────
def _frame_path(sid):
    p = os.path.join(FRAMES, "%s.jpg" % sid)
    return p if os.path.exists(p) else None


def run_image_claude(beats, seg_map, pool, model, tag):
    """claude -p 는 이미지를 인자로 못 받는다 → 파일 경로를 프롬프트에 적어
    에이전트가 Read로 직접 보게 한다(로컬 파일이라 가능)."""
    lines = []
    for sid in pool:
        p = _frame_path(sid)
        if not p:
            continue
        s = seg_map[sid]
        say = (" | 말:%s" % (s.get("text") or "")[:40]) if s.get("text") else ""
        lines.append("[%s] 이미지:%s | 캡션:%s%s"
                     % (sid, p, (s.get("scene_desc") or "")[:60], say))
    prompt = (
        "아래 숏폼 대본의 각 비트에 어울리는 영상 조각을 고르는 일이다.\n"
        "★후보마다 실제 프레임 이미지 **파일 경로**가 있다. Read 도구로 **이미지를 직접 열어 보고**\n"
        "  화면에 무엇이 보이는지 확인한 뒤 골라라. 캡션 글자만 믿지 마라.\n"
        "- 같은 조각을 두 비트에 쓰지 마라.\n"
        "- why에 화면에서 실제로 본 것을 근거로 한 줄 적어라.\n\n"
        "[대본]\n%s\n\n[후보 — 이미지 경로 + 캡션]\n%s\n\n"
        "마지막에 picks 배열의 JSON만 출력해라(설명은 why 안에)."
        % (_beat_lines(beats, False), "\n".join(lines)))
    t0 = time.time()
    r = subprocess.run(["claude", "-p", "--model", model],
                       input=prompt, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1800)
    dt = time.time() - t0
    io.open(os.path.join(LOG, "%s.txt" % tag), "w", encoding="utf-8").write(
        "RC=%s (%.1fs)\n--- PROMPT ---\n%s\n--- STDOUT ---\n%s" % (r.returncode, dt, prompt, r.stdout))
    print("      [%s] %.1fs rc=%s" % (tag, dt, r.returncode), flush=True)
    if r.returncode != 0:
        return {}
    return _picks_to_map(_extract_json(r.stdout), beats, seg_map)


def run_image_gemini(beats, seg_map, pool, model, tag):
    """제미니는 이미지를 인라인으로 넣는다(google-genai types.Part)."""
    from google.genai import types
    from shopping_shorts import keyroute
    parts = []
    head = ("아래 숏폼 대본의 각 비트에 어울리는 영상 조각을 골라라.\n"
            "★후보마다 **실제 프레임 이미지**가 함께 주어진다. 이미지를 보고 화면에 무엇이\n"
            "  있는지 확인한 뒤 골라라. 캡션 글자만 믿지 마라.\n"
            "- 같은 조각을 두 비트에 쓰지 마라.\n\n[대본]\n%s\n\n[후보]\n"
            % _beat_lines(beats, False))
    parts.append(types.Part.from_text(text=head))
    n_img = 0
    for sid in pool:
        p = _frame_path(sid)
        if not p:
            continue
        s = seg_map[sid]
        parts.append(types.Part.from_text(
            text="\n[%s] 캡션:%s" % (sid, (s.get("scene_desc") or "")[:60])))
        parts.append(types.Part.from_bytes(
            data=io.open(p, "rb").read(), mime_type="image/jpeg"))
        n_img += 1
    parts.append(types.Part.from_text(text="\n\npicks 배열의 JSON만 출력해라."))

    # ★키는 프로덕션과 같은 경로로 받는다(edit_plan.py:2266) — 규칙을 베끼지 않는다.
    keys = list(keyroute.gemini_keys("general") or [])
    last = None
    for k in keys[:6]:
        try:
            from google import genai
            cli = genai.Client(api_key=k)
            t0 = time.time()
            resp = cli.models.generate_content(
                model=edit_plan.comment_gen._MODEL,
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=_SCHEMA),
            )
            dt = time.time() - t0
            io.open(os.path.join(LOG, "%s.txt" % tag), "w", encoding="utf-8").write(
                "OK %.1fs 이미지%d장\n%s" % (dt, n_img, resp.text or ""))
            print("      [%s] %.1fs 이미지%d장" % (tag, dt, n_img), flush=True)
            return _picks_to_map(json.loads(resp.text), beats, seg_map)
        except Exception as e:
            last = e
            continue
    print("      [%s] 실패: %r" % (tag, last), flush=True)
    return {}


def _picks_to_map(raw, beats, seg_map):
    if not raw or not isinstance(raw, dict):
        return {}
    idxs = {b["beat_idx"] for b in beats}
    out, used = {}, set()
    for p in raw.get("picks", []):
        # ★키 이름이 모델마다 흔들린다(실측: 오푸스가 beat/clip으로 냄) — 스키마를 줘도
        #   claude -p는 강제되지 않는다. 별칭을 모두 받아준다.
        def _get(d, *names):
            for n in names:
                if n in d:
                    return d[n]
            return None
        try:
            bi = int(_get(p, "beat_idx", "beat", "idx", "index"))
            sid = str(_get(p, "seg_id", "clip", "seg", "segment_id")).strip()
        except (TypeError, ValueError):
            continue
        if bi in idxs and sid in seg_map and sid not in used:
            out[bi] = sid
            used.add(sid)
    return out


def main():
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    models = (sys.argv[2].split(",") if len(sys.argv) > 2 else ["opus", "gemini"])
    beats, seg_map = load_job()
    pool = [sid for sid in sorted(seg_map)
            if not edit_plan._is_edge_seg(seg_map[sid]) and "pad" not in sid.lower()]
    print("비트 %d · 후보 %d · 프레임 %d장" % (len(beats), len(pool), len(os.listdir(FRAMES))),
          flush=True)

    modes = ["prod", "free", "image"]
    rows, done = [], 0
    total = reps * len(models) * len(modes)
    t0all = time.time()

    for rep in range(reps):
        for model in models:
            for mode in modes:
                done += 1
                tag = "%s_%s_r%d" % (mode, model, rep)
                print("[%d/%d] %s" % (done, total, tag), flush=True)
                row = {"mode": mode, "model": model, "rep": rep}
                try:
                    t0 = time.time()
                    if mode == "prod":
                        picks = run_prod(beats, seg_map, model, tag)
                    elif mode == "free":
                        picks = run_free(beats, seg_map, pool, model, tag)
                    else:
                        picks = (run_image_claude(beats, seg_map, pool, model, tag)
                                 if model != "gemini"
                                 else run_image_gemini(beats, seg_map, pool, model, tag))
                    row["seconds"] = round(time.time() - t0, 1)
                    # 채점: 고른 seg를 비트에 꽂아 프로덕션 축으로 잰다(참고용).
                    probe = []
                    for b in beats:
                        nb = dict(b)
                        sid = picks.get(b["beat_idx"])
                        if sid:
                            nb["primary"] = dict(seg_map[sid])
                        probe.append(nb)
                    bad, det = score(probe, seg_map)
                    row.update(ok=True, picks=picks, axis_bad=bad, detail=det,
                               filled=sum(1 for v in picks.values() if v))
                    print("      → 채움 %d/%d · 축채점 어긋남 %d (%.1fs)"
                          % (row["filled"], len(beats), bad, row["seconds"]), flush=True)
                except Exception as e:
                    row.update(ok=False, error="%r" % (e,), tb=traceback.format_exc()[-900:])
                    print("      ✗ %r" % (e,), flush=True)
                rows.append(row)
                json.dump(rows, io.open(OUT, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=1)
                json.dump({"done": done, "total": total,
                           "elapsed_min": round((time.time() - t0all) / 60, 1), "last": tag},
                          io.open(PROG, "w", encoding="utf-8"), ensure_ascii=False)

    print("\n완료 %d건 · %.1f분" % (len(rows), (time.time() - t0all) / 60), flush=True)


if __name__ == "__main__":
    main()
