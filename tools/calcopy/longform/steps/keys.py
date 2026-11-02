# 고객 키 읽기: 환경변수 → 꾸러미 data/keys → ~/.shortem/keys. 값은 출력하지 않는다.
import os

ENV = {"typecast": "TYPECAST_API_KEY", "pixabay": "PIXABAY_API_KEY", "gemini": "GEMINI_API_KEY", "typesafe": "TYPESAFE_API_KEY"}


def get(name):
    v = os.environ.get(ENV[name], "").strip()
    if v: return v
    for d in (os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "keys"), os.path.expanduser("~/.shortem/keys")):
        p = os.path.join(d, name)
        if os.path.exists(p): return open(p, encoding="utf-8").read().strip()
    return ""
