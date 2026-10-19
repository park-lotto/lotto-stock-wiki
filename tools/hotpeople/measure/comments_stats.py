# -*- coding: utf-8 -*-
"""댓글 실측 — yt-dlp --write-comments 결과(*.info.json)에서: 편당 댓글 수·좋아요 상위 댓글·물음표 비율·
자막 문장 인용(subs.json이 있으면 어느 자막이 댓글에 되풀이되나)·상위 단어.
사용: PYTHONUTF8=1 py comments_stats.py <comments 폴더> [subs.json] → comments_stats.json + 콘솔
"""
import json, glob, os, sys, re, collections as C

D = sys.argv[1]; subs = json.load(open(sys.argv[2], encoding="utf-8")) if len(sys.argv) > 2 else {}
out = {}; allw = C.Counter()
for f in sorted(glob.glob(os.path.join(D, "*.info.json"))):
    j = json.load(open(f, encoding="utf-8")); cs = j.get("comments") or []
    vid = j["id"]; texts = [c.get("text", "") for c in cs]
    top = sorted(cs, key=lambda c: -(c.get("like_count") or 0))[:3]
    q = sum(1 for t in texts if "?" in t)
    quoted = []
    if vid in subs:
        for s in subs[vid]["subs"]:
            key = re.sub(r"[\s/\"'“”‘’.,…!?]", "", s.get("text", ""))[:8]
            if len(key) >= 4:
                n = sum(1 for t in texts if key in re.sub(r"\s", "", t))
                if n: quoted.append((s["n"], n))
    for t in texts: allw.update(re.findall(r"[가-힣]{2,}", t))
    out[vid] = {"title": j.get("title"), "views": j.get("view_count"), "n_comments": j.get("comment_count"), "fetched": len(cs),
                "question_pct": round(100 * q / len(texts)) if texts else None,
                "top3": [(c.get("like_count"), (c.get("text") or "")[:60]) for c in top], "quoted_subs": quoted}
json.dump(out, open("comments_stats.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for vid, o in sorted(out.items(), key=lambda kv: -(kv[1]["views"] or 0))[:12]:
    print(f"{o['views']:>9,} 댓글 {o['n_comments']} 물음표 {o['question_pct']}% 인용자막 {o['quoted_subs']} | {o['top3'][0] if o['top3'] else ''}")
print("댓글 단어 상위 30:", allw.most_common(30))
