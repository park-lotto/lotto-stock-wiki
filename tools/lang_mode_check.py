# -*- coding: utf-8 -*-
"""영어모드 변환 격리 시험(관제 029) — 실제 작업 대본을 실제 AI로 번역해 계약을 잰다.

사용:
  py tools/lang_mode_check.py sample.json            # [{job_id, lines:[...]}, ...]
  py tools/lang_mode_check.py --from-server 10       # 라이브 DB에서 최근 완료 작업 10편을 읽어(읽기 전용) 시험

잰다(카드 029 '됐다의 기준'): 줄 수 = 원문 줄 수 · 영어 비율 ≥ 95% · 한글 잔존 0 · 실패 0.
결과는 out/lang_mode_check_<시각>.json 에 남긴다(문장 원문·번역 전부).
"""
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from shopping_shorts import script_translate  # noqa: E402

_KEY = "C:/Users/TheRose/crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem"
_HOST = "ubuntu@shoppingshorts.duckdns.org"
_REMOTE = r'''cd /home/ubuntu/lotto-stock-wiki/shopping_shorts && python3 - <<"EOF"
import sqlite3, json
c = sqlite3.connect("data/reference.db"); c.row_factory = sqlite3.Row
out = []
for r in c.execute("SELECT job_id, edit_plan_json FROM mix_jobs WHERE status IN ('done','ready_for_review') AND edit_plan_json IS NOT NULL ORDER BY updated_at DESC LIMIT %d"):
    try:
        beats = (json.loads(r["edit_plan_json"]) or {}).get("beats") or []
    except Exception:
        continue
    lines = [b.get("narration") for b in beats if isinstance(b, dict) and (b.get("narration") or "").strip()]
    if len(lines) >= 3:
        out.append({"job_id": r["job_id"], "lines": lines})
print(json.dumps(out, ensure_ascii=False))
EOF'''


def from_server(n):
    cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=15", "-i", _KEY, _HOST, _REMOTE % n]
    raw = subprocess.check_output(cmd, timeout=120).decode("utf-8", "replace")
    return json.loads(raw.strip().splitlines()[-1])


def run(samples):
    rows, ok_all = [], True
    for s in samples:
        lines = s["lines"]
        t0 = time.time()
        try:
            out = script_translate.to_english(lines)
            err = ""
        except Exception as e:  # noqa: BLE001 — 시험은 실패도 결과다
            out, err = [], repr(e)[:200]
        ratio = script_translate.english_ratio(out) if out else 0.0
        passed = (not err) and len(out) == len(lines) and ratio >= 0.95
        ok_all = ok_all and passed
        rows.append({"job_id": s.get("job_id"), "n": len(lines), "n_out": len(out), "en_ratio": round(ratio, 3),
                     "sec": round(time.time() - t0, 1), "error": err, "pass": passed,
                     "ko": lines, "en": out})
        print("%s %-14s 줄 %2d→%2d 영어 %.0f%% %4.1fs %s" % ("✅" if passed else "❌", s.get("job_id"), len(lines), len(out), ratio * 100,
                                                          time.time() - t0, err))
    return ok_all, rows


def main():
    args = sys.argv[1:]
    if args and args[0] == "--from-server":
        samples = from_server(int(args[1]) if len(args) > 1 else 10)
    elif args:
        samples = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    else:
        print(__doc__); return 2
    ok, rows = run(samples)
    outp = ROOT / "out" / ("lang_mode_check_%s.json" % time.strftime("%Y%m%d_%H%M%S"))
    outp.parent.mkdir(exist_ok=True)
    outp.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("== %d편 중 통과 %d · 결과 %s" % (len(rows), sum(1 for r in rows if r["pass"]), outp))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
