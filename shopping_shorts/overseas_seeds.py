"""카테고리 → {서브레딧, 시드계정} 시드팩 로더. JSON에서 관리(코드수정 없이 추가)."""
import json
import os

_PATH = os.path.join(os.path.dirname(__file__), "overseas_seeds.json")


def load_seeds():
    with open(_PATH, encoding="utf-8") as f:
        return json.load(f)


# JSON 키에서 파생 — 시드 카테고리를 바꿔도 코드 수정 없이 동기 유지(드리프트 방지).
CATEGORIES = list(load_seeds().keys())
