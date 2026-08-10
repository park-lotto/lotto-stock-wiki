# -*- coding: utf-8 -*-
"""서버에서 실행 — 최근 생성된 우리 대본을 JSON으로 뽑는다(읽기 전용).
용도: 어미·문장연결 개선을 위한 before 샘플 확보. 서버 파일 수정 없음.
"""
import json
import sqlite3

DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

out = {"mix": [], "wiki": [], "endings": []}

try:
    rows = con.execute(
        "SELECT job_id, edit_plan_json FROM mix_jobs "
        "WHERE edit_plan_json IS NOT NULL AND edit_plan_json != '' "
        "ORDER BY rowid DESC LIMIT 40").fetchall()
    for r in rows:
        try:
            beats = json.loads(r["edit_plan_json"]).get("beats", [])
        except Exception:
            continue
        items = [{"role": b.get("role", ""), "narration": b.get("narration", "")}
                 for b in beats if (b.get("narration") or "").strip()]
        if items:
            out["mix"].append({"job_id": r["job_id"], "beats": items})
except Exception as e:
    out["mix_err"] = str(e)

try:
    rows = con.execute(
        "SELECT full_text FROM script_wiki WHERE full_text IS NOT NULL "
        "ORDER BY rowid DESC LIMIT 25").fetchall()
    out["wiki"] = [r["full_text"] for r in rows if (r["full_text"] or "").strip()]
except Exception as e:
    out["wiki_err"] = str(e)

try:
    rows = con.execute(
        "SELECT text, freq, status FROM pattern_item WHERE bucket='ending' "
        "ORDER BY freq DESC LIMIT 80").fetchall()
    out["endings"] = [{"text": r["text"], "freq": r["freq"], "status": r["status"]}
                      for r in rows]
except Exception as e:
    out["endings_err"] = str(e)

print(json.dumps(out, ensure_ascii=False))
