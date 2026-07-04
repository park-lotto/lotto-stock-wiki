"""
smoke_test_key_vault.py — 18개 Gemini 키가 전부 실제로 인증되는지 1콜씩 확인.
사용법: python scripts/smoke_test_key_vault.py
"""
import sys
import time
sys.path.insert(0, ".")
from pipeline.atoms import key_vault

GROUPS = ["general", "ingest", "embed", "briefing"]


AUTH_FAIL_MARKERS = ("API_KEY_INVALID", "PERMISSION_DENIED", "400", "403")
RATE_LIMITED_MARKERS = ("429", "RESOURCE_EXHAUSTED")


def check_key(group: str, idx: int, key: str) -> str:
    client = key_vault.get_client_for_key(key)
    try:
        if group == "embed":
            resp = client.models.embed_content(model="gemini-embedding-001", contents="ping")
            ok = bool(resp.embeddings and resp.embeddings[0].values)
        else:
            resp = client.models.generate_content(model="gemini-3.1-flash-lite", contents="ping")
            ok = bool((resp.text or "").strip())
        return "OK" if ok else "빈 응답"
    except Exception as e:
        msg = str(e)[:100]
        if any(marker in msg for marker in AUTH_FAIL_MARKERS):
            return f"AUTH_FAIL: {msg}"
        if any(marker in msg for marker in RATE_LIMITED_MARKERS):
            return f"RATE_LIMITED: {msg}"
        return f"OTHER_FAIL: {msg}"


def main():
    total = 0
    ok_count = 0
    rate_limited = []
    real_failures = []
    for group in GROUPS:
        keys = key_vault.get_keys(group)
        print(f"\n[{group}] {len(keys)}개 키")
        for i, key in enumerate(keys):
            total += 1
            result = check_key(group, i, key)
            print(f"  #{i+1}: {result}")
            if result == "OK":
                ok_count += 1
            elif result.startswith("RATE_LIMITED"):
                rate_limited.append(f"{group}#{i+1}: {result}")
            else:
                # AUTH_FAIL, OTHER_FAIL, or unexpected non-OK result (e.g. "빈 응답")
                real_failures.append(f"{group}#{i+1}: {result}")
            time.sleep(1)  # 연속 호출로 인한 자체 RPM 유발 방지

    print(
        f"\n총 {total}개 키 확인: OK {ok_count}개, "
        f"RATE_LIMITED {len(rate_limited)}개, 실패 {len(real_failures)}개"
    )
    if rate_limited:
        print("  [RATE_LIMITED - 키 자체는 정상, 일시적 쿼터 초과]")
        for f in rate_limited:
            print(f"  - {f}")
    if real_failures:
        print("  [실패 - 실제 키 문제 가능성]")
        for f in real_failures:
            print(f"  - {f}")
    return 1 if real_failures else 0


if __name__ == "__main__":
    sys.exit(main())
