# -*- coding: utf-8 -*-
"""숏템 공용 제미나이 키(사장님 키 + 회원 공용 풀)를 서버에서 받아 이 PC 의 .env 에 넣는다.

왜: 칼카피 엔진(engine/gemini_keys.py)은 .env·환경변수만 본다. 회원 키는 서버 DB(암호화)에만 있어
    PC 를 옮기면(집 CH ↔ 회사 TheRose) 키가 3개로 줄어 무료 한도가 금방 바닥난다(2026-10-16 회사 PC 실측 3개).
    풀 고르기 규칙은 서버 store.get_pooled_keys(꺼둔·죽은 키 제외) 하나를 그대로 쓴다 — 여기서 다시 거르지 않는다.

쓰는 법(서버 읽기라 사장님이 직접):  ! py tools/calcopy/pull_pool_keys.py
    --dry  : 몇 개 받을지 세기만(.env 안 씀)
.env 의 `# >>> calcopy pool keys` ~ `# <<< calcopy pool keys` 칸만 다시 쓴다(여러 번 돌려도 같은 결과).
키 값은 화면에 찍지 않는다(개수만).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOST = "ubuntu@3.35.251.172"   # IP 가 바뀌면 nslookup shoppingshorts.duckdns.org
KEY = str(Path.home() / "crawling_bot_client" / "LightsailDefaultKey-ap-northeast-2.pem").replace("\\", "/")
REPO = "/home/ubuntu/lotto-stock-wiki"
START, END = "# >>> calcopy pool keys", "# <<< calcopy pool keys"
NAME = "SHORTS_GEMINI_KEY_{}"

_REMOTE = r'''cd %s && set -a; . /etc/shopping-shorts.env; set +a; python3 -c "
import json,os,re
from shopping_shorts.store import Store
from shopping_shorts.config import DB_PATH
own=[v for k,v in sorted(os.environ.items()) if re.fullmatch(r'(SHORTS_GEMINI_KEY|GEMINI_API_KEY)(_\d+)?',k) and v.strip()]
pool=Store(DB_PATH).get_pooled_keys('gemini')
print('JSON'+json.dumps({'owner':own,'pool':pool}))"''' % REPO


def fetch() -> tuple[list[str], list[str]]:
    r = subprocess.run(["ssh", "-o", "ConnectTimeout=15", "-i", KEY, HOST, _REMOTE],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    line = next((l for l in (r.stdout or "").splitlines() if l.startswith("JSON")), "")
    if r.returncode or not line:
        raise SystemExit("서버에서 키를 못 받았다(rc=%s): %s" % (r.returncode, (r.stderr or r.stdout)[-300:]))
    d = json.loads(line[4:])
    return [k.strip() for k in d["owner"] if k.strip()], [k.strip() for k in d["pool"] if k and k.strip()]


def env_targets() -> list[Path]:
    """이 폴더의 .env + (트랙 폴더면) main 폴더 .env — 둘 다 엔진이 읽는 자리다."""
    out = [ROOT / ".env"]
    if ROOT.parent.name == ".tracks":
        out.append(ROOT.parent.parent / ".env")
    return out


def write_block(env: Path, keys: list[str]) -> int:
    text = env.read_text(encoding="utf-8") if env.exists() else ""
    text = re.sub(r"\n?%s.*?%s\n?" % (re.escape(START), re.escape(END)), "\n", text, flags=re.S)
    have = {m.group(2).strip() for m in re.finditer(r"^([A-Z0-9_]+)=(\S+)", text, flags=re.M)}
    used = {int(m.group(1)) for m in re.finditer(r"^SHORTS_GEMINI_KEY_(\d+)=", text, flags=re.M)}
    new, n = [], 100      # 100번부터 — 손으로 넣은 번호(_2~_14 등)와 안 겹치게
    for k in keys:
        if k in have:
            continue
        have.add(k)
        while n in used:
            n += 1
        new.append("%s=%s" % (NAME.format(n), k))
        n += 1
    block = "\n".join([START, "# pull_pool_keys.py 가 쓴다 — 손으로 고치지 마라", *new, END])
    env.write_text(text.rstrip("\n") + "\n\n" + block + "\n", encoding="utf-8")
    return len(new)


def main(argv: list[str]) -> int:
    owner, pool = fetch()
    keys = list(dict.fromkeys(owner + pool))
    print("서버: 사장님 키 %d + 회원 공용 %d = 중복 빼고 %d개" % (len(owner), len(pool), len(keys)))
    if "--dry" in argv:
        return 0
    for env in env_targets():
        print("%s: 새로 넣음 %d개" % (env, write_block(env, keys)))
    sys.path.insert(0, str(ROOT))
    from tools.calcopy.engine import gemini_keys
    print("엔진이 보는 키: %d개" % len(gemini_keys.keys()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
