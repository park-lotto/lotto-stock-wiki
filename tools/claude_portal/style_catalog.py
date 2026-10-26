"""판 요약 만들기(관제 266) — 엔진 판 설정(tools/calcopy/hybrid/styles/*판.json)에서 설정 화면이 쓰는 칸만 뽑아
shopping_shorts/claude_styles.json 에 둔다. 라이브 서버엔 판 파일이 없어서(엔진 트랙에만 있다) 이 요약을 읽는다.

  py tools/claude_portal/style_catalog.py --engine <엔진 트랙 폴더> [--ref HEAD]      # 쓰기
  py tools/claude_portal/style_catalog.py --engine <엔진 트랙 폴더> [--ref HEAD] --check  # 다르면 rc=1(쓰지 않음)

★읽는 곳 = 엔진 트랙의 **커밋된 판**(--ref, 기본 HEAD) — 작업 트리가 아니다. 다른 창이 만들고 있는 커밋 전 판(10-26 실측: 이븐쇼핑판.json)이
  라이브 목록에 새지 않게.

뽑는 칸 = claude_studio.style_summary 가 읽는 것만(bench.channel · voice.name/voice_id · packs.sfx/motion/bgm · bgm.id · thumb_card_face).
대본·컷·자리 규칙·근거 문서 경로 같은 노하우는 안 옮긴다(회원 화면에 필요 없다).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "shopping_shorts" / "claude_styles.json"


def slim(d: dict) -> dict:
    packs = d.get("packs") or {}
    pick = lambda x, keys: {k: x[k] for k in keys if isinstance(x, dict) and k in x}   # noqa: E731
    return {"bench": pick(d.get("bench") or {}, ("channel",)),
            "voice": pick(d.get("voice") or {}, ("name", "voice_id")),
            "bgm": pick(d.get("bgm") or {}, ("id",)),
            "thumb_card_face": bool(d.get("thumb_card_face")),
            "packs": {"sfx": pick(packs.get("sfx") or {}, ("pack", "map")),
                      "motion": pick(packs.get("motion") or {}, ("pack", "graphics")),
                      "bgm": pick(packs.get("bgm") or {}, ("id",))}}


STYLES_REL = "tools/calcopy/hybrid/styles"


def committed_styles(engine: Path, ref: str = "HEAD") -> dict:
    """{판 이름: 판 설정} — 엔진 트랙 ref 에 커밋된 *판.json 만."""
    import subprocess
    git = lambda *a: subprocess.run(["git", "-C", str(engine), *a], capture_output=True, check=True).stdout   # noqa: E731
    names = [n for n in git("ls-tree", "-z", "--name-only", f"{ref}:{STYLES_REL}").decode("utf-8").split(chr(0)) if n.endswith("판.json")]
    return {n[:-5]: json.loads(git("show", f"{ref}:{STYLES_REL}/{n}").decode("utf-8")) for n in sorted(names)}


def build(engine: Path, ref: str = "HEAD") -> dict:
    out = {stem: slim(d) for stem, d in committed_styles(engine, ref).items()}
    return {"_about": "판 요약 — tools/claude_portal/style_catalog.py 가 엔진 판에서 만든다. 손으로 고치지 마라(관제 266).", "styles": out}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--ref", default="HEAD")
    a = ap.parse_args()
    data = build(Path(a.engine), a.ref)
    text = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
    old = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
    if a.check:
        print("같음" if old == text else "다름 — 다시 만들어야 합니다")
        return 0 if old == text else 1
    OUT.write_text(text, encoding="utf-8")
    print(f"판 {len(data['styles'])}개 → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
