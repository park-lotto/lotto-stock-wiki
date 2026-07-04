"""
smoke_test_key_vault.py — 18개 Gemini 키가 전부 실제로 인증되는지 1콜씩 확인.
사용법: python scripts/smoke_test_key_vault.py
"""
import sys
import time
sys.path.insert(0, ".")
from pipeline.atoms import key_vault

GROUPS = ["general", "ingest", "embed", "briefing"]


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
        return f"FAIL: {str(e)[:100]}"


def main():
    total = 0
    failures = []
    for group in GROUPS:
        keys = key_vault.get_keys(group)
        print(f"\n[{group}] {len(keys)}개 키")
        for i, key in enumerate(keys):
            total += 1
            result = check_key(group, i, key)
            print(f"  #{i+1}: {result}")
            if result != "OK":
                failures.append(f"{group}#{i+1}: {result}")
            time.sleep(1)  # 연속 호출로 인한 자체 RPM 유발 방지

    print(f"\n총 {total}개 키 확인, 실패 {len(failures)}개")
    for f in failures:
        print(f"  - {f}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
