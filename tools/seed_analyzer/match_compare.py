# -*- coding: utf-8 -*-
"""장면 매칭 모델 비교 — 같은 대본 8줄 + 컷 목록을 여러 모델(Vertex Gemini · Claude)에 주고 줄마다 고른 컷을 나란히 (2026-09-22).
  py tools/seed_analyzer/match_compare.py --input <match_input.json> --out <html> [--models gemini-3.1-flash-lite,gemini-3.5-flash,gemini-3.6-flash,claude-sonnet-5,claude-opus-5]
입력 JSON은 서버에서 뽑는다(lines·seg_index·backbone_vid). 프롬프트·스키마는 shopping_shorts/ai_match.py 것을 그대로 쓴다(0순위-B).
"""
import argparse, html, json, os, re, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
PROJECT = "project-74eaf695-8229-44a1-876"


def build_prompt(lines, seg_index, backbone_vid):
    from shopping_shorts import ai_match as am
    from shopping_shorts.backbone_assemble import _secs
    order = sorted(seg_index, key=lambda s: (seg_index[s].get("vid") or "", s))
    lb = "\n".join("  %d. [%s] (%.1f초) %s" % (i + 1, L.get("role") or "", _secs(L["text"]), L["text"]) for i, L in enumerate(lines))
    return "%s\n\n[대본]\n%s\n\n[컷 목록] 번호 | 영상 | 길이 | [역할] 화면\n%s" % (am.BRIEF, lb, am._cut_block(seg_index, backbone_vid, order)), am.SCHEMA


def call_gemini(client, model, prompt, schema):
    from google.genai import types
    r = client.models.generate_content(model=model, contents=prompt,
                                       config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema))
    return json.loads(r.text)


def call_claude(model, prompt, schema):
    """Vertex의 Claude → 실패하면 이 PC의 claude CLI(Max)로."""
    txt = None
    try:
        from anthropic import AnthropicVertex
        for region in ("global", "us-east5", "asia-northeast1"):
            try:
                c = AnthropicVertex(project_id=PROJECT, region=region)
                m = c.messages.create(model=model, max_tokens=2000, messages=[{"role": "user", "content": prompt + "\n\nJSON만 답하라. 스키마: " + json.dumps(schema, ensure_ascii=False)}])
                txt = m.content[0].text; break
            except Exception as e:      # noqa: BLE001
                last = repr(e)[:160]
        if txt is None:
            print("  vertex claude 실패:", last, file=sys.stderr)
    except Exception as e:              # noqa: BLE001
        print("  anthropic sdk 없음:", repr(e)[:100], file=sys.stderr)
    if txt is None:
        import subprocess
        cli_model = "opus" if "opus" in model else "sonnet"
        # ★프롬프트는 표준입력으로 — 명령 인자로 넘기면 길이에 잘려 빈 답이 온다(실측 2026-09-22: 두 모델 다 0줄)
        # ★프로젝트 폴더에서 부르면 CLAUDE.md·훅이 붙어 "JSON을 전달했습니다" 같은 요약만 돌아온다(실측) → 빈 임시 폴더에서 부른다
        import tempfile
        neutral = tempfile.mkdtemp(prefix="claude_match_")
        p = subprocess.run(["claude", "-p", "--model", cli_model, "--output-format", "text"],
                           input=prompt + "\n\n답은 오직 JSON 객체 하나. 앞뒤 설명·마크다운 금지. 스키마: " + json.dumps(schema, ensure_ascii=False),
                           capture_output=True, text=True, encoding="utf-8", timeout=420, cwd=neutral)
        txt = p.stdout
        if not (txt or "").strip():
            print("  claude CLI 빈 답:", (p.stderr or "")[:200], file=sys.stderr)
    m = re.search(r"\{.*\}", txt or "", re.S)
    return json.loads(m.group(0)) if m else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--models", default="gemini-3.1-flash-lite,gemini-3.5-flash,gemini-3.6-flash,claude-sonnet-5,claude-opus-5")
    ap.add_argument("--from-picks", default="", help="이미 받은 picks.json으로 표만 다시(모델 호출 0회)")
    a = ap.parse_args()
    d = json.load(open(a.input, encoding="utf-8"))
    lines, idx, bb = d["lines"], d["seg_index"], d["backbone_vid"]
    prompt, schema = build_prompt(lines, idx, bb)
    results = {}
    if a.from_picks:
        for m, r in json.load(open(a.from_picks, encoding="utf-8")).items():
            results[m] = {"picks": {int(k): tuple(v) for k, v in r["picks"].items()}, "sec": r.get("sec", 0), "error": None}
    from google import genai
    gclient = genai.Client(vertexai=True, project=PROJECT, location="global") if not a.from_picks else None
    todo = [x.strip() for x in a.models.split(",") if x.strip()]
    if a.from_picks:
        todo = todo if a.models != ap.get_default("models") else []   # --models를 명시하면 그 모델은 다시 부른다(덮어씀)
    for model in todo:
        if gclient is None and not model.startswith("claude"):
            gclient = genai.Client(vertexai=True, project=PROJECT, location="global")
        t0 = time.time()
        try:
            out = call_claude(model, prompt, schema) if model.startswith("claude") else call_gemini(gclient, model, prompt, schema)
        except Exception as e:          # noqa: BLE001
            out = {"error": repr(e)[:200]}
        picks = {}
        for p in (out.get("picks") or []):
            try:
                picks[int(p.get("line")) - 1] = ([str(c) for c in (p.get("cuts") or [])], p.get("why") or "")
            except Exception:           # noqa: BLE001
                pass
        results[model] = {"picks": picks, "sec": round(time.time() - t0, 1), "error": out.get("error")}
        print("%-24s %5.1f초 %s" % (model, results[model]["sec"], out.get("error") or ("줄 %d개 응답" % len(picks))))
    if results:
        json.dump({m: {"picks": {str(k): v for k, v in r["picks"].items()}, "sec": r["sec"]} for m, r in results.items()},
                  open(os.path.splitext(a.out)[0] + ".picks.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    clipdir = os.path.join(os.path.dirname(os.path.abspath(a.out)), "clips")
    def clip_tag(c):
        f = os.path.join(clipdir, c + ".mp4")
        return "<video src=clips/%s.mp4 muted autoplay loop playsinline style='height:170px;border-radius:4px;background:#000'></video><br>" % html.escape(c) if os.path.exists(f) else ""
    H = ["<meta charset=utf-8><style>body{font-family:sans-serif;font-size:13px;max-width:1600px;margin:16px auto}table{border-collapse:collapse;width:100%}"
         "td,th{border:1px solid #ccc;padding:6px;vertical-align:top}th{background:#f3f3f3}.bad{color:#c00}.why{color:#777;font-size:11px}.role{color:#36c;font-size:11px}</style>",
         "<h2>장면 매칭 모델 비교 · 같은 대본 8줄 · 컷 %d개</h2><table><tr><th style='width:260px'>대본</th>%s</tr>" % (
             len(idx), "".join("<th>%s<br><span class=why>%.0f초</span></th>" % (html.escape(m), r["sec"]) for m, r in results.items()))]
    for i, L in enumerate(lines):
        H.append("<tr><td><span class=role>%d. %s</span><br>%s</td>" % (i + 1, L["role"], html.escape(L["text"])))
        for m, r in results.items():
            cuts, why = r["picks"].get(i, ([], ""))
            cells = []
            for c in cuts:
                v = idx.get(c)
                cells.append("<span class=bad>%s (없는 컷)</span>" % html.escape(c) if not v else
                             clip_tag(c) + "<b>%s</b> [%s] %s <span class=why>%.1f초</span>" % (html.escape(v.get("vid") or ""), html.escape(v.get("role") or ""), html.escape((v.get("desc") or "")[:48]), v.get("secs", 0)))
            H.append("<td>%s<div class=why>%s</div></td>" % ("<br>".join(cells) or ("<span class=bad>%s</span>" % html.escape(r.get("error") or "빈 답")), html.escape(why)))
        H.append("</tr>")
    H.append("</table>")
    open(a.out, "w", encoding="utf-8").write("\n".join(H))
    print("HTML:", a.out)


if __name__ == "__main__":
    main()
