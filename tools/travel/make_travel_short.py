# -*- coding: utf-8 -*-
"""여행 쇼츠 한 편 — 두 단계(관제 239). 영상(Veo, 돈 드는 단계) 전에 사장님이 사진·대본을 먼저 본다.

  1단계 pick   : 숙소 주소 → 상세·공식 사진 → 사진 판정(종류·글자·사람·화려함) → 7장 → 세로 시작 화면 → 대본 3안
                 → 검토 화면(review.html: 단계·고른 7장·후보 전체·대본 3안·금지 검사·예상 비용). 여기서 멈춘다.
  2단계 render : (검토 뒤) Veo 7클립 → 음성(일레븐 미나) → 진짜 렌더(video_assemble.assemble) + 캡컷 초안.

사용:
  py tools/travel/make_travel_short.py pick   <숙소주소> <작업폴더>
  py tools/travel/make_travel_short.py render <작업폴더> [--script 0|1|2] [--swap 3=12,5=8] [--no-veo]
     --swap 칸=후보번호 : 검토 화면의 후보 번호로 사진을 바꾼다(바꾸면 대본을 다시 쓴다)
판단은 전부 shopping_shorts.travel_build / travel_source / ai_scene / video_assemble 의 주인 함수가 한다.
"""
import base64
import html
import io
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from shopping_shorts import travel_source, travel_build as tb, ai_scene, video_assemble as va, capcut_draft  # noqa: E402

# 음성 = 일레븐 미나(사장님 2026-10-19). 값은 큐레이션 프리셋 kr-mina-stable 그대로(assets/voice_presets.json)
MINA = {"voice_id": "aiUUgjHa4mpHf6UenZuf", "model_id": "eleven_v3",
        "voice_settings": {"stability": 0.55, "similarity_boost": 0.78, "style": 0.15}, "tempo": 1.35}
VEO_WON_PER_4S = 300
CAM_KO = {"water_aerial": "드론이 위에서 천천히 내려가며 물결·조명 반짝임", "water": "드론처럼 물 쪽으로 천천히 다가감, 잔물결",
          "onsen": "물이 흐르고 김이 피어오름, 손으로 찍듯 오른쪽 이동", "bath": "욕조에 물이 차오름, 카메라 거의 고정",
          "room": "눈높이로 객실 안으로 천천히 들어감", "view": "창밖 풍경이 드러나게 오른쪽으로 천천히 이동",
          "exterior": "건물에서 하늘로 아주 천천히 올려다봄", "lobby": "1인칭으로 천천히 걸어 들어감",
          "restaurant": "가운데로 천천히 다가감", "other": "가운데로 천천히 다가감"}     # ai_scene.TRAVEL_CAMERA 의 한국어 설명          # 기존 실측(관제 AI장면생성): 4초 약 300원
STAGES = [("상세", "숙소 페이지에서 이름·시설·공식 사진을 가져온다(후기 사진은 안 쓴다)"),
          ("사진 판정", "사진마다 종류·글자/간판·사람·화려함을 AI가 본다(12장씩 한 번에)"),
          ("7장", "물놀이 3 · 객실 2 · 시그니처 2, 글자·사람 사진 제외, 첫 컷 = 가장 화려한 물놀이"),
          ("원본 재설명", "고른 7장은 원본 해상도로 한 장씩 다시 본다(격자 판정 설명이 틀린 실측 있음)"),
          ("세로 화면", "가로 사진을 9:16 시작 화면으로(높이 충분하면 자르기, 낮으면 흐린 배경)"),
          ("대본", "고른 순서의 사진마다 한 줄 — 강의 실제 대본 5편을 본보기로 3유형(안티/반전·감각 몰입·타깃 혜택)"),
          ("대본 관문", "① 이름·가격·지역·가 본 척·길이(미나 1.35배 18~20초) ② 줄마다 그 사진을 다시 보여 주고 '사진에 없는 말' 검사 → 걸리면 문제를 알려 주고 다시 씀"),
          ("⏸ 사장님 확인", "여기서 멈춘다 — 사진·대본을 보고 바꿀 것을 정한다"),
          ("영상화", "사진마다 Veo 4초(카메라 움직임 표)"),
          ("음성", "일레븐 미나, 줄마다 합성 후 1.35배"),
          ("렌더·캡컷", "문장 = 컷, 클립을 문장 길이에 맞춰 배속, 오른쪽 위 '광고·AI 콘텐츠·출처' 표기")]


def _thumb_b64(path, w=300):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    im.thumbnail((w, w * 2))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=78)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def stage_pick(url, work):
    work.mkdir(parents=True, exist_ok=True)
    rep = {"url": url, "steps": {}}

    def step(name, t):
        rep["steps"][name] = round(time.time() - t, 1)
        print("· %s %.1f초" % (name, rep["steps"][name]), flush=True)

    t = time.time()
    detail = travel_source.fetch(url)
    step("상세", t)
    t = time.time()
    rooms = [p for p in detail["photos"] if p.get("label") == "객실"][:12]
    cands = ([p for p in detail["photos"] if p.get("label") != "객실"] + rooms)[:36]
    pdir = work / "photos"
    pdir.mkdir(exist_ok=True)
    paths = []
    for i, p in enumerate(cands):
        try:
            paths.append(tb.download(p["url"], pdir / ("%02d.jpg" % i)))
        except Exception as e:      # noqa: BLE001 — 한 장 실패는 건너뛴다(이유는 남긴다)
            print("  사진 실패:", e)
    step("사진 받기 %d장" % len(paths), t)
    t = time.time()
    judged = tb.judge_photos(paths, work)
    for i, j in enumerate(judged, 1):
        j["no"] = i
    step("사진 판정", t)
    pk = tb.pick7(judged)
    state = {"url": url, "detail": detail, "judged": judged, "picks": [j["no"] for j in pk["photos"]],
             "short": pk["short"], "rep": rep}
    _frames_and_script(state, work)
    return state


def _frames_and_script(state, work):
    by_no = {j["no"]: j for j in state["judged"]}
    t = time.time()
    need = [by_no[n] for n in state["picks"] if not by_no[n].get("described")]
    for q in tb.describe_picks(need):          # 고른 사진은 원본으로 다시 본다(격자 설명은 틀린다)
        q["described"] = True
        by_no[q["no"]].update(q)
    state["rep"]["steps"]["원본 재설명"] = round(time.time() - t, 1)
    picks = [by_no[n] for n in state["picks"]]
    t = time.time()
    state["frames"] = []
    for i, p in enumerate(picks):
        fp, mode = tb.start_frame(p["path"], work / ("start_%d.png" % i))
        state["frames"].append({"path": fp, "mode": mode})
    state["rep"]["steps"]["세로 화면"] = round(time.time() - t, 1)
    t = time.time()
    state["script"] = tb.write_script(picks, state["detail"])
    state["rep"]["steps"]["대본"] = round(time.time() - t, 1)
    (work / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    review_html(state, work)


def review_html(state, work):
    d, by_no = state["detail"], {j["no"]: j for j in state["judged"]}
    picks = [by_no[n] for n in state["picks"]]
    e = html.escape
    KO = {"water_aerial": "물놀이(위에서)", "water": "물놀이", "onsen": "노천탕·스파", "bath": "욕조", "room": "객실",
          "view": "뷰", "exterior": "외관", "lobby": "로비", "restaurant": "식당", "other": "기타"}
    stages = "".join("<li><b>%s</b> — %s</li>" % (e(a), e(b)) for a, b in STAGES)
    versions = (state["script"] or {}).get("versions") or []
    issues = (state["script"] or {}).get("issues") or {}
    chosen = ((state["script"] or {}).get("chosen") or {}).get("type")
    rows = ""
    for i, p in enumerate(picks):
        cells = "".join("<td class=sc>%s</td>" % e((v.get("lines") or [""] * 7)[i] if i < len(v.get("lines") or []) else "")
                        for v in versions)
        rows += ("<tr><td class=n>%d</td><td><img src='%s'><div class=s>후보 %d · %s · 화려함 %d</div></td>"
                 "<td><img src='%s' class=v><div class=s>%s</div></td><td class=d>%s<div class=s>카메라: %s</div></td>%s</tr>"
                 % (i + 1, _thumb_b64(p["path"]), p["no"], e(KO.get(p["kind"], p["kind"])), p["wow"],
                    _thumb_b64(state["frames"][i]["path"], 160), "자르기" if state["frames"][i]["mode"] == "crop" else "흐린 배경",
                    e(p["desc_ko"]), e(CAM_KO.get(p["kind"], CAM_KO["other"])), cells))
    vhead = "".join("<th class=sc>%s %s<div class=s>%d자 ≈ %.1f초 · 지적 %d개</div></th>" % (
        "★추천" if v.get("type") == chosen else "", e(v.get("type", "")), len(" ".join(v.get("lines") or [])),
        len(" ".join(v.get("lines") or [])) / tb.CHARS_PER_SEC, len(issues.get(v.get("type", ""), [])))
        for v in versions)
    notes = "".join("<h3>%s</h3><ul>%s</ul>" % (e(v.get("type", "")), "".join("<li>%s</li>" % e(x) for x in issues.get(v.get("type", ""), []))
                                                  or "<li>지적 없음</li>") for v in versions)
    others = "".join(
        "<div class=c%s><img src='%s'><div class=s>후보 %d · %s · %d%s</div></div>" % (
            " style='opacity:.45'" if (j["has_text"] or j["has_people"]) else "", _thumb_b64(j["path"], 200), j["no"],
            e(KO.get(j["kind"], j["kind"])), j["wow"],
            " · 제외(" + ("글자" if j["has_text"] else "") + ("사람" if j["has_people"] else "") + ")" if (j["has_text"] or j["has_people"]) else "")
        for j in state["judged"] if j["no"] not in state["picks"])
    cost = len(picks) * VEO_WON_PER_4S
    page = """<!doctype html><html lang=ko><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>여행 쇼츠 검토</title><style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#15181d;--sub:#5b6472;--line:#e3e6eb;--acc:#0a84c6}
@media (prefers-color-scheme:dark){:root{--bg:#0f1216;--card:#171b21;--ink:#e8ebef;--sub:#9aa3af;--line:#2a3039;--acc:#4cb3ea}}
body{margin:0;background:var(--bg);color:var(--ink);font-family:system-ui,'Malgun Gothic',sans-serif;font-size:15px;line-height:1.6}
.w{max-width:1280px;margin:0 auto;padding:24px 16px 60px}h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:26px 0 10px}
.box{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin-top:14px;overflow-x:auto}
table{border-collapse:collapse;width:100%%;min-width:900px}td,th{border-bottom:1px solid var(--line);padding:8px;vertical-align:top;text-align:left}
td img{width:180px;border-radius:8px;display:block}th.sc,td.sc{min-width:220px}td.d{min-width:200px}h3{font-size:15px;margin:12px 0 4px}td img.v{width:90px}.n{font-weight:800;color:var(--acc);font-size:18px}
.s{font-size:12px;color:var(--sub);margin-top:3px}.d{max-width:220px}.g{display:flex;flex-wrap:wrap;gap:10px}.c img{width:200px;border-radius:8px}
ol li{margin:3px 0}</style><div class=w>
<h1>여행 쇼츠 검토 — %s</h1><div class=s>%s · 공식 사진 %d장 중 %d장 판정 · %s · 영상화 전 단계에서 멈춤</div>
<div class=box><h2 style=margin-top:0>진행 단계</h2><ol>%s</ol>
<div class=s>영상화 예상 비용: 4초 클립 %d개 × 약 %d원 = 약 %s원(기존 실측 단가) · 음성: 일레븐 미나(1.35배)</div>
<div class=s>모자란 칸: %s</div></div>
<div class=box><h2 style=margin-top:0>고른 7장과 줄별 대본</h2><table><tr><th>컷</th><th>원본</th><th>세로 시작 화면</th><th>무엇이 보이나</th>%s</tr>%s</table></div>
<div class=box><h2 style=margin-top:0>대본 관문 지적(사진에 없는 말·길이 등)</h2>%s</div>
<div class=box><h2 style=margin-top:0>나머지 후보 — 바꾸려면 "3번 칸을 후보 12로" 처럼 말씀해 주세요</h2><div class=g>%s</div></div>
</div></html>""" % (e(d.get("name") or ""), e(d.get("source_label") or ""), len(d.get("photos") or []), len(state["judged"]),
                     e(d.get("address") or ""), stages, len(picks), VEO_WON_PER_4S, format(cost, ","),
                     e(json.dumps(state.get("short") or {}, ensure_ascii=False)) if state.get("short") else "없음",
                     vhead, rows, notes, others)
    out = work / "review.html"
    out.write_text(page, encoding="utf-8")
    print("검토 화면:", out)
    return out


def stage_render(work, script_idx=None, swaps=None, no_veo=False):
    state = json.loads((work / "state.json").read_text(encoding="utf-8"))
    if swaps:
        for slot, no in swaps.items():
            state["picks"][slot - 1] = no
        _frames_and_script(state, work)
        print("사진을 바꿔 대본을 다시 썼다 — 검토 화면을 다시 보고 render 를 다시 부르세요.")
        return
    by_no = {j["no"]: j for j in state["judged"]}
    picks = [by_no[n] for n in state["picks"]]
    versions = state["script"]["versions"]
    if script_idx is None and not state["script"].get("clean"):
        raise SystemExit("세 안 모두 관문 지적이 남아 있다 — 검토 화면을 보고 --script 번호로 직접 고르세요(돈 드는 영상화는 사람이 고른 뒤에만)")
    v = versions[script_idx] if script_idx is not None else state["script"]["chosen"]
    lines = v["lines"]
    # 안이 정한 사진 순서(order)대로 사진·시작 화면을 다시 세운다 — 판단은 travel_build.ordered_picks 한 곳
    order_idx = [picks.index(p) for p in tb.ordered_picks(picks, v)]
    picks = [picks[k] for k in order_idx]
    state["frames"] = [state["frames"][k] for k in order_idx]
    hard =[x for x in tb.script_issues(lines, state["detail"], len(picks)) if not x.startswith("길이")]
    if hard:                                    # 이름·가격·지역·가 본 척은 사람이 골라도 렌더하지 않는다
        raise SystemExit("대본 금지 검사 탈락 — 렌더하지 않는다: %s" % hard)
    rep = state["rep"]
    t = time.time()
    clips = []
    for i, (p, fr) in enumerate(zip(picks, state["frames"])):
        out = work / ("clip_n%02d.mp4" % p["no"])        # 사진 번호로 이름 — 순서가 바뀌어도 같은 사진의 클립을 다시 쓴다
        if not (out.exists() and out.stat().st_size > 10_000):
            if no_veo:
                va._run_ffmpeg(["ffmpeg", "-y", "-loop", "1", "-i", fr["path"], "-t", "4", "-r", "30", "-vf", "scale=1080:1920",
                                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(out)])
            else:
                prompt = ai_scene.build_travel_prompt(p["kind"], p["desc_en"], 4)
                (work / ("prompt_%d.txt" % i)).write_text(prompt, encoding="utf-8")
                ai_scene.generate(fr["path"], prompt, 4, str(out))
            print("  클립 %d/%d" % (i + 1, len(picks)), flush=True)
        clips.append(str(out))
    rep["steps"]["영상화"] = round(time.time() - t, 1)
    t = time.time()
    from shopping_shorts import tts, audio_post
    tts_paths = []
    for i, line in enumerate(lines):
        out = work / ("tts_%d.mp3" % i)
        tts.synthesize_tts(line, str(out), voice_id=MINA["voice_id"], voice_settings=MINA["voice_settings"],
                           model_id=MINA["model_id"], speed=1.0,
                           previous_text=lines[i - 1] if i else None, next_text=lines[i + 1] if i + 1 < len(lines) else None)
        audio_post.finish_line_audio(str(out), tempo=MINA["tempo"], silence_trim="mid")
        tts_paths.append(str(out))
    rep["steps"]["음성"] = round(time.time() - t, 1)
    t = time.time()
    plan, srcs = tb.build_plan(lines, tts_paths, clips, va._probe_duration)
    deco = tb.deco_for(state["detail"])
    final = work / "final.mp4"
    tmap = {i: p for i, p in enumerate(tts_paths)}
    va.assemble(plan, tmap, srcs, str(final), deco=deco, caption_style={"position": "mid"})
    rep["steps"]["렌더"] = round(time.time() - t, 1)
    tl = va._beat_timeline(plan, tmap)
    proj, _, _ = capcut_draft.assemble_draft_folder(str(work / "capcut"), "C:/capcut_travel", plan=plan, timeline=tl,
                                                    source_video_paths=srcs, tts_paths=tmap,
                                                    project_name="travel_" + str(state["detail"].get("id") or "x"), deco=deco)
    rep.update(final=str(final), final_sec=va._probe_duration(final), capcut=proj, script=v)
    (work / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print("완성:", final, rep["final_sec"], "초 · 캡컷:", proj)


def main():
    cmd = sys.argv[1]
    if cmd == "pick":
        stage_pick(sys.argv[2], Path(sys.argv[3]).resolve())
    elif cmd == "rescript":           # 사진은 그대로 두고 대본만 다시(대본 규칙을 고친 뒤)
        work = Path(sys.argv[2]).resolve()
        st = json.loads((work / "state.json").read_text(encoding="utf-8"))
        _frames_and_script(st, work)
    elif cmd == "render":
        work = Path(sys.argv[2]).resolve()
        args = sys.argv[3:]
        si = int(args[args.index("--script") + 1]) if "--script" in args else None
        sw = {}
        if "--swap" in args:
            for kv in args[args.index("--swap") + 1].split(","):
                a, b = kv.split("=")
                sw[int(a)] = int(b)
        stage_render(work, si, sw or None, "--no-veo" in args)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
