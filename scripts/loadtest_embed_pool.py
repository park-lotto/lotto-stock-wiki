"""
loadtest_embed_pool.py — 2026-07-01 실측 피크(1,171건)에 준하는 임베딩 부하를
EMBED 풀(6키)에 실제로 흘려서 "전체 소진" 없이 버티는지, 실제 소요 시간이
07:00 단일 배치 실행 시간 안에 들어오는지 확인한다.

사용법: python scripts/loadtest_embed_pool.py --n 1200
"""
import argparse
import sys
import time
sys.path.insert(0, ".")
from pipeline.atoms import key_vault
from pipeline.atoms.vector_db import embed_text

# Windows 콘솔/파이프의 기본 코드페이지(cp949)는 ✅/⚠️ 이모지를 인코딩하지
# 못해 마지막 출력 줄에서 UnicodeEncodeError로 죽는다. UTF-8로 강제한다.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1200, help="오늘 피크(1,171)보다 약간 많게 기본값 설정")
    args = ap.parse_args()

    live_before = key_vault.get_live_keys("embed")
    print(f"시작 시점 살아있는 embed 키: {len(live_before)}/{len(key_vault.get_keys('embed'))}")

    start = time.monotonic()
    failures = 0
    for i in range(args.n):
        try:
            embed_text(f"부하테스트 텍스트 {i} — 반도체 업황 개선 관련 더미 문장.")
        except RuntimeError as e:
            failures += 1
            print(f"  [{i}] 실패: {e}")
        if (i + 1) % 100 == 0:
            elapsed = time.monotonic() - start
            print(f"  {i+1}/{args.n} 처리, 경과 {elapsed:.1f}s")

    elapsed = time.monotonic() - start
    live_after = key_vault.get_live_keys("embed")
    print(f"\n총 {args.n}건, 실패 {failures}건, 소요 {elapsed:.1f}s ({elapsed/60:.1f}분)")
    print(f"종료 시점 살아있는 embed 키: {len(live_after)}/{len(key_vault.get_keys('embed'))}")
    if failures:
        print("⚠️ 일부 실패 발생 — embed 풀이 오늘 피크 물량을 완전히 커버하지 못함")
        return 1
    print("✅ 전체 소진 없이 완료 — embed 풀이 오늘 피크 물량을 커버함")
    return 0


if __name__ == "__main__":
    sys.exit(main())
