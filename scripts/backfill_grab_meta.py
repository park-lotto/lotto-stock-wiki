#!/usr/bin/env python3
"""담기 때 '다른 영상 얼굴'로 저장된 행을 URL 기준 실제 값으로 바로잡는다.

왜(2026-09-01 실사고): 유튜브 쇼츠는 SPA라 스크롤로 다음 영상에 가도 og:image·
og:title이 처음 로드한 영상 것으로 남는다 → 주소는 A인데 제목·썸네일은 B로 저장됐다.
사장님이 즐겨찾기에서 A를 못 찾고 다시 담자 "이미 담겨 있어요"만 떴다.

주소는 항상 정확하므로(location.href는 스크롤 따라 제대로 바뀐다) URL로 다시
조회한 값이 진실이다. 판정은 app._grab_meta_is_stale 한 곳에서만 한다(0순위-B).

    python3 -m scripts.backfill_grab_meta            # 미리보기(아무것도 안 고침)
    python3 -m scripts.backfill_grab_meta --apply    # 실제 반영
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from shopping_shorts.app import DB_PATH, _grab_meta_is_stale
from shopping_shorts.media_download import probe_grab_meta
from shopping_shorts.store import Store


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="실제로 고친다(없으면 미리보기)")
    args = ap.parse_args()

    store = Store(DB_PATH)
    with store._conn() as c:
        rows = c.execute(
            "SELECT customer_id, shortcode, url, COALESCE(name,''), COALESCE(thumbnail,'') "
            "FROM mix_basket").fetchall()

    targets = [(cid, sc, url, name, th) for cid, sc, url, name, th in rows
               if _grab_meta_is_stale(url, th)]
    print(f"전체 {len(rows)}행 / 얼굴 어긋남 {len(targets)}행")
    if not targets:
        return

    fixed = failed = 0
    for cid, sc, url, name, th in targets:
        meta = probe_grab_meta(url)
        title, thumb = meta.get("title"), meta.get("thumbnail")
        if not title and not thumb:
            # ★조용히 넘기지 않는다 — 못 고친 건 못 고쳤다고 보여야 다음에 다시 볼 수 있다.
            print(f"  [실패] cid={cid} {sc} 조회 불가 url={url}")
            failed += 1
            continue
        print(f"  cid={cid} {sc}")
        print(f"    전: {name[:40]}")
        print(f"    후: {(title or '')[:40]}")
        if args.apply:
            store.mix_basket_set_meta(sc, customer_id=cid, thumbnail=thumb,
                                      name=title, overwrite=True)
        fixed += 1

    print(f"\n{'반영' if args.apply else '미리보기'}: 고침 {fixed} / 실패 {failed}")
    if not args.apply:
        print("실제로 반영하려면 --apply 를 붙여라.")


if __name__ == "__main__":
    main()
