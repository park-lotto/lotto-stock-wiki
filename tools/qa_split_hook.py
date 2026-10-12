# -*- coding: utf-8 -*-
"""훅 제목 두 줄 나누기(`split_hook`)를 두 가지 잣대로 잰다 — 고칠 때마다 다시 돌린다(2026-09-22).

왜: 대본 첫 문장이 제목에 그대로 들어가는데 길이 균형만 보고 끊어서
    "아니 텀블러이 / 있다고?"처럼 말이 끊겼다(사장님 제보).

잣대 ①**사람 정답**: 템플릿 견본 20개(실제 채널이 손으로 나눈 것)를 한 줄로 합쳐 다시 나눠
       원래대로 복원되나 본다. 이게 제일 강한 근거다.
잣대 ②**실제 대본 첫 문장**: 서버에서 받아둔 나레이션 첫 문장으로 '말이 끊긴 줄'을 센다.
       파일이 없으면 ①만 돈다(만드는 법은 --help 참고).

실행: py tools/qa_split_hook.py [첫문장.json]
"""
import json
import re
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shopping_shorts.template_copy import split_hook, EVEN_SHOPPING   # noqa: E402

# 말이 끊긴 표시 — split_hook 안의 규칙과 **일부러 따로** 적는다.
#   같은 정규식을 쓰면 "내 규칙이 내 규칙을 통과했다"가 되어 아무것도 못 잡는다.
JOSA_END = re.compile(r"(?:이|가|을|를|은|는|에|와|과|도|만|의|로|으로|부터|까지|에서|한테|보다)$")
MOD_START = re.compile(r"^(?:몰랐던|못한|있는|없는|하는|되는|만든|나온|생긴|좋은|같은|아닌|쓰는"
                       r"|보는|드는|넘는|맞는|싶은|받는|사는|먹는|찾는|남는|난|된|한|할|될)\b")


def human_answers():
    raw = (ROOT / "out" / "precision20-data.js").read_text(encoding="utf-8-sig").strip()
    rows = json.loads(raw.split("=", 1)[1].rstrip(";\r\n "))
    out = []
    for row in rows:
        sample = row.get("sample") or {}
        h1, h2 = (sample.get("hook1") or "").strip(), (sample.get("hook2") or "").strip()
        if h1 and h2:
            out.append((row.get("name", "")[:10], h1, h2))
    return out


def check_human():
    rows = human_answers()
    ok, misses = 0, []
    for name, h1, h2 in rows:
        g1, g2 = split_hook(f"{h1} {h2}")
        if (g1, g2) == (h1, h2):
            ok += 1
        else:
            misses.append((name, f"{h1} / {h2}", f"{g1} / {g2}"))
    print(f"① 사람 정답 복원: {ok}/{len(rows)}")
    for name, want, got in misses:
        print(f"   ✗ [{name}] 정답 {want}")
        print(f"      {' ' * (len(name) + 4)}코드 {got}")
    return ok, len(rows)


def check_real(path: Path):
    if not path or not path.exists():
        print("② 실제 대본 첫 문장: 파일 없음 — 건너뜀")
        print(f"   (만들려면 서버 reference.db의 edit_plan_json에서 timeline[0].narration을 모아 "
              f"JSON 배열로 저장하고 경로를 인자로 준다)")
        return None
    lines = [re.sub(r"\s+", " ", x).strip() for x in json.loads(path.read_text(encoding="utf-8"))]
    lines = [x for x in lines if len(x.split()) >= 2]
    bad_josa = bad_mod = 0
    len1, len2 = [], []
    for text in lines:
        a, b = split_hook(text)
        if not b:
            continue
        len1.append(len(a))
        len2.append(len(b))
        last = a.split()[-1]
        if len(last) > 1 and JOSA_END.search(last):
            bad_josa += 1
        if MOD_START.search(b):
            bad_mod += 1
    total = bad_josa + bad_mod
    print(f"② 실제 대본 첫 문장 {len(lines)}개")
    print(f"   첫 줄이 조사로 끝남      : {bad_josa}건")
    print(f"   둘째 줄이 꾸밈말로 시작   : {bad_mod}건")
    print(f"   → 말 끊긴 줄나눔 {total}/{len(lines)} = {total / max(1, len(lines)) * 100:.1f}%")
    print(f"   길이: 첫 줄 중앙 {st.median(len1):.0f}(계약 {EVEN_SHOPPING.hook_line_max}) "
          f"/ 둘째 줄 중앙 {st.median(len2):.0f}(계약 {EVEN_SHOPPING.hook2_line_max})")
    return total, len(lines)


if __name__ == "__main__":
    ok, total = check_human()
    print()
    arg = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    check_real(arg)
    # 사람 정답은 실제 화면에 들어가는 값이라 이것부터 통과해야 한다.
    sys.exit(0 if ok == total else 1)
