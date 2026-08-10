# -*- coding: utf-8 -*-
"""로컬 reference.db에 실제 생성된 대본이 있는지 확인 (있으면 몇 개, 최근 것 미리보기)."""
import io
import json
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DB = r"C:\Users\CH\Desktop\로또의 주식\shopping_shorts\data\reference.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row


def count(sql, *a):
    try:
        return con.execute(sql, a).fetchone()[0]
    except Exception as e:
        return f"ERR {e}"


print("[mix_jobs 총]", count("SELECT COUNT(*) FROM mix_jobs"))
print("[edit_plan 있는 job]", count(
    "SELECT COUNT(*) FROM mix_jobs WHERE edit_plan_json IS NOT NULL AND edit_plan_json != ''"))
print("[produce_works]", count("SELECT COUNT(*) FROM produce_works"))
print("[script_drafts]", count("SELECT COUNT(*) FROM script_drafts"))
print("[script_wiki]", count("SELECT COUNT(*) FROM script_wiki"))
print("[pattern_item approved]", count(
    "SELECT COUNT(*) FROM pattern_item WHERE status='approved' AND is_negative=0"))

print("\n--- 최근 edit_plan 대본 미리보기(최대 3개) ---")
try:
    rows = con.execute(
        "SELECT job_id, edit_plan_json FROM mix_jobs "
        "WHERE edit_plan_json IS NOT NULL AND edit_plan_json != '' "
        "ORDER BY rowid DESC LIMIT 3").fetchall()
    for r in rows:
        plan = json.loads(r["edit_plan_json"])
        beats = plan.get("beats", [])
        text = " ".join((b.get("narration") or "") for b in beats)
        print(f"\n[{r['job_id']}] 비트{len(beats)}개 / {len(text)}자")
        print(f"  {text[:300]}")
except Exception as e:
    print("ERR", e)

print("\n--- script_wiki (담아둔 S급 참고대본) 최근 3개 ---")
try:
    rows = con.execute(
        "SELECT full_text FROM script_wiki ORDER BY rowid DESC LIMIT 3").fetchall()
    for r in rows:
        t = (r["full_text"] or "")[:250]
        print(f"\n  {t}")
except Exception as e:
    print("ERR", e)

print("\n--- pattern_item: 어미(ending) 버킷 승인분 ---")
try:
    rows = con.execute(
        "SELECT text, freq FROM pattern_item WHERE bucket='ending' "
        "ORDER BY freq DESC LIMIT 40").fetchall()
    print(f"  총 {len(rows)}개: " + " / ".join(f"{r['text']}({r['freq']})" for r in rows))
except Exception as e:
    print("ERR", e)
