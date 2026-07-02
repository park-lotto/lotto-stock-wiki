"""build_brain.py — 브레인 페이지의 AUTO 마커 섹션만 갱신 (수동 뼈대 보존).

CLI:
    python -m pipeline.people.build_brain 태린이아빠
"""
import sys
import io
import re
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pipeline.people.registry import get_person
from pipeline.people.people_query import atoms_for

_ROOT = Path(__file__).parent.parent.parent


def render_live_stance(atoms):
    if not atoms:
        return "_(활성 스탠스 없음)_"
    lines = []
    for a in atoms:
        asset = a.get("asset") or a.get("sector") or "?"
        lines.append(f"- **{asset}** ({a.get('signal','')}) — {a['content']} "
                     f"·{a['date']} {a['source_name']}")
    return "\n".join(lines)


def render_speech_log(atoms):
    if not atoms:
        return "_(발언 없음)_"
    lines = []
    for a in atoms:
        lines.append(f"- `{a['date']}` [{a.get('content_type','')}] "
                     f"{a.get('source_name','')} {a.get('sector','')}/{a.get('asset','')}: {a['content']}")
    return "\n".join(lines)


def update_markers(page_text, sections):
    out = page_text
    for key, body in sections.items():
        pattern = re.compile(
            rf"(<!-- AUTO:{re.escape(key)} -->)(.*?)(<!-- /AUTO:{re.escape(key)} -->)",
            re.DOTALL,
        )
        out = pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(3)}", out)
    return out


def build(person):
    cfg = get_person(person)
    page_path = _ROOT / cfg["brain_page"]
    text = page_path.read_text(encoding="utf-8")
    stance = atoms_for(person, stance_only=True, days=30)
    log = atoms_for(person, days=14, limit=40)
    updated = update_markers(text, {
        "live_stance": render_live_stance(stance),
        "speech_log": render_speech_log(log),
    })
    page_path.write_text(updated, encoding="utf-8")
    return updated


if __name__ == "__main__":
    person = sys.argv[1] if len(sys.argv) > 1 else "태린이아빠"
    build(person)
    print(f"[{person}] 브레인 페이지 자동 섹션 갱신 완료.")
