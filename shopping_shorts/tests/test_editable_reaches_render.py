"""회원 설정 칸 전수 대조 — 저장 관문(preview_request.EDITABLE·check)을 통과하는 칸은 bench 렌더 입력에 닿거나, 안 닿는다고 알려야 한다.

왜(11-05): 칸이 저장은 되는데 bench 렌더(styles.member_frame → render_bench snapshot·frame_png·frame_segments)에 안 닿는 결함이
칸마다 따로 반복됐다(58767e5ef 자막 등장·강조·자막팩 · 8934f3b6d · 91f864e50 화면 틀·자막 쌓기). 칸별 수리 대신 이 장치 하나:
- EDITABLE 의 모든 (그룹, 칸)(text.caption 은 check 가 받는 하위 칸까지)이 아래 CASES 표에 있어야 한다 — 새 칸을 만들면 여기서 실패한다.
  표에 넣으려면 '어디서 쓰는지(길)'를 적어야 하고, 그 길의 렌더 입력이 기본과 달라지는지 실제로 잰다(= 칸을 만든 사람이 렌더 연결도 한다).
- 길(ROUTES): frame_png 그림 · frame_segments 구간 틀 · snapshot 자막 스냅샷 · caption 판 자막 칸(쌓기) · voice 대본 목소리(RI.member_voice) ·
  bgm 믹스 곡(render_bench.mix_bgm_id) · text_mode 박힌 글자 방식(flow_driver.js → SHORTEM_TEXT_MODE → vmake_clean.style_mode).
- 영상에 안 닿는 칸은 st['member_unused'] 에 그 칸 이름이 남으면 통과(조용히 받지 않는다).
- NOT_REACHING = 지금 bench 판에서 쓰는 곳이 없는 칸(결함 목록, 고치면 strict xfail 이 깨져 CASES 로 옮기게 한다)."""
import hashlib
import inspect
import json
import re
from pathlib import Path

import pytest

from tools.calcopy import preview_request as PR
from tools.calcopy import vmake_clean as VC
from tools.calcopy.hybrid import render_bench as RB, render_itssum as RI, styles as STY

ROOT = Path(__file__).resolve().parents[2]
V = "썰템쇼판"          # bench 판 — 게시글형(머리띠·작성자 줄)·구간 틀(훅 카드)·자막 쌓기(caption.stack)·자막팩 humorshowshow 가 다 있다
S = {"title": ["아무도 몰랐던", "이 제품 뒷이야기"], "title_lines": ["아무도 몰랐던", "이 제품 뒷이야기"], "source_label": "출처",
     "lines": [{"id": "L1", "kind": "tts", "tts": "a", "caps": [{"text": "a"}]}]}
T = {"lines": {"L1": [0.0, 1.0]}, "end": 10.0}
TC = "tc_68f9c6a72f0f04a417bb136f"       # 문정(타입캐스트) — 판 목소리(박창수)와 다른 성우
NAME = {"brand": {"channel_name": "시험채널"}}

# (그룹, 칸[, 하위 칸]) → (값, 앞에 깔 회원 칸(그 칸이 기대는 칸 — 그 위에서 이 칸만 바꿔 잰다), 쓰는 길)
CASES = {
    ("brand", "channel_name"): ("시험채널", {}, ("frame_png", "frame_segments")),
    ("brand", "colors"): ({"bg": [30, 60, 120]}, {}, ("frame_png", "frame_segments")),
    ("brand", "logo"): ({"file": "p_test.png", "x": 40, "y": 1500, "w": 300}, {}, ("frame_png",)),
    ("brand", "name_scale"): (1.6, NAME, ("frame_png",)),
    ("brand", "name_color"): ("#FF0000", NAME, ("frame_png",)),
    ("brand", "watermark"): ({"cx": 300, "cy": 1700, "px": 70, "alpha": 220}, NAME, ("frame_png", "frame_segments")),
    ("text", "title_font"): ("BMJUA", {}, ("frame_png",)),
    ("text", "title_colors"): (["#FF0000", "#00FF00"], {}, ("frame_png",)),
    ("text", "title_scale"): (0.8, {}, ("frame_png",)),
    ("text", "title_dy"): (120, {}, ("frame_png",)),
    ("text", "caption_color"): ("#FF0000", {}, ("snapshot",)),
    ("text", "caption_dy"): (-120, {}, ("snapshot",)),
    ("text", "caption_font"): ("BMJUA", {}, ("snapshot",)),
    ("text", "caption_scale"): (1.3, {}, ("snapshot",)),
    ("text", "caption", "mode"): ("replace", {}, ("member_unused",)),      # bench 는 판 caption.stack 으로 쌓는다 — 안 닿는다고 알림
    ("text", "caption", "enter"): ({"kind": "pop", "ms": 250}, {}, ("snapshot",)),
    ("text", "caption", "emphasis"): ({"words": "auto", "style": "underline", "rgb": [255, 0, 0]}, {}, ("snapshot",)),
    ("text", "caption", "outline_px"): (8, {}, ("snapshot",)),
    ("text", "caption", "outline_rgb"): ([255, 255, 255], {}, ("snapshot",)),
    ("text", "caption_pack"): ("clean", {}, ("snapshot",)),
    ("text", "orig_text"): ("vmake", {}, ("text_mode",)),                # 판 orig_text.mode = blur
    ("text", "post_author"): ("시험작성자", {}, ("frame_png",)),
    ("text", "layout"): ("full", {}, ("frame_png", "frame_segments")),
    ("text", "caption_stack"): ({"y": 900, "pitch": 120, "break": "full"}, {}, ("caption",)),
    ("tts", "voice_id"): (TC, {}, ("voice",)),
    ("tts", "provider"): ("typecast", {"tts": {"voice_id": TC}}, ("voice",)),
    ("tts", "name"): ("문정", {"tts": {"voice_id": TC}}, ("voice",)),
    ("tts", "tempo"): (1.2, {}, ("voice",)),
    ("tts", "emotion"): ("happy", {"tts": {"voice_id": TC, "provider": "typecast"}}, ("voice",)),
    ("bgm", "candidates"): (["blue"], {}, ("bgm",)),                      # 판 곡 = sweets
}

# 지금 bench 판에서 쓰는 곳이 없는 칸 — 결함 목록(고치지 않고 보고, 2026-11-05). 쓰는 곳 = 옛 PC 제작기 팩("1") 길뿐.
NOT_REACHING = {
    ("tts", "preset_id"): ("tc-moonjung-stable", {"tts": {"voice_id": TC}}, "styles.member_frame 이 tts 에서 voice_id·name·provider·tempo·emotion 만 받는다"),
    ("tts", "alternates"): ([{"voice_id": TC, "name": "문정"}], {}, "대체 목소리는 make.py --voice(옛 PC 제작기)만 읽는다"),
    ("bgm", "gain"): (0.3, {}, "member_frame 은 gain==0(없음)만 본다 — bench 믹스 크기는 판 bgm.db_below_voice"),
    ("sfx_pool", "start"): (["sfx_x"], {}, "bench 효과음 = 판 sfx_files(옛 engine/remake 만 sfx_pool)"),
    ("sfx_pool", "point"): (["sfx_x"], {}, "위와 같음"),
    ("sfx_pool", "end"): (["sfx_x"], {}, "위와 같음"),
    ("meme_pool", "kinds"): (["놀람"], {}, "bench 짤 = 흐름이 받은 W/memes(옛 engine/remake 만 meme_pool)"),
    ("meme_pool", "ids"): ([], {}, "위와 같음"),
    ("template",): ("__first__", {}, "bench 스냅샷 presetId 는 plain 고정 — 템플릿은 preset_make·render_jaemi 길만"),
}

ROUTES = ("frame_png", "frame_segments", "snapshot", "caption", "voice", "bgm", "text_mode")


def _caption_subkeys() -> set:
    """check 가 받는 text.caption 하위 칸 — check 소스의 'set(cap) - {…}' 그대로(하위 칸이 늘면 표도 늘어야 한다)."""
    m = re.search(r"set\(cap\) - \{([^}]*)\}", inspect.getsource(PR.check))
    return set(re.findall(r'"(\w+)"', m.group(1)))


def _editable_keys() -> set:
    out = set()
    for g, ks in PR.EDITABLE.items():
        if ks is None:
            out.add((g,))
        for k in ks or ():
            if (g, k) == ("text", "caption"):
                out |= {(g, k, s) for s in _caption_subkeys()}
            else:
                out.add((g, k))
    return out


def _pack(key, value, base) -> dict:
    if key == ("template",):
        t = PR.catalog()["templates"][0]
        value = {"mode": t["mode"], "id": t["id"]}
    p = json.loads(json.dumps(base))
    if len(key) == 1:
        p[key[0]] = value
    elif len(key) == 2:
        p.setdefault(key[0], {})[key[1]] = value
    else:
        p.setdefault(key[0], {}).setdefault(key[1], {})[key[2]] = value
    return p


def _inputs(tmp_path, monkeypatch, member) -> dict:
    """회원 팩 member 로 판을 읽어 렌더 입력을 길별로 잰다(값 = 해시 또는 값). member=None = 회원 팩 없음."""
    monkeypatch.delenv("SHORTEM_TEXT_MODE", raising=False)
    if member is None:
        monkeypatch.delenv("SHORTEM_MEMBER_PACK", raising=False)
    else:
        d = tmp_path / ("m" + hashlib.md5(json.dumps(member, sort_keys=True).encode()).hexdigest()[:10])
        (d / "packs").mkdir(parents=True, exist_ok=True)
        (d / "logos").mkdir(exist_ok=True)
        from PIL import Image
        Image.new("RGBA", (300, 120), (255, 0, 0, 255)).save(d / "logos" / "p_test.png")
        pf = d / "packs" / "p.json"
        pf.write_text(json.dumps({"member": member}, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setenv("SHORTEM_MEMBER_PACK", str(pf))
        tm = (member.get("text") or {}).get("orig_text")
        if tm in ("vmake", "blur"):          # flow_driver.js 가 회원 칸 text.orig_text 를 실행기 환경으로(아래 시험이 그 코드를 확인)
            monkeypatch.setenv("SHORTEM_TEXT_MODE", tm)
    st = STY.load(V)
    png = tmp_path / "f.png"
    RB.frame_png(dict(S), st, png)
    h = lambda o: hashlib.md5(json.dumps(o, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()   # noqa: E731
    S2 = {"voice": {k: st["voice"][k] for k in ("name", "voice_id", "provider", "emotion") if k in st["voice"]}}
    RI.member_voice(S2, st)
    return {"frame_png": hashlib.md5(png.read_bytes()).hexdigest(),
            "frame_segments": h(RB.frame_segments(dict(S), T, st)),
            "snapshot": h(RB.snapshot(st)),
            "caption": h(st.get("caption")),
            "voice": h([S2.get("voice"), S2.get("member_tempo")]),
            "bgm": RB.mix_bgm_id({}, st),
            "text_mode": VC.style_mode(V),
            "member_unused": list(st.get("member_unused") or [])}


def _name(key) -> str:
    return ".".join(key)


def test_표가_EDITABLE_전_칸을_덮는다():
    keys = _editable_keys()
    missing = sorted(keys - set(CASES) - set(NOT_REACHING))
    assert not missing, f"렌더 대조 표에 없는 회원 칸 {missing} — CASES 에 값·쓰는 길을 적고 렌더까지 연결하라"
    assert not (set(CASES) | set(NOT_REACHING)) - keys, "EDITABLE 에서 빠진 칸이 표에 남았다"
    assert not set(CASES) & set(NOT_REACHING)
    assert all(set(r) <= set(ROUTES) | {"member_unused"} for _, _, r in CASES.values())


@pytest.mark.parametrize("key", sorted(set(CASES) | set(NOT_REACHING)), ids=_name)
def test_대표값은_저장_관문을_통과한다(key):
    value, base = (CASES.get(key) or NOT_REACHING[key])[:2]
    assert PR.check(_pack(key, value, base)) == [], f"{_name(key)} 대표값이 저장 관문에서 거절됐다"


@pytest.fixture(scope="module")
def _cache():
    return {}


def _diff(tmp_path, monkeypatch, cache, key, value, base):
    k0 = json.dumps(base, sort_keys=True)
    if k0 not in cache:
        cache[k0] = _inputs(tmp_path, monkeypatch, base)      # 기준선도 회원 팩(빈 팩이라도) — 팩이 있기만 해도 달라지는 칸(채널명 없음 = 로고·워터마크 지움)을 칸 효과로 오인하지 않게
    a = cache[k0]
    b = _inputs(tmp_path, monkeypatch, _pack(key, value, base))
    changed = {r for r in ROUTES if a[r] != b[r]}
    told = any(_name(key) in m for m in b["member_unused"] if m not in a["member_unused"])
    return changed, told


@pytest.mark.parametrize("key", sorted(CASES), ids=_name)
def test_칸이_렌더_입력에_닿는다(key, tmp_path, monkeypatch, _cache):
    value, base, routes = CASES[key]
    changed, told = _diff(tmp_path, monkeypatch, _cache, key, value, base)
    if "member_unused" in routes:
        assert told, f"{_name(key)} — 안 닿는 칸인데 member_unused 로 알리지 않았다"
        return
    assert changed & set(routes) or told, (f"{_name(key)} 가 저장은 되는데 bench 렌더 입력({'/'.join(routes)})이 안 달라진다 "
                                           f"(달라진 길: {sorted(changed) or '없음'}) — styles.member_frame 연결 확인")


@pytest.mark.parametrize("key", sorted(NOT_REACHING), ids=_name)
@pytest.mark.xfail(strict=True, reason="bench 판에서 쓰는 곳이 없는 칸(결함 목록) — 연결하면 이 xfail 이 깨진다: CASES 로 옮겨라")
def test_안_닿는_칸_목록(key, tmp_path, monkeypatch, _cache):
    value, base, _why = NOT_REACHING[key]
    changed, told = _diff(tmp_path, monkeypatch, _cache, key, value, base)
    assert changed or told


def test_박힌_글자_칸은_실행기가_환경으로_넘긴다():
    """text.orig_text 의 길 앞 절반(회원 PC) — flow_driver.js 가 팩 text.orig_text 를 SHORTEM_TEXT_MODE 로(vmake_clean.style_mode 가 읽는다)."""
    js = (ROOT / "shortem_client" / "server" / "flow_driver.js").read_text(encoding="utf-8")
    assert "pk.text.orig_text" in js and "SHORTEM_TEXT_MODE: textMode" in js
    assert "SHORTEM_TEXT_MODE" in inspect.getsource(VC.style_mode)
