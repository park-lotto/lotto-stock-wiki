# -*- coding: utf-8 -*-
"""클로드형 테스트가 진짜로 잡는지(관제 234) — 판단 코드를 일부러 망가뜨려 해당 테스트가 **실패**하는지 본다(끝나면 원복).

0순위-A1c "고치기 전 코드에서 그 검사가 실패하는지 먼저 시험한다" 의 도구판. ★못 잡음 이 하나라도 나오면 그 테스트는 아무것도 안 잰다.

    py tools/claude_portal/mutation_check.py
"""
import subprocess
import sys
from pathlib import Path

TRACK = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
P = TRACK / "shopping_shorts" / "claude_portal.py"
T = "shopping_shorts/tests/test_claude_portal.py"
# (이름, 원래 코드, 망가뜨린 코드, 잡아야 할 테스트)
MUT = [
    ("참조 안 하는 글꼴까지", 'refs = [f"font:{f}" for f in channel_profile.fonts_of(merged.get("frame"))]',
     'refs = [r["id"] for r in _assets(store, "font")]', "test_assets_자산수_참조수_같고_blob_sha_일치"),
    ("견본 Range 허용", '    if rng and rng != "bytes=0-":\n        bad = "range"', '    if False:\n        bad = "range"',
     "test_견본_Range_403_토큰없으면_거절"),
    ("다른 기기 lease 허용", '            elif cur:\n                busy = cur', '            elif False:\n                busy = cur',
     "test_lease_두기기_동시면_두번째_409_TTL뒤_성공"),
    ("기기 제한 없음", "elif len(live) < DEVICES_MAX:", "elif True:", "test_기기_3대째_거절"),
    ("A1 정지 안 함", '                    _hit_suspend("A1", t["suspend_sec"], detail, prior + 1)', "                    pass",
     "test_A1_키공유_국가2_경고_다음엔_정지"),
    ("pack 목록 무시", 'a = _row(c, "SELECT * FROM claude_assets WHERE id=?", (str(asset_id),)) if hit else None',
     'a = _row(c, "SELECT * FROM claude_assets WHERE id=?", (str(asset_id),))', "test_목록밖_pack_거절_extra는_허용풀만"),
    ("페이지에 path 노출", '"date": r.get("date"), "preview": _pv("result", r.get("n"))}',
     '"date": r.get("date"), "preview": _pv("result", r.get("n")), "path": r.get("path")}', "test_페이지_응답에_금지키_원본URL_0개"),
    ("옛 kv 키 통과", 'if (not row or row["kv"] != kv or',
     'if (not row or False or', "test_라이선스_위조_만료_재발급"),
]


def main():
    orig = P.read_bytes()
    missed = 0
    try:
        for name, old, new, test in MUT:
            s = orig.decode("utf-8")
            if s.count(old) != 1:
                print(f"{name:16s} → ★망가뜨릴 자리를 못 찾음(코드가 바뀌었다 — 이 도구를 고쳐라)")
                missed += 1
                continue
            if name == "옛 kv 키 통과":
                s = s.replace(old, new).replace('or int(row["gkv"] or 0) != _gkv(store) or row["revoked"]):', "or False):", 1)
                s = s.replace('or not hmac.compare_digest(row["key_hash"] or "", _key_hash(key.strip()))', "", 1)
            else:
                s = s.replace(old, new)
            P.write_bytes(s.encode("utf-8"))
            r = subprocess.run([sys.executable, "-m", "pytest", f"{T}::{test}", "-q", "-p", "no:cacheprovider", "-W", "ignore"],
                               cwd=TRACK, capture_output=True, text=True, encoding="utf-8", errors="replace")
            caught = r.returncode != 0
            missed += 0 if caught else 1
            print(f"{name:16s} → {'잡음(실패)' if caught else '★못 잡음(통과)'}  {test}")
    finally:
        P.write_bytes(orig)
    print("원복:", P.read_bytes() == orig, "| 못 잡음", missed)
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
