# 고객 키 읽기: 환경변수 → ~/.shortem/keys/<이름>. 값은 어디에도 출력하지 않는다.
import os

ENV = {"typecast": "TYPECAST_API_KEY", "pixabay": "PIXABAY_API_KEY", "gemini": "GEMINI_API_KEY", "typesafe": "TYPESAFE_API_KEY"}


def get(name):
    v = os.environ.get(ENV[name], "").strip()
    if v: return v
    p = os.path.expanduser(f"~/.shortem/keys/{name}")
    return open(p, encoding="utf-8").read().strip() if os.path.exists(p) else ""
