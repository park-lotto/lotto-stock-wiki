# -*- coding: utf-8 -*-
"""흩어진 효과음을 한곳에 모으고 종류·길이 목록을 만든다 (관제 331).

    py -X utf8 tools/asset_library/build.py sfx [--dry] [--lib C:/숏템_자산]

판단 주인 = build() 하나. 원본은 옮기거나 지우지 않는다(복사만).
- 같은 파일은 내용 지문(sha1)으로 하나만 남긴다
- 종류 = 파일·폴더 이름 낱말(KINDS). 못 정하면 '기타'(나중에 듣고 분류)
- 길이 = ffprobe 실측. 6초 넘는 소리는 효과음이 아니라 '긴소리'(배경음 후보)로 뺀다
결과: <lib>/효과음/<종류>/<원래이름> + <lib>/효과음/목록.json
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
SOURCES = [
    HOME / "Desktop/지난작업_보관/효과음_배경음_모음",
    HOME / "Desktop/로또의 주식/shopping_shorts/assets/sfx_packs",
    HOME / "Desktop/지난작업_보관/쇼츠AI_스타터킷",
    HOME / "Desktop/지난작업_보관/MakeLens",
    HOME / "Downloads/soundFX",
    HOME / "Desktop/로또의 주식/remotion-stock/public/sfx",
    Path("C:/숏템_칼카피/sseolpulda/sfx_pack"),
]
SKIP_DIRS = ("배경음", "bgm", "music", "음악", ".venv", "site-packages", "tests", "audio_sample", "_internal")   # 배경음은 4단계에서 따로
AUD = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"}
LONG_S = 6.0

# 앞에 있는 것이 먼저 잡힌다(구체적인 것 먼저)
KINDS = [
    ("휙", ["whoosh", "swoosh", "swish", "휙", "슉", "swipe", "transition", "전환"]),
    ("팝", ["pop", "팝", "뽁", "bubble", "뾱"]),
    ("클릭", ["click", "클릭", "tap", "탭", "딸깍", "mouse", "키보드", "타자"]),
    ("박수", ["clap", "박수", "applause"]),
    ("웃음", ["laugh", "웃음", "haha", "sitcom"]),
    ("놀람", ["surprise", "놀람", "gasp", "wow", "헉", "shock", "vine"]),
    ("띵동", ["ding", "띵", "bell", "chime", "notification", "알림"]),
    ("정답", ["correct", "정답", "success", "성공", "level", "coin", "코인"]),
    ("오답", ["wrong", "오답", "fail", "실패", "error", "buzzer", "땡"]),
    ("반짝", ["sparkle", "shine", "반짝", "twinkle", "magic", "마법", "glitter"]),
    ("쿵", ["boom", "쿵", "impact", "punch", "thud", "drop", "bass", "강조"]),
    ("뿅", ["뿅", "boing", "spring", "cartoon", "만화", "slide", "zip"]),
    ("카메라", ["camera", "shutter", "찰칵", "사진"]),
    ("돈", ["cash", "money", "돈", "register", "ka-ching", "kaching"]),
    ("글리치", ["glitch", "글리치", "static", "noise"]),
    ("상승", ["rise", "riser", "상승", "build", "uplift"]),
    ("코믹", ["fart", "방귀", "funny", "코믹", "웃긴", "honk", "quack"]),
    ("긴장", ["suspense", "긴장", "tension", "drum", "드럼", "dun"]),
]


def kind_of(path: Path) -> str:
    t = (path.parent.name + "/" + path.name).lower()   # 이름과 바로 위 폴더만(먼 폴더 낱말이 잘못 잡던 것: '종합'→띵동)
    for k, words in KINDS:
        if any(w in t for w in words):
            return k
    return "기타"


def dur(p: Path) -> float | None:
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                             capture_output=True, text=True, timeout=20).stdout.strip()
        return round(float(out), 3)
    except Exception:  # noqa: BLE001 — 못 재면 목록에 None 으로 남긴다(지어내지 않음)
        return None


def length_band(d: float | None) -> str:
    if d is None:
        return "모름"
    return "아주짧음(~0.5초)" if d <= 0.5 else "짧음(0.5~1.5초)" if d <= 1.5 else "보통(1.5~3초)" if d <= 3 else "김(3~6초)"


def build(lib: Path, dry: bool = False) -> dict:
    out = lib / "효과음"
    seen: dict[str, dict] = {}
    dup = 0
    for src in SOURCES:
        if not src.exists():
            continue
        for dp, _dn, fn in os.walk(src):
            if any(s in os.path.relpath(dp, src).lower() for s in SKIP_DIRS):   # 뿌리 이름(효과음_배경음_모음)은 보지 않는다
                continue
            for f in fn:
                p = Path(dp) / f
                if p.suffix.lower() not in AUD:
                    continue
                h = hashlib.sha1(p.read_bytes()).hexdigest()
                if h in seen:
                    dup += 1
                    seen[h]["also"].append(str(p))
                    continue
                d = dur(p)
                k = "긴소리" if d and d > LONG_S else kind_of(p)
                seen[h] = {"sha1": h, "kind": k, "sec": d, "band": length_band(d) if k != "긴소리" else "6초 넘음",
                           "name": p.name, "src": str(p), "also": []}
    # 이름 읽기 분류(sfx_kinds.json, 지문 앞 10자 → kind·mood)가 있으면 그것이 낱말 분류보다 먼저다
    kinds_file = Path(__file__).with_name("sfx_kinds.json")
    if kinds_file.exists():
        km = json.loads(kinds_file.read_text(encoding="utf-8"))
        for r in seen.values():
            v = km.get(r["sha1"][:10])
            if v and r["kind"] != "긴소리":
                r["kind"], r["mood"] = v["kind"], v.get("mood")
    # 복사 — 같은 이름은 지문 앞 6자를 붙인다
    used = set()
    for r in seen.values():
        dst = out / r["kind"] / r["name"]
        if (r["kind"], r["name"].lower()) in used:
            dst = dst.with_name(f"{dst.stem}_{r['sha1'][:6]}{dst.suffix}")
        used.add((r["kind"], dst.name.lower()))
        r["file"] = str(dst.relative_to(lib))
        if not dry:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                shutil.copy2(r["src"], dst)
    items = sorted(seen.values(), key=lambda r: (r["kind"], r["sec"] or 0))
    summary: dict[str, dict] = {}
    for r in items:
        s = summary.setdefault(r["kind"], {"n": 0})
        s["n"] += 1
        s[r["band"]] = s.get(r["band"], 0) + 1
    res = {"total": len(items), "duplicates_skipped": dup, "by_kind": summary, "items": items}
    if not dry:
        out.mkdir(parents=True, exist_ok=True)
        (out / "목록.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


if __name__ == "__main__":
    a = sys.argv[1:]
    lib = Path(a[a.index("--lib") + 1]) if "--lib" in a else Path("C:/숏템_자산")
    r = build(lib, dry="--dry" in a)
    print(f"모은 효과음 {r['total']}개 · 같은 파일 건너뜀 {r['duplicates_skipped']}개")
    for k, s in sorted(r["by_kind"].items(), key=lambda x: -x[1]["n"]):
        print(f"  {k:6s} {s['n']:4d}  " + " · ".join(f"{b} {n}" for b, n in s.items() if b != "n"))
