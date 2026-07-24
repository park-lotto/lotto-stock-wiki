"""카테고리 → {서브레딧, 시드계정} 시드팩 로더. JSON에서 관리(코드수정 없이 추가)."""
import json
import os

_PATH = os.path.join(os.path.dirname(__file__), "overseas_seeds.json")


def load_seeds():
    with open(_PATH, encoding="utf-8") as f:
        return json.load(f)


CATEGORIES = ["주방/레시피", "살림/생활꿀템", "인테리어", "자취템", "가전템", "뷰티"]
