# -*- coding: utf-8 -*-
"""채널 전수조사 결과(JSON 폴더)를 DB의 channel_survey 표에 넣는다(관제 137) — '채널별 터진 영상' 탭의 재료.

    서버:  python3 tools/channel_hits/load_survey.py /home/ubuntu/survey134/out
    (환경파일을 실은 셸에서. DB 는 shopping_shorts.config.DB_PATH — 앱이 읽는 그 DB)

조사 JSON 은 tools/channel_hits/survey.py 가 만든다(채널마다 <채널ID>.json: {cid, videos:[{id,title,at,secs,views,…}]}).
채널마다 통째로 갈아 끼우므로 몇 번을 돌려도 같다. 끝에 탭에 실제로 나올 편수를 찍는다.
"""
import collections
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from shopping_shorts.config import DB_PATH  # noqa: E402
from shopping_shorts.store import Store  # noqa: E402


def main(folder, db_path=None):
    st = Store(db_path or DB_PATH)
    files = sorted(glob.glob(os.path.join(folder, "UC*.json")))
    n_ch = n_v = 0
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        n = st.save_channel_survey(d.get("cid") or os.path.basename(f)[:-5], d.get("videos") or [], surveyed_at=d.get("at") or "")
        n_ch += 1
        n_v += n
    items = st.channel_hit_items()
    by = collections.Counter(i["category"] for i in items)
    print("넣음: 채널 %d · 쇼츠 %d편 → 탭에 나올 터진 영상 %d편 / %d채널 (%s)" % (
        n_ch, n_v, len(items), len({i["username"] for i in items}), ", ".join("%s %d" % kv for kv in by.most_common())))
    return 0 if files else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("사용: python3 tools/channel_hits/load_survey.py <조사 JSON 폴더> [DB 경로]")
    sys.exit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
