"""live_episode.js 가 남긴 claude.jsonl 을 사람이 읽게 — 붙은 MCP · 도구 부름·결과 앞부분 · 마지막 답.

  py test/peek_episode.py <live_ep 폴더>/claude.jsonl [줄 수]
"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
rows = []
for line in open(sys.argv[1], encoding="utf-8"):
    try:
        m = json.loads(line)
    except ValueError:
        continue
    if m.get("type") == "system" and m.get("subtype") == "init":
        rows.append("MCP " + json.dumps(m.get("mcp_servers"), ensure_ascii=False))
    if m.get("type") == "result":
        rows.append("END " + str(m.get("result") or "")[:300].replace("\n", " "))
    msg = m.get("message") if isinstance(m.get("message"), dict) else {}
    for c in msg.get("content") or []:
        if c.get("type") == "tool_use":
            rows.append("USE " + c["name"].replace("mcp__shortem__", "") + " " + json.dumps(c.get("input"), ensure_ascii=False)[:160])
        elif c.get("type") == "tool_result":
            t = c.get("content")
            t = t[0].get("text") if isinstance(t, list) and t else t
            rows.append("RES " + str(t)[:240].replace("\n", " "))
        elif c.get("type") == "text" and m.get("type") == "assistant":
            rows.append("SAY " + c["text"][:200].replace("\n", " "))
print("\n".join(rows[-n:]))
