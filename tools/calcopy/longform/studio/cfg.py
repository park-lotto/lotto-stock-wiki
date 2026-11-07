# 설정의 주인(load_cfg)과 경로. 장면표를 읽지 않으므로 녹음(steps/narrate.py)도 같은 함수를 부른다.
import os, json
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(HERE, *a)                     # 공용 재료(글꼴·효과음·배경음)
WORK = os.path.abspath(os.environ.get("SHORCL_WORK") or os.getcwd())   # 편마다 다른 것(대본·샷·녹음·그림·결과)
E = lambda *a: os.path.join(WORK, *a)
def load_cfg():
    """설정의 주인. 기본 channel.json ← 판(plates/<이름>/channel.json) ← 작업 폴더 channel.json.
    판 이름을 아는 곳은 여기 하나다(SHORCL_PLATE 가 작업 폴더 plate 칸보다 먼저). 다른 함수는 CFG 칸만 읽는다.
    판 층의 dict 칸(colors 등)은 기본 위에 칸별로 얹고, 작업 폴더 층은 예전처럼 얕게 덮는다."""
    cfg = json.load(open(P("channel.json"), encoding="utf-8"))
    work = json.load(open(E("channel.json"), encoding="utf-8")) if os.path.exists(E("channel.json")) and E("channel.json") != P("channel.json") else {}
    plate = os.environ.get("SHORCL_PLATE") or work.get("plate")
    if plate:
        pp = P("plates", plate, "channel.json")
        if not os.path.exists(pp): raise SystemExit(f"없는 판: {plate} ({pp})")
        for k, v in json.load(open(pp, encoding="utf-8")).items():
            if k.startswith("_"): continue
            cfg[k] = dict(cfg[k], **v) if isinstance(v, dict) and isinstance(cfg.get(k), dict) else v
        cfg["plate"] = plate
    cfg.update(work)
    if plate: cfg["plate"] = plate
    return cfg
