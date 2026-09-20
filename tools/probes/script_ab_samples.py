# -*- coding: utf-8 -*-
"""[프로브] 대본 퀄리티 §10-1 — 같은 소스로 쓰는 모델 급(lite vs 상위)을 눈가림 짝으로 뽑는다.
사용: py tools/probes/script_ab_samples.py <job_id> [video_id] [pairs=3]
  → out/probes/script_ab/<job>.md (A/B 무표시) + <job>_answer.json (정답)
전제: 로컬 DB에 잡의 extract가 있어야 한다. 스타일 스파인이 DB에 없으면 합성 스타일 블록으로 돌린다(구조 비교용).
키: SHORTS 풀 0개면 예비풀 키로 우회. 사장님이 A/B를 고른 결과를 answer와 대조해 "모델 급 차이가 보이나"를 잰다."""
import sys, os, json, random, sqlite3, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, ROOT); os.chdir(ROOT)
from shopping_shorts import keyroute, comment_gen, script_generate as SG, bank_assemble
from shopping_shorts.config import DB_PATH

if comment_gen._current_key_and_idx()[0] is None:
    K = keyroute.gemini_keys("general")[0]
    comment_gen._current_key_and_idx = lambda: (K, 0)
    comment_gen.SHORTS_GEMINI_KEYS = [K]
    print("(SHORTS 풀 0개 → 예비풀 키로 우회)")

JOB = sys.argv[1] if len(sys.argv) > 1 else "409f894230c6"
ONLY = sys.argv[2] if len(sys.argv) > 2 else None
PAIRS = int(sys.argv[3]) if len(sys.argv) > 3 else 3
MODELS = ("gemini-3.1-flash-lite", "gemini-3.5-flash")

ex = json.loads(sqlite3.connect(DB_PATH).execute(
    "select extract_json from mix_jobs where job_id=?", (JOB,)).fetchone()[0])
vid = ONLY or next(iter(ex))
e = ex[vid]
src = [{"name": "홈템", "full_text": e.get("full_text_ko") or e.get("full_text") or "", "structure": {},
        "product": (e.get("source_brief") or {}).get("product") or "", "segments": e.get("segments") or []}]

from shopping_shorts.store import Store
spines = [s for s in Store(DB_PATH).list_style_spines() if s.get("beat_roles")]
if spines:
    style = spines[0]
else:
    bank_assemble.style_block = lambda style, seconds=30, seed="": (
        "[스타일] 칸은 정확히 이 순서·이 이름으로 5개: role=첫말 → role=문제 → role=시연 → role=결과 → role=약속. "
        "각 칸 한두 문장, 반말 섞인 구어체. 해결 뒤에 '심지어'로 장점 하나를 더 얹어라(딱 한 번). 전체 110~150자.")
    style = {"id": "syn", "name": "합성", "beat_roles": ["첫말", "문제", "시연", "결과", "약속"], "chars_per_30s": 160}
    print("(스타일 스파인 없음 → 합성 스타일 블록)")
SG._style_extra = lambda: ""
SG._speaker_judge = None

out_dir = Path(ROOT) / "out" / "probes" / "script_ab"; out_dir.mkdir(parents=True, exist_ok=True)
pairs, answer = [], []
for k in range(PAIRS):
    got = {}
    for m in MODELS:
        comment_gen._MODEL = m
        SG._MODEL = m
        try:
            d = SG.generate_one_style(src, style, target_seconds=25, seed=f"{JOB}{k}", grounded=True)
            got[m] = (d or {}).get("script") or "(생성 실패)"
        except Exception as ex_:
            got[m] = f"(오류 {ex_!r})"
        time.sleep(3)
    order = list(MODELS); random.shuffle(order)
    pairs.append({"A": got[order[0]], "B": got[order[1]]})
    answer.append({"pair": k + 1, "A": order[0], "B": order[1]})
    print(f"pair {k+1} done")

md = [f"# 대본 A/B 눈가림 비교 — 잡 {JOB} / 소스 {vid}", "",
      "같은 소스·같은 스타일·같은 규칙. 모델만 다르다. 어느 쪽이 더 좋은 대본인지 고르고 이유를 한 줄 적는다.", ""]
for i, p in enumerate(pairs, 1):
    md += [f"## {i}번 짝", "", "**A**", "", p["A"], "", "**B**", "", p["B"], "", "선택: [ A / B ] 이유:", ""]
(out_dir / f"{JOB}.md").write_text("\n".join(md), encoding="utf-8")
(out_dir / f"{JOB}_answer.json").write_text(json.dumps(answer, ensure_ascii=False, indent=1), encoding="utf-8")
print("saved", out_dir / f"{JOB}.md")
