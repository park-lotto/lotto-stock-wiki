# -*- coding: utf-8 -*-
"""숙소 핵심 꿀팁 가이드북 — NotebookLM 인포그래픽(세로)·슬라이드(PDF) (관제 239, 2026-10-20 사장님).

깔때기: 숏폼(마지막 컷에 가이드북 살짝) → 관련 롱폼 → 고정댓글 링크(쿠팡파트너스·여행 예약) → 이 가이드북을 준다.
원고 주인 = travel_build.guidebook_source(숙소 상세 + review_insights). 그림은 NotebookLM 이 원고로 만든다(지어내기 금지 지시).

사용: py tools/travel/make_guidebook.py <state.json(detail.review_insights 포함)> <출력폴더> [--style bento_grid]
필요: nlm(uv tool install notebooklm-mcp-cli) 로그인 — `nlm login --check` 가 실패면 `nlm login`(구글 로그인만 사장님)
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from shopping_shorts import travel_build as tb  # noqa: E402

FOCUS = ("이 숙소에 처음 가는 사람을 위한 재미있고 예쁜 핵심 꿀팁 가이드북. 숙소 한눈에 → 여기서만 볼 순간 → 가기 전 꿀팁"
         "(후기 언급 수 숫자 강조) → 뭐 먹지 → 숙소 앞 볼거리 → 주의할 점과 해결법 → 추천 1박 동선 순서. 후기 숫자는 그대로 쓰고 지어내지 말 것.")


def nlm(*args, timeout=600):
    r = subprocess.run(["nlm", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                       env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    if r.returncode != 0:
        raise RuntimeError("nlm %s 실패: %s" % (" ".join(args[:2]), (r.stderr or r.stdout)[-300:]))
    return r.stdout


def js(out):
    return json.loads(re.search(r"[\[{].*[\]}]", out, re.S).group(0))


def main():
    state = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    style = sys.argv[sys.argv.index("--style") + 1] if "--style" in sys.argv else "bento_grid"
    d = state["detail"]
    src = out / "guidebook_source.md"
    src.write_text(tb.guidebook_source(d, d.get("review_insights") or {}), encoding="utf-8")
    nb = js(nlm("notebook", "create", "%s 꿀팁 가이드북" % d.get("name", ""), "--json"))["notebook_id"]
    print("노트북", nb)
    nlm("source", "add", nb, "--file", str(src), "--title", "꿀팁 가이드북 원고", "--wait", timeout=900)
    ig = js(nlm("infographic", "create", nb, "-o", "portrait", "-d", "detailed", "--style", style, "--language", "ko",
                "--focus", FOCUS, "-y", "--json"))["artifact_id"]
    sd = js(nlm("slides", "create", nb, "-f", "detailed_deck", "--language", "ko", "--focus", FOCUS, "-y", "--json"))["artifact_id"]
    for _ in range(60):                       # 최대 30분
        st = {x["artifact_id"]: x["status"] for x in js(nlm("studio", "status", nb, "--json"))}
        print(time.strftime("%H:%M:%S"), st, flush=True)
        if all(st.get(a) not in ("queued", "in_progress", "pending", "running") for a in (ig, sd)):
            break
        time.sleep(30)
    nlm("download", "infographic", nb, "--id", ig, "-o", str(out / "guidebook_infographic.png"))
    nlm("download", "slide-deck", nb, "--id", sd, "-o", str(out / "guidebook_slides.pdf"))
    print("끝:", out)


if __name__ == "__main__":
    main()
