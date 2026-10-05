"""감정짤 밈팩 — 감정별 리액션 짤 후보 영상을 유튜브에서 찾는다(쿼터 0, yt-dlp ytsearch).

    py tools/meme_pack/search.py <출력폴더> [--per 15]

출력: <출력폴더>/candidates.json  (감정 → 후보 영상 목록: id·제목·채널·길이·조회수·검색어)
짧은 영상(≤ MAX_SEC)만 남긴다 — 짤 한 개짜리 소스가 자르기 쉽고 감정이 분명하다.
"""
import argparse
import json
import os
import subprocess
import sys

# 감정 12종(2026-10-05 사장님 확정 흐름: 6→9→12) — 관제 카드 121 '됐다의 기준'과 같은 목록이다(이 파일이 감정 목록의 주인).
EMOTIONS = {
    "놀람": ["놀라는 짤 밈 소스", "깜짝 놀라는 리액션 밈", "surprised reaction meme clip", "shocked face reaction meme template"],
    "충격_입막": ["입틀막 짤 밈", "충격 받은 리액션 짤", "hand over mouth shocked reaction meme", "omg reaction meme clip"],
    "의심_황당": ["황당한 표정 짤 밈", "어이없는 리액션 짤", "confused reaction meme clip", "skeptical look reaction meme"],
    "기쁨_환호": ["환호하는 리액션 짤 밈", "기뻐서 소리지르는 짤", "cheering celebration reaction meme clip", "excited happy reaction meme template"],
    "감탄_박수": ["감탄 박수 리액션 짤", "기립박수 밈 짤", "clapping reaction meme clip", "impressed reaction meme"],
    "웃음": ["빵터지는 리액션 짤 밈", "웃참 실패 짤", "laughing reaction meme clip", "bursting out laughing meme template"],
    "슬픔": ["우는 짤 밈 리액션", "오열하는 짤 밈", "crying reaction meme clip", "sad reaction meme template"],
    "분노_짜증": ["화내는 리액션 짤 밈", "빡친 표정 짤", "angry reaction meme clip", "annoyed frustrated reaction meme"],
    "당황_멘붕": ["당황하는 짤 밈", "멘붕 리액션 짤", "awkward panic reaction meme clip", "speechless reaction meme"],
    "공포_움찔": ["무서워하는 리액션 짤 밈", "깜짝 놀라 움찔 짤", "scared reaction meme clip", "terrified flinch reaction meme"],
    "거절_절레": ["고개 절레절레 짤 밈", "싫어 안돼 리액션 짤", "no no no reaction meme clip", "shaking head nope reaction meme"],
    "끄덕_엄지": ["고개 끄덕 인정 짤 밈", "엄지척 리액션 짤", "nodding approval reaction meme clip", "thumbs up reaction meme"],
}

# 짤 사이트(GIPHY·Gifer·Tenor·GIFDB) 검색어 — 감정마다 영어 태그. 사이트별 수집기는 전부 이 표를 가져다 쓴다
# (수집기마다 검색어를 따로 적으면 감정이 사이트마다 어긋난다 — 0순위-B).
SITE_QUERIES = {
    "놀람": ["surprised reaction", "wow shocked face"],
    "충격_입막": ["gasp hand over mouth", "omg shocked reaction"],
    "의심_황당": ["confused reaction", "skeptical side eye"],
    "기쁨_환호": ["cheering excited reaction", "yes celebration happy"],
    "감탄_박수": ["clapping applause reaction", "impressed standing ovation"],
    "웃음": ["laughing hard reaction", "cant stop laughing"],
    "슬픔": ["crying reaction", "sad tears reaction"],
    "분노_짜증": ["angry reaction", "annoyed eye roll"],
    "당황_멘붕": ["awkward reaction", "facepalm speechless"],
    "공포_움찔": ["scared reaction", "terrified flinch"],
    "거절_절레": ["no shaking head reaction", "nope reaction"],
    "끄덕_엄지": ["nodding yes approval", "thumbs up reaction"],
}
# 국내(한국 방송·연예인) 짤을 찾는 한국어 검색어 — 한국어 검색이 되는 사이트(Tenor 등)에서 쓴다
SITE_QUERIES_KO = {
    # ★감정 낱말 하나("놀람")는 사이트가 번역 검색을 해 해외 짤만 준다(Tenor 실측 2026-10-05: "놀람" 한글 짤 0/50,
    #   "놀라는 짤" 31/50). 한국 사람이 실제로 치는 "~하는 짤" 꼴로 적는다.
    "놀람": ["놀라는 짤", "깜짝 놀란 짤"],
    "충격_입막": ["충격받은 짤", "입틀막 짤"],
    "의심_황당": ["황당한 짤", "어이없는 짤"],
    "기쁨_환호": ["신나는 짤", "환호하는 짤"],
    "감탄_박수": ["박수치는 짤", "감탄하는 짤"],
    "웃음": ["빵터진 짤", "웃는 짤"],
    "슬픔": ["우는 짤", "오열 짤"],
    "분노_짜증": ["화내는 짤", "짜증나는 짤"],
    "당황_멘붕": ["당황한 짤", "멘붕 짤"],
    "공포_움찔": ["무서워하는 짤", "소름 짤"],
    "거절_절레": ["절레절레 짤", "싫어하는 짤"],
    "끄덕_엄지": ["끄덕이는 짤", "엄지척 짤"],
}
MAX_SEC = 60


def ytsearch(query, n):
    cmd = ["yt-dlp", "--flat-playlist", "--no-warnings", "-J", f"ytsearch{n}:{query}"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(f"[실패] {query}: {r.stderr.strip()[:200]}", file=sys.stderr)
        return []
    return json.loads(r.stdout).get("entries") or []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--per", type=int, default=15)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    # 이미 찾아둔 감정은 다시 검색하지 않는다 — 검색 결과가 날마다 달라 후보가 바뀌면 고른 것(state.json)과 어긋난다
    path = os.path.join(a.out_dir, "candidates.json")
    old = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    result, seen = {}, {r["id"] for rows in old.values() for r in rows}
    for emo, queries in EMOTIONS.items():
        if old.get(emo):
            result[emo] = old[emo]
            print(f"{emo}: {len(old[emo])}편 (기존)")
            continue
        rows = []
        for q in queries:
            for e in ytsearch(q, a.per):
                vid, dur = e.get("id"), e.get("duration")
                if not vid or vid in seen or not dur or dur > MAX_SEC:
                    continue
                seen.add(vid)
                rows.append({"id": vid, "title": e.get("title"), "channel": e.get("channel"),
                             "duration": dur, "views": e.get("view_count") or 0, "query": q})
        rows.sort(key=lambda x: -x["views"])
        result[emo] = rows
        print(f"{emo}: {len(rows)}편")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
