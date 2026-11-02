# -*- coding: utf-8 -*-
"""고급반 채널 벤치마킹 한 입구(관제 304, 사장님 11-02 "고급형은 그 노하우를 담아준다").

    python tools/calcopy/engine/bench_member.py --channel <유튜브 채널 주소> --out <폴더> --name "<내 프리셋 이름>" [--n 3]
    python tools/calcopy/engine/bench_member.py --video <주소|영상 파일> [--video …] --out <폴더> --name "<이름>"

회원 PC 에서 도는 순서: 채널 쇼츠 조회순 → 받기(회원 로그인) → 뜯기(analyze) → 틀(to_frame) → 프리셋 저장(preset_save).
새 판단은 없다 — 전부 기존 함수를 부르기만 한다(판단 주인: 뜯기 analyze.analyze · 틀 to_frame.main · 합치기 preset_save.save).
이 파일이 정하는 것은 둘뿐: '어느 편을 쓰나'(pick_videos, 조회순) · '어느 틀 묶음에 넣나'(shape_key, 층이 같은 편끼리).

글자·그림 판독은 gemini_free.ask 하나로 간다. 회원 PC 는 CALCOPY_GEMINI_BACKEND=client 라 회원 Claude 가 답하고(shortem_ai),
소리는 회원 PC 받아쓰기(asr_local)가 글로 바꿔 준다. SHORTEM_MEMBER_GEMINI_KEY 가 있으면 회원 본인 키로 먼저 묻고, 실패하면 회원 Claude 로 넘긴다.
서버 키·서버 풀은 쓰지 않는다 — 그 파일들은 이 묶음에 없다(tools/claude_portal/benchmark_pack.py).

마지막 줄 = 결과 JSON {ok, slug, name, presets:[{style, sources}], failed:[{video, why}], source_kind}. 진행 = <out>/progress.json.
결과 폴더 꼴은 엔진 프리셋과 같다: <out>/channel/<slug>/preset/<틀>/ · <out>/channel/<slug>/뜯기/<편>/뜯기.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MAX_VIDEOS = 5
SHORT_URL = "https://www.youtube.com/shorts/{}"
DOWNLOAD_FMT = "bv*[height>=1080]+ba/bv*[height>=720]+ba/b"   # 틀은 화면 크기로 재므로 720p 아래는 쓰지 않는다
KEEP_IN_TEAR = ("뜯기.json",)                                  # 뜯기 폴더에서 프리셋에 남길 것 — 나머지(프레임·자막 조각)는 벤치 화면이라 지운다
KIND_PROMPT = ("아래는 어떤 쇼츠 채널의 영상 제목·자막이다. 이 채널이 소재를 어디서 가져오는지 하나만 고른다. "
               "해외영상=해외 영상을 가져와 설명, 제품비하인드=제품·브랜드 뒷이야기, 커뮤니티=게시판 글·썰, 뉴스=뉴스 기사, 고객제품=판매 제품 소개. "
               '답 JSON: {{"source_kind": "<다섯 중 하나>"}}\n\n{text}')


def say(out: Path, what: str, n: int = 0, m: int = 0) -> None:
    (out / "progress.json").write_text(json.dumps({"what": what, "n": n, "m": m}, ensure_ascii=False), encoding="utf-8")


def pick_videos(channel: str, n: int, stats=None) -> list[dict]:
    """(판단 주인) 채널에서 쓸 편 = 조회수 높은 순 n편."""
    if stats is None:
        from tools.calcopy.engine.yt_channel import channel_stats as stats
    st = stats(channel, 30)
    if not st:
        raise ValueError("채널을 읽지 못했습니다 — 주소를 확인하거나 영상 주소로 주세요")
    rows = [v for v in st.get("videos") or [] if v.get("id")]
    rows.sort(key=lambda v: -(v.get("views") or 0))
    return [{"id": v["id"], "url": SHORT_URL.format(v["id"]), "title": v.get("title") or "", "views": v.get("views")} for v in rows[:n]]


def given_videos(items: list[str]) -> list[dict]:
    out = []
    for x in items:
        p = Path(x)
        vid = p.stem if p.is_file() else (re.search(r"(?:shorts/|v=|youtu\.be/|reel/|video/)([0-9A-Za-z_-]+)", x) or [None, hashlib.sha1(x.encode()).hexdigest()[:11]])[1]
        out.append({"id": vid, "url": x, "title": "", "views": None})
    return out


def fetch(v: dict, d: Path, dl=None) -> Path:
    """영상 한 편을 이 PC 로 — 파일이면 그대로, 주소면 회원 로그인으로 받는다(주인 = yt_fetch.ytdlp)."""
    if Path(v["url"]).is_file():
        return Path(v["url"])
    if dl is None:
        from tools.calcopy.engine.yt_fetch import download_full as dl
    dst = d / f"{v['id']}.mp4"
    r = dl(v["url"], dst, fmt=DOWNLOAD_FMT)
    if getattr(r, "returncode", 1) != 0 or not dst.is_file():
        raise ValueError("영상을 받지 못했습니다 — 유튜브 로그인을 확인해 주세요")
    return dst


def member_llm():
    """글자·그림 판독 창구. 회원 본인 제미나이 키가 있으면 먼저, 아니면(또는 실패하면) 회원 Claude(gemini_free.ask = client 창구)."""
    from tools.calcopy.engine import gemini_free as GF
    key = os.environ.get("SHORTEM_MEMBER_GEMINI_KEY", "").strip()
    if not key:
        return GF.ask

    def ask(parts, prompt, tag="", models=None):
        d, err = gemini_with_key(key, parts, prompt)
        if d is not None:
            d["_via"] = "member_key"
            return d, None
        print(f"[bench] 회원 제미나이 키 실패({tag}): {err} → 회원 Claude 로 넘긴다", file=sys.stderr)
        return GF.ask(parts, prompt, tag, models)
    return ask


def gemini_with_key(key: str, parts: list, prompt: str, client=None) -> tuple[dict | None, str | None]:
    from google import genai
    from google.genai import types
    from tools.calcopy.engine import gemini_free as GF
    contents = []
    for p in parts or []:
        if isinstance(p, (bytes, bytearray)):
            contents.append(types.Part.from_bytes(data=bytes(p), mime_type="image/jpeg"))
        elif isinstance(p, tuple):
            contents.append(types.Part.from_bytes(data=p[0], mime_type=p[1]))
        else:
            contents.append(p)
    contents.append(prompt)
    try:
        c = client or genai.Client(api_key=key, http_options=types.HttpOptions(timeout=GF.TIMEOUT_MS))
        r = c.models.generate_content(model=GF.PRIMARY, contents=contents,
                                      config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0, seed=GF.SEED))
        d = json.loads(r.text)
    except Exception as e:  # noqa: BLE001 — 실패 이유를 돌려주면 부르는 쪽이 회원 Claude 로 넘긴다
        return None, f"{type(e).__name__}: {str(e)[:120]}"
    d = {"items": d} if isinstance(d, list) else d
    return (d, None) if isinstance(d, dict) else (None, "JSON 객체가 아니다")


def tear(mp4: Path, d: Path, llm) -> tuple[dict, dict, Path]:
    """영상 한 편 → (뜯기, 틀 설명서, 뜯기 파일). 주인 = analyze.analyze · to_frame.main."""
    from tools.calcopy.engine import analyze as A, to_frame as T
    d.mkdir(parents=True, exist_ok=True)
    J = A.analyze(str(mp4), str(d), llm=llm, materials=False)
    jp, fp = d / "뜯기.json", d / "frame.json"
    T.main([str(jp), "--out", str(fp)])
    return J, json.loads(fp.read_text(encoding="utf-8")), jp


def shape_key(frame: dict) -> tuple:
    """(판단 주인) 같은 틀인가 — 층의 종류·역할이 같아야 한 프리셋으로 합친다."""
    frames = frame.get("frames") if isinstance(frame.get("frames"), list) else [frame]
    return tuple(tuple(sorted(f"{L.get('kind')}:{L.get('role')}" for L in (f.get("layers") or []))) for f in frames)


def pick_kind(texts: list[str], llm) -> str:
    from tools.calcopy.engine.topic_find import SOURCE_KINDS
    d, err = llm([], KIND_PROMPT.format(text="\n".join(texts)[:3000]), tag="bench_kind")
    kind = (d or {}).get("source_kind")
    if kind not in SOURCE_KINDS:
        print(f"[bench] 소재 유형을 못 정했다({kind!r}, {err}) → 해외영상으로 둔다", file=sys.stderr)
        return "해외영상"
    return kind


def tidy(d: Path) -> None:
    for p in d.iterdir():
        if p.name in KEEP_IN_TEAR:
            continue
        shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)


def slug_of(name: str) -> str:
    return "my_" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]


def run(out: Path, name: str, channel: str = "", videos: list[str] | None = None, n: int = 3, deps: dict | None = None) -> dict:
    from tools.calcopy.engine import preset_save as P
    deps = deps or {}
    out.mkdir(parents=True, exist_ok=True)
    llm = deps.get("llm") or member_llm()
    slug = slug_of(name)
    ch = out / "channel" / slug
    n = max(1, min(int(n), MAX_VIDEOS))
    say(out, "채널 영상 고르는 중")
    picked = given_videos(videos)[:MAX_VIDEOS] if videos else pick_videos(channel, n, deps.get("stats"))
    groups: dict = {}
    failed, texts = [], []
    for i, v in enumerate(picked):
        try:
            say(out, "영상 받는 중", i + 1, len(picked))
            mp4 = fetch(v, out / "src", deps.get("download"))
            say(out, "영상 뜯는 중", i + 1, len(picked))
            tdir = ch / "뜯기" / v["id"]
            J, frame, jp = (deps.get("tear") or tear)(mp4, tdir, llm)
            key = shape_key(frame)
            if key not in groups:
                groups[key] = {"style": "틀" if not groups else f"틀{len(groups) + 1}", "sources": []}
            g = groups[key]
            say(out, "프리셋 저장 중", i + 1, len(picked))
            P.save(J, frame, ch / "preset" / g["style"], v["id"], f"channel/{slug}/뜯기/{v['id']}/뜯기.json")
            g["sources"].append(v["id"])
            texts.append(v.get("title") or "")
            texts += [" ".join(it.get("text") or []) for it in ((J.get("captions") or {}).get("items") or [])[:6]]
            tidy(tdir)
        except Exception as e:  # noqa: BLE001 — 한 편이 실패해도 나머지로 간다. 이유는 결과에 남긴다(조용히 넘어가지 않는다)
            failed.append({"video": v["id"], "why": f"{type(e).__name__}: {str(e)[:160]}"})
    if not groups:
        return {"ok": False, "name": name, "slug": slug, "presets": [], "failed": failed,
                "why": "프리셋을 만들 수 있는 영상이 없습니다"}
    kind = pick_kind(texts, llm)
    for g in groups.values():
        P.set_meta(ch / "preset" / g["style"], source_kind=kind)
    shutil.rmtree(out / "src", ignore_errors=True)
    ordered = sorted(groups.values(), key=lambda g: -len(g["sources"]))
    return {"ok": True, "name": name, "slug": slug, "source_kind": kind, "failed": failed,
            "presets": [{"style": g["style"], "sources": g["sources"]} for g in ordered]}


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="")
    ap.add_argument("--video", action="append", default=[])
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--n", type=int, default=3)
    a = ap.parse_args(argv)
    if not a.channel and not a.video:
        print(json.dumps({"ok": False, "why": "채널 주소나 영상 주소가 필요합니다"}, ensure_ascii=False))
        return 2
    try:
        r = run(Path(a.out), a.name, a.channel, a.video, a.n)
    except Exception as e:  # noqa: BLE001 — 마지막 줄은 늘 JSON(부르는 쪽이 이유를 읽는다)
        r = {"ok": False, "why": f"{type(e).__name__}: {str(e)[:200]}"}
    print(json.dumps(r, ensure_ascii=False))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
