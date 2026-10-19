# -*- coding: utf-8 -*-
"""샥탬스토리 하이브리드 — 앞 = 새 엔진으로 다시 렌더한 칼카피 0~cut 초(후킹), 뒤 = 같은 옷(지훈·샥탬 프리셋·같은 BGM 이어서)의 1인칭 체험 나레 (관제 097, 2026-10-18).

    PYTHONUTF8=1 py tools/calcopy/shark/hybrid.py <하이브리드 doc 폴더> <작업 폴더> [--plan] [--preview] [--confirm-tts] [--back-only] [--desktop <mp4>]

  --plan        뒤를 TTS 없이 추정 시각으로 줄표·컷표만(render.py --plan 그대로)
  --preview     뒤를 삐 소리로 끝까지 렌더 + 앞과 이어 붙임(비용 0, 컷·크롭·이음 눈 확인)
  --back-only   뒤만 렌더(앞 수리본이 아직 없을 때). 이어 붙이기는 나중에 다시 부르면 뒤 렌더를 재사용
  --confirm-tts 타입캐스트를 처음 부를 때만(페이블 OK 뒤 1회)

  앞 = front_render(): 앞 render_info 의 engine 표식이 지금 엔진(render.ENGINE)과 다르면 앞 칼카피를 새 엔진으로 다시 렌더한다
        (물건 원·적중 검사·고급 모양·−14 LUFS) — 작업 폴더 <앞 작업>/../엔진v2(또는 hybrid.front_work), 옛 타입캐스트 나레 재사용(--tts-from, 비용 0).
        옛 완성 mp4(front_src)는 새 판이 없을 때(--old-front)만.
  뒤 꾸밈 = 뒤 재료.json effects 를 shark/render.py 가 그대로 받는다(대상·적중 검사 같은 길) — 대상 확실한 것만.
판단 주인(여기서 정하는 것은 넷뿐 — 나머지는 shark/render.py 를 부른다):
  ⓪ 앞 판 고르기     front_render()
  ① 앞 자르기 시각  front_cut()   — 대본 hybrid.cut(앞 render_info 줄 경계) → 프레임 단위(30fps 안쪽)
  ② BGM 이어 틀기    back_defaults() — 앞 편 BGM 곡(앞 render_info.audio_mix.bgm)을 ①초부터(render.DEF bgm·bgm_ss, 대본엔 안 적는다 = 한 곳)
  ③ 이음 효과        join()        — 앞 마지막 프레임을 늘려 뒤 첫 dur 초와 xfade(제목 띠 keep_top 위는 고정), 소리는 그대로 이어 붙임
선례: channel/hottemreport/현장썰하이브리드/render_front.py(이음 xfade·띠 고정) — 뒤 렌더러만 샥탬 것으로.
대본.json(뒤) = shark/render.py 꼴(final.lines 전부 나레 + caps·emph, titles = 앞과 같은 제목, voice = 지훈) + hybrid{front_doc, front_src, cut, transition}.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid.common import StageError, dur_of, jload, jsave, lufs, md5, run  # noqa: E402
from tools.calcopy.shark import render as SR_  # noqa: E402

FPS = 30
LIM = 10 ** ((SR_.LOUD["true_peak_max"] - 1.0) / 20)   # 이음 리미터 = 렌더와 같은 목표(rules.json loudness) — 앞·뒤 둘 다 −14 LUFS 로 렌더돼 이음도 같은 크기


def front_info(H: dict, doc: Path, old: bool = False, plan: bool = False) -> dict:
    fd = (doc / H["front_doc"]).resolve()
    ri = Path(H["front_render_info"])
    if not ri.exists():
        raise StageError(f"앞 render_info 없음 {ri}")
    if old:
        return {"doc": fd, "info": jload(ri), "src": Path(H["front_src"]), "how": "옛 완성본(--old-front)"}
    return front_render(H, fd, ri, plan)


def front_render(H: dict, fd: Path, ri: Path, plan: bool = False) -> dict:
    """(판단 주인: 앞 판) 새 엔진(render.ENGINE) 표식이 붙은 앞 렌더가 있으면 그것, 없으면 앞 칼카피를 다시 렌더(옛 나레 재사용)."""
    fw = Path(H.get("front_work") or ri.parents[2] / "엔진v2")
    nri = fw / "render" / "render_info.json"
    if nri.exists() and jload(nri).get("engine") == SR_.ENGINE and (fw / "render" / "final.mp4").exists():
        return {"doc": fd, "info": jload(nri), "src": fw / "render" / "final.mp4", "how": f"새 엔진 앞(있음) {fw}"}
    if plan:      # 계획만 — 옛 줄 시각으로 자리만 본다(같은 나레라 줄 시각 같음)
        return {"doc": fd, "info": jload(ri), "src": Path(H["front_src"]), "how": "계획: 옛 render_info(앞 새 렌더 전)"}
    info = SR_.render(fd, fw, "render", False, None, None, ri.parent)
    return {"doc": fd, "info": info, "src": fw / "render" / "final.mp4", "how": f"새 엔진 앞 렌더 {fw} (나레 재사용 {ri.parent})"}


def front_cut(H: dict, F: dict, check_src: bool = True) -> dict:
    """(판단 주인: 앞 자르기) hybrid.cut_after = 앞 줄 id → 그 줄 끝(t1). 프레임 단위로 안쪽."""
    L = {x["id"]: x for x in F["info"]["lines"]}
    if H["cut_after"] not in L:
        raise StageError(f"앞 줄 {H['cut_after']} 없음")
    x = L[H["cut_after"]]
    t = float(x["t1"])
    nf = int(t * FPS)
    src_dur = dur_of(F["src"]) if check_src else F["info"]["dur"]
    if abs(src_dur - F["info"]["dur"]) > 0.15:
        raise StageError(f"앞 영상 길이 {src_dur:.2f} ≠ 앞 render_info {F['info']['dur']:.2f} — 수리본과 render_info 가 다른 판")
    return {"line": x["id"], "t1": t, "speak_end": x["speak"][1], "nf": nf, "dur": nf / FPS}


def back_defaults(F: dict, cut: dict) -> dict:
    """(판단 주인: BGM 이어 틀기) 앞 편 곡을 앞이 끊긴 초부터."""
    am = F["info"].get("audio_mix") or {}
    if not am.get("bgm"):
        raise StageError("앞 render_info 에 audio_mix.bgm 없음")
    return {"bgm": am["bgm"], "bgm_lufs": am.get("bgm_lufs", SR_.DEF["bgm_lufs"]), "duck_db": am.get("duck_db", SR_.DEF["duck_db"]),
            "bgm_ss": round(cut["dur"] + float(am.get("bgm_ss") or 0.0), 3)}


def render_back(doc: Path, work: Path, mode: str, confirm: bool, bd: dict) -> dict:
    keep = {k: SR_.DEF[k] for k in bd if k in SR_.DEF}     # bgm_ss 는 DEF 기본값이 없다(render 가 C.get("bgm_ss") 로 읽음) — 없던 칸은 끝나고 지운다
    SR_.DEF.update(bd)          # 대본 render 칸이 없으면 이 값(앞과 같은 곡·같은 크기·이어 튼 초)
    S = jload(doc / "대본.json")
    clash = [k for k in bd if k in (S.get("render") or {})]
    if clash:
        raise StageError(f"대본 render 에 {clash} 가 있다 — BGM 은 앞 편에서 정한다(한 곳)")
    try:
        return SR_.render(doc, work, mode, confirm)
    finally:
        for k in bd:              # 앞을 같은 프로세스에서 다시 렌더할 때 뒤 BGM 값이 새지 않게
            if k in keep:
                SR_.DEF[k] = keep[k]
            else:
                SR_.DEF.pop(k, None)


def join(F: dict, cut: dict, back_mp4: Path, tr: dict, R: Path) -> Path:
    """(판단 주인: 이음) 앞 0~cut 프레임 그대로 + 뒤. 이음 화면 효과 = tr.kind(xfade) tr.dur 초, 위 제목 띠(keep_top px)는 고정."""
    front = R / "front.mp4"
    fdur = cut["dur"]
    run(["ffmpeg", "-y", "-i", F["src"], "-frames:v", cut["nf"], "-af", f"atrim=0:{fdur:.4f},afade=t=out:st={fdur - 0.03:.4f}:d=0.03",
         "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", FPS, "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "1", front])
    back = R / "back_cfr.mp4"
    run(["ffmpeg", "-y", "-i", back_mp4, "-vf", f"fps={FPS}", "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "1", back])
    d, band = float(tr.get("dur", 0.25)), int(tr.get("keep_top", 434))
    final = R / "final.mp4"
    run(["ffmpeg", "-y", "-i", front, "-i", back, "-filter_complex",
         f"[0:v]tpad=stop_mode=clone:stop_duration={d:.3f},settb=AVTB,fps={FPS},split[f][fb];[fb]crop=1080:{band}:0:0[band];[1:v]settb=AVTB,fps={FPS}[b];"
         f"[f][b]xfade=transition={tr.get('kind', 'slideleft')}:duration={d:.3f}:offset={fdur:.4f}[x];[x][band]overlay=0:0:eof_action=pass,format=yuv420p[v];"
         f"[0:a][1:a]concat=n=2:v=0:a=1,alimiter=limit={LIM:.4f}:attack=2:release=40:level=false,afade=t=in:d=0.03[a]",   # 이어 붙여 AAC 다시 구우면 최고점이 튐(10-18 4편 미리보기) → rules loudness 트루피크 −1dB 로 막음(R5 한 곳) · 리미터는 첫 몇 ms 를 못 잡아 0초에 +1.3(3편) → 첫 30ms 페이드
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-r", FPS, "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "1", final])
    return final


def plan_md(doc: Path, S: dict, F: dict, cut: dict, bd: dict, info: dict) -> Path:
    """계획 시트(plan/하이브리드_계획.md) — 앞 자르기·이음 문장·뒤 줄별 화면·강조·효과. 숫자는 render_info(뒤 계획)·앞 render_info 에서만."""
    H = S["hybrid"]
    caps_of = {}
    for c in info["captions"]:
        caps_of.setdefault(c["line"], []).append(c)
    emph = {l["id"]: {e["cap"]: f"{e['span']}({e['color']})" for e in l.get("emph") or []} for l in S["final"]["lines"]}
    fl = {x["id"]: x for x in F["info"]["lines"]}
    fcaps = [c for c in F["info"]["captions"] if c["line"] == cut["line"]]
    L = [f"# 하이브리드 계획 — {doc.name} (tools/calcopy/shark/hybrid.py --plan 이 씀)", "",
         f"- 제품: {S.get('product', '')}",
         f"- 앞: `{H['front_src']}` 0~{cut['dur']:.3f}초(프레임 {cut['nf']}) = 앞 줄 {cut['line']} 끝 — 끝 원음 「{' / '.join(c['text'] for c in fcaps)}」 · 까닭: {H.get('cut_why', '')}",
         f"- 이음: {H.get('transition', {}).get('kind')} {H.get('transition', {}).get('dur')}초(제목 띠 y<{H.get('transition', {}).get('keep_top')} 고정) · BGM {bd['bgm']} 를 {bd['bgm_ss']}초부터 이어서 · 목소리 {S['voice']['name']}({S['voice']['voice_id']}, speed {S['voice'].get('speed')}) · 목표 말속도 {S['final']['cps_target']}자/초",
         f"- 뒤 길이(추정 {info['narr'].get('how', '')}): {info['dur']:.2f}초 → 전체 약 {cut['dur'] + info['dur']:.1f}초 · 컷 {info['summary']['cuts']}개 중앙 {info['summary']['cut_median']:.2f}초", "",
         "## 뒤 줄별 (대사 | 자막 조각·강조 | 화면)", "| 줄 | 할 일 | 대사 | 자막(강조 덩어리·색) | 화면(소스@초 — 설명) | 근거 |", "|---|---|---|---|---|---|"]
    for l in S["final"]["lines"]:
        cs = " / ".join(f"{c['text']}" + (f" [{emph[l['id']][c['text']]}]" if c["text"] in emph.get(l["id"], {}) else "") for c in caps_of.get(l["id"], []))
        sh = " · ".join(f"{Path(c['src']).stem[:8]}@{c['ss']} {c['see']}" for c in info["cuts"] if c["line"] == l["id"] and not c.get("dropped"))
        L.append(f"| {l['id']} | {l.get('fn', '')} | {l['text']} | {cs} | {sh} | {', '.join(l.get('facts') or []) or '창작(감상·사회 반응)'} |")
    eff = [f"{e['line']} {e['kind']}" + (f" → {e.get('target_what') or e.get('target')}" if e.get("target") else "") for e in jload(doc / "재료.json").get("effects") or []]
    L += ["", "## 효과", "- 이음 자리 화면 효과 1개(위 이음). 뒤 꾸밈 = 재료 effects(대상 확실한 것만 — 렌더 fx.gate 적중 검사가 미달이면 뺌): " + (", ".join(eff) or "없음"), "",
          "## 근거", *[f"- {k}: {v if isinstance(v, str) else v.get('text')}" for k, v in (S.get("facts") or {}).items()]]
    out = doc / "plan" / "하이브리드_계획.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    return out


def sheets(final: Path, cut: float, out_dir: Path) -> dict:
    """눈 확인 시트: 0~3초 · 이음 자리(cut−1.5~cut+1.5) · 끝 3초 — 각 12장(0.25초 간격, 4×3)."""
    dur = dur_of(final)
    res = {}
    for name, t0 in (("0~3초", 0.0), ("이음", max(0.0, cut - 1.5)), ("끝", max(0.0, dur - 3.0))):
        p = out_dir / f"시트_{name}.jpg"
        run(["ffmpeg", "-y", "-ss", f"{t0:.3f}", "-t", "3", "-i", final, "-vf", "fps=4,scale=270:-1,tile=4x3", "-frames:v", "1", "-q:v", "3", p])
        res[name] = {"path": str(p), "t0": round(t0, 2)}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("doc"); ap.add_argument("work")
    ap.add_argument("--plan", action="store_true"); ap.add_argument("--preview", action="store_true")
    ap.add_argument("--back-only", action="store_true"); ap.add_argument("--confirm-tts", action="store_true"); ap.add_argument("--desktop")
    ap.add_argument("--old-front", action="store_true", help="앞을 옛 완성 mp4(front_src)에서 자름(새 엔진 앞을 안 만든다)")
    a = ap.parse_args()
    doc, work = Path(a.doc).resolve(), Path(a.work).resolve()
    try:
        S = jload(doc / "대본.json")
        H = S["hybrid"]
        F = front_info(H, doc, a.old_front, plan=a.plan or a.back_only)
        print(f"[앞] {F['how']}", flush=True)
        cut = front_cut(H, F, check_src=not (a.back_only or a.plan))
        bd = back_defaults(F, cut)
        mode = "plan" if a.plan else ("preview" if a.preview else "render")
        info = render_back(doc, work, mode, a.confirm_tts, bd)
        s = info["summary"]
        print(f"[뒤 {mode}] {info['dur']:.2f}초 · 컷 {s['cuts']} 중앙 {s['cut_median']:.2f} 최단 {s['cut_min']:.2f} 끝 {s['end_cut']:.2f} · 1.2초 미만 {s['short_cuts']} · 자막 최대 {s['cap_max_chars']}자 · BGM {bd}", flush=True)
        if a.plan:
            print("계획 시트:", plan_md(doc, jload(doc / "대본.json"), F, cut, bd, info))
        if a.plan or a.back_only:
            return
        R = work / ("preview" if a.preview else "render")
        back_mp4 = R / "final.mp4"
        J = work / ("hybrid_preview" if a.preview else "hybrid")
        J.mkdir(parents=True, exist_ok=True)
        final = join(F, cut, back_mp4, H.get("transition") or {}, J)
        from tools.calcopy.engine import check_seams
        win = (0, 434, 1080, 1052)
        seams = check_seams.check(str(final), win, None)
        I, pk = lufs(final)
        res = {"made_by": "tools/calcopy/shark/hybrid.py", "engine": SR_.ENGINE, "front_how": F["how"], "front_src": str(F["src"]), "front_md5": md5(F["src"]), "cut": cut, "bgm": bd,
               "back": str(back_mp4), "back_dur": info["dur"], "back_audio": info.get("audio_mix"), "final": str(final), "final_dur": dur_of(final),
               "final_lufs": I, "final_peak": pk, "front_lufs": lufs(J / "front.mp4"), "back_lufs": lufs(back_mp4),
               "seams": {"ok": seams["ok"], "컷": len(seams["컷"]), "되감김": seams["되감김"], "점프줌": seams["점프줌"], "판정": seams.get("점프줌_판정")},
               "sheets": sheets(final, cut["dur"], J), "md5": md5(final)}
        if a.desktop:
            dst = Path(a.desktop)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(final, dst)
            res["desktop"] = {"path": str(dst), "md5_same": md5(dst) == res["md5"]}
        jsave(J / "hybrid_info.json", res)
        print(f"[하이브리드] {res['final_dur']:.2f}초 · {I} LUFS · 최고점 {pk} · 앞 {res['front_lufs']} 뒤 {res['back_lufs']} · 이음매 {res['seams']} · MD5 {res['md5'][:8]}", flush=True)
    except StageError as e:
        print(f"[멈춤] {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
