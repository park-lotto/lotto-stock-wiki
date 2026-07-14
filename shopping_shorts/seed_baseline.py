"""레퍼런스 랭킹 상위 N개를 분석해 학습 카테고리 통계 기본값을 깐다(2026-07-14).

위키 저장 없이 script_extracts만 채워 daily_batch.recompute_element_stats()가
학습 표본으로 쓰게 한다(대본위키 학습소재선택기 설계 결정 #1: 표본 = 위키뿐 아니라
대본추출 전체). 반복 실행해도 이미 구조분석된 항목은 건너뛴다."""
import hashlib
import sys
from pathlib import Path

from shopping_shorts import daily_batch
from shopping_shorts.config import DB_PATH
from shopping_shorts.frame_extract import download_video
from shopping_shorts.script_extract import extract_script
from shopping_shorts.structure_analyze import analyze_structure
from shopping_shorts.store import Store

_TMP_DIR = Path(__file__).parent / "data" / "seed_tmp"


def seed(n=30, db_path=DB_PATH):
    store = Store(db_path)
    items, _ = store.load_last_run()
    items = sorted(items, key=lambda i: i.get("score", 0), reverse=True)[:n]

    ok = skipped = failed = 0
    for idx, it in enumerate(items, 1):
        code = it["shortcode"]
        category = it.get("category")
        try:
            existing = store.get_extract(code)
            if existing and existing.get("structure"):
                skipped += 1
                continue
            script = store.get_script(code)
            if not script:
                video_url = it.get("video_url")
                if not video_url:
                    failed += 1
                    print(f"[{idx}/{len(items)}] 실패(video_url 없음) {code}")
                    continue
                work_dir = _TMP_DIR / hashlib.sha1(code.encode()).hexdigest()[:16]
                video_path = download_video(video_url, work_dir)
                script = extract_script(video_path, code, caption=it.get("caption", ""))
                if not script.get("full_text") and not script.get("segments"):
                    failed += 1
                    print(f"[{idx}/{len(items)}] 실패(추출빈결과) {code}")
                    continue
                store.save_script(code, script, category=category)
            structure = analyze_structure(script.get("full_text", ""))
            store.save_extract_structure(code, structure)
            ok += 1
            print(f"[{idx}/{len(items)}] 완료 · {category} · {code}")
        except Exception as e:
            failed += 1
            print(f"[{idx}/{len(items)}] 실패 {code}: {e}")

    saved = daily_batch.recompute_element_stats(store)
    print(f"시드 완료 — 성공 {ok} / 스킵(이미분석) {skipped} / 실패 {failed} · 카테고리×요소 통계 {saved}건 재계산")


if __name__ == "__main__":
    n_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    seed(n_arg)
