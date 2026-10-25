# -*- coding: utf-8 -*-
"""지시서 15(관제 263, 표준 §12-4) — 효과 밀도·말속도 상위 편 목표.

  · placement.place targets 모드: 업그레이드 판(targets 칸)은 꾸밈·효과음 개수를 상위 편 p75 쪽으로(상한 max) — 1차 판은 결과 그대로
  · 조용한 0발 금지(⑮): rules.sfx 없는 판 → 로그 ⚠ + check_place ×
  · script_audit tts_cps_spread: 편차 큰 대본 실패 + 다시 나누기 제안 / 고른 대본 통과
  · render_itssum.make_sentences(spread): 타입캐스트만 줄별 ±8%, 미나(고정 배속 1.35)는 그대로
"""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import placement as PL  # noqa: E402
from tools.calcopy.hybrid import render_itssum as RI  # noqa: E402
from tools.calcopy.hybrid import script_audit as SA  # noqa: E402
from tools.calcopy.hybrid import styles as ST  # noqa: E402


def _rows():
    """나레 16덩어리(7줄, 줄마다 key 있는 덩어리 하나 이상) + 원음 6덩어리 — 잇템로그 ep13 꼴(28초)."""
    out, t = [], 0.0
    plan = [("N1", "narr", ["연어로 만든 크림을|연어", "얼굴에 바르고", "경악한 외국인이 있다는데요?"]),
            ("O1", "orig", ["진짜야 연어래|연어", "뭐?"]),
            ("N2", "narr", ["분홍 알갱이마다|분홍", "성분이 들었다는데|성분"]),
            ("N3", "narr", ["얼굴에 올리고", "스르르 녹아 버렸어요|녹아"]),
            ("O2", "orig", ["어머 세상에!", "진짜 세상에!|세상에"]),
            ("N4", "narr", ["다른 외국인도", "소리부터 질렀는데|소리"]),
            ("O3", "orig", ["우와!", "이게 뭐야?|뭐야"]),
            ("N5", "narr", ["댓글 보니까", "한두 알이면 충분하다던데|한두 알"]),
            ("N6", "narr", ["버블티 펄 같다는|버블티", "사람도 있다고 하고"]),
            ("N7", "narr", ["아 나도 오늘 밤엔", "캡슐 딱 두 알만|두 알", "발라 봐야겠다"])]
    for line, sp, caps in plan:
        for j, c in enumerate(caps):
            text, _, key = c.partition("|")
            r = {"line": line, "j": j, "speaker": sp, "text": text, "t0": round(t, 3), "t1": round(t + 1.27, 3)}
            if key:
                r["key"] = key
            out.append(r)
            t += 1.27
    return out


def _deco(r):
    return PL._is_deco(r)          # 1차 자(kal_analyze._decorated)와 같은 자 — 훅 빨강·팝 변형도 꾸밈(04 b94bcb3aa)


TG = {"fx_rate_narr": {"goal": 0.18, "cap": 0.231, "p25": 0.12, "first": 0.124, "src": "시험"},
      "fx_rate_orig": {"goal": 0.056, "cap": 0.111, "p25": 0.0, "first": 0.056, "src": "시험"},
      "sfx_rate": {"goal": 0.051, "cap": 0.067, "p25": 0.035, "first": 0.051, "src": "시험"}}


def test_no_sfx_rule_warns_and_check_fails():
    """사보타주 짝: 고치기 전 placement 는 rules.sfx 없는 판에서 '효과음 0발(판 규칙 sfx 없음)' 로그만 남기고 check_place ok=True(조용한 0발)."""
    st = copy.deepcopy(ST.load("잇템로그판"))
    del st["placement"]["rules"]["sfx"]
    p = PL.place(_rows(), st, "seed")
    assert p["sfx"] == []
    assert any(w.startswith("⚠ 효과음 0발") for w in p.get("warn") or []), p.get("warn")
    assert any(l.startswith("⚠ 효과음 0발") for l in p["log"])
    chk = PL.check_place(p, st)
    assert chk["ok"] is False and any("효과음 0발" in b for b in chk["bad"]), chk["bad"]
    # 벤치에 효과음이 정말 없으면 판에 0 을 적는다 → 경고 없음(없는 것도 스타일)
    st["placement"]["rules"]["sfx"] = {"max": 0, "why": "시험 — 벤치 0발"}
    p2 = PL.place(_rows(), st, "seed")
    assert not p2.get("warn") and p2["sfx"] == []


def test_first_pan_unchanged_and_v2_without_targets_equals_first():
    """1차 판(targets 없음) = 옛 동작: 목표 모드 칸이 안 생기고, v2 에서 목표 모드를 끄면 1차 판과 자막표·효과음·전환이 같다."""
    rows = _rows()
    a = PL.place(rows, ST.load("잇템로그판"), "ep13")
    b = PL.place(rows, ST.load("잇템로그판_v2"), "ep13", targets=False)
    assert "targets" not in a and not any("목표 밀도" in l for l in a["log"])
    nocolor = lambda rs: [{**r, "emph": [{k: v for k, v in e.items() if k != "color"} for e in r.get("emph") or []]} for r in rs]  # noqa: E731
    assert nocolor(a["rows"]) == nocolor(b["rows"])          # 강조색(㉒)은 업그레이드 판에서만 고른다 — 자리·낱말은 같다
    for k in ("sfx", "transitions", "reference"):
        assert a[k] == b[k], k
    assert PL.density_targets(ST.load("잇템로그판")) is None


def _no_deco_pos(name):
    st = copy.deepcopy(ST.load(name))
    st["placement"]["rules"].pop("deco_pos", None)          # 07 15a9f46ed 가 판에 넣은 deco_pos·stickers — 목표 모드만 따로 잰다
    st["placement"]["rules"].pop("stickers", None)
    return st


def test_targets_fill_density_to_goal_within_cap():
    st = _no_deco_pos("잇템로그판_v2")
    rows = _rows()
    p = PL.place(rows, st, "ep13", targets=TG)
    narr = [r for r in p["rows"] if r["speaker"] == "narr"]
    G = PL.density_goal({"p75": 0.18, "p25": 0.12, "max": 0.231, "first": 0.124}, len(narr))
    assert (G["n_goal"], G["lo"], G["hi"], G["n_first"]) == (3, 2, 4, 2)          # 16덩어리: round(2.88)·round(1.92)·round(3.70)·round(1.98)
    assert sum(_deco(r) for r in narr) == G["n_goal"]
    assert all(r["emph"][0]["word"] == r["key"] for r in narr if r.get("emph_by") == "targets")   # 종류 = 1차 그대로(강조 낱말 = 대본 key)
    # 훅 변형 3덩어리만으로 목표 3 이 찬다 → 목표를 올리면(0.3×16=5) 훅 밖 덩어리에 강조를 더하고, 강조색 규칙(㉒)이 지워도 다른 덩어리로 다시 채운다
    TG2 = {**TG, "fx_rate_narr": {**TG["fx_rate_narr"], "goal": 0.3, "cap": 0.4}}
    p2 = PL.place(rows, st, "ep13", targets=TG2)
    n2 = [r for r in p2["rows"] if r["speaker"] == "narr"]
    G2 = PL.density_goal({"p75": 0.3, "p25": 0.12, "max": 0.4, "first": 0.124}, len(n2))
    assert sum(_deco(r) for r in n2) == G2["n_goal"] == 5, [(r["text"], r.get("emph"), r.get("variant")) for r in n2]
    assert sum(1 for r in n2 if r.get("emph_by") == "targets" and r.get("emph")) == 2
    dur = rows[-1]["t1"]
    Gs = PL.density_goal({"p75": 0.051, "p25": 0.035, "max": 0.067, "first": 0.051}, dur)
    assert len(p["sfx"]) == Gs["n_goal"] and Gs["lo"] <= len(p["sfx"]) <= Gs["hi"]
    chk = PL.check_place(p, st)
    assert "targets" in chk["slots"] and not [b for b in chk["bad"] if "목표 밀도" in b], chk["bad"]
    # 1차로 돌리면 강조는 본보기 비율만(목표 모드 아님)
    a = PL.place(rows, ST.load("잇템로그판"), "ep13")
    assert not any(r.get("emph_by") == "targets" for r in a["rows"])


def test_targets_sfx_roles_rule_and_cap_check():
    """rules.sfx.roles(03→15 넘김) = 그 역할에만 · 목표 밖이면 check_place ×."""
    st = copy.deepcopy(ST.load("잇템로그판_v2"))
    st["placement"]["rules"]["sfx"]["roles"] = ["훅"]
    p = PL.place(_rows(), st, "ep13", targets=TG)
    assert p["sfx"] and all(e.get("role") in ("hook", None) for e in p["sfx"]), p["sfx"]
    bad = PL.check_place({**p, "targets": {"sfx_rate": {"n": 9, "n_goal": 1, "lo": 1, "hi": 2}}}, st)["bad"]
    assert any("목표 밀도 sfx_rate" in b for b in bad)


def test_density_targets_reads_top_file_same_ruler():
    """v2 목표 = 상위편_목표.json density(placement.py count 잇템로그판 --top · kal_analyze._stats — upgrade_table 과 같은 자)."""
    tg = PL.density_targets(ST.load("잇템로그판_v2"))
    p = ROOT / "channel/ititemlog/_kal/상위편_목표.json"
    D = json.loads(p.read_text(encoding="utf-8")).get("density")
    if not D:
        pytest.skip("상위편_목표.json density 없음 — count 잇템로그판 --top 전")
    assert tg["sfx_rate"]["goal"] == D["sfx_rate"]["p75"] and tg["fx_rate_narr"]["cap"] == D["fx_rate_narr"]["max"]
    assert "상위편_목표.json" in tg["sfx_rate"]["src"]


def test_sticker_kind_new_vocab():
    assert PL.sticker_kind("기타(노랑 물음표 + 동심원 그림 애니)") == "question"
    assert PL.sticker_kind("노랑 글자 라벨 '3600원'(검은 외곽)") == "yellow_label"
    assert PL.sticker_kind("기타(마우스 손가락 포인터 — 클릭 시늉)") == "cursor"
    assert PL.sticker_kind("주황 손그림 X(#f95d32)") == "hand_x"
    assert PL.sticker_kind("💎 다이아") == "gem"


def _script(caps_per_line):
    return {"lines": [{"id": f"N{i + 1}", "kind": "tts", "tts": " ".join(c) + ".", "caps": [{"text": x} for x in c]} for i, c in enumerate(caps_per_line)]}


def test_tts_cps_spread_line_level_uneven_fails_with_suggestion_even_passes():
    """⑲ 말속도 편차 = TTS 줄 단위(자막 조각 나누기와 무관 — caps 를 바꿔도 값이 같다)."""
    st = ST.load("잇템로그판")
    uneven = _script([["댓글 보니까"], ["캡슐은 한두 알이면 충분하다던데 사람마다 다르다고 하고"], ["아, 진짜, 와,"], ["처음 보고는 소리부터 질렀는데"]])
    ok, why = SA.rule_check({"kind": "tts_cps_spread", "max": 0.063}, uneven, st)
    assert ok is False and "제안" in why, why
    R = SA.cps_spread(uneven, {"max": 0.063}, st)
    assert R["level"] == "line" and R["suggest"] and any("쉼표" in s["why"] for s in R["suggest"]), R["suggest"]
    resplit = _script([["댓글", "보니까"], ["캡슐은 한두 알이면", "충분하다던데 사람마다 다르다고 하고"], ["아,", "진짜, 와,"], ["처음 보고는", "소리부터 질렀는데"]])
    assert SA.cps_spread(resplit, {"max": 0.063}, st)["cv"] == R["cv"], "자막 나누기는 줄 단위 자에 영향 없음"
    even = _script([["댓글 보니까 캡슐은 한두 알이면"], ["다른 외국인도 처음 보고 놀랐는데"], ["분홍 알갱이마다 성분이 들었다는데"]])
    ok2, why2 = SA.rule_check({"kind": "tts_cps_spread", "max": 0.063}, even, st)
    assert ok2 is True, why2


def test_speech_rule_from_targets_only_on_upgrade_pan():
    assert SA.speech_rule(ST.load("잇템로그판")) is None
    r = SA.speech_rule(ST.load("잇템로그판_v2"))
    v2 = ST.load("잇템로그판_v2")["targets"]["speech"]
    assert r and r["kind"] == "tts_cps_spread" and r["max"] == v2["cps_cv"]["ours_goal"], r      # 조각 자(spread)가 아니라 문장 자(cps_cv)
    assert RI.spread_of(ST.load("잇템로그판_v2")) == v2["cps_cv"]["ours_goal"]


def test_density_judge_rule():
    """⑳ 나아짐 = 허용 범위 안 ∧ 1차 n 보다 목표에 가깝거나 같음 · 나빠짐 = 범위 밖(27.8초 효과음: 목표 1·허용 1~2)."""
    G = PL.density_goal({"p75": 0.051, "p25": 0.035, "max": 0.067, "first": 0.051}, 27.77)
    assert (G["n_goal"], G["lo"], G["hi"], G["n_first"]) == (1, 1, 2, 1)
    assert PL.density_judge(1, G) == (True, False)
    assert PL.density_judge(2, G) == (False, False)      # 범위 안이지만 1차(1)보다 목표에서 멀다
    assert PL.density_judge(0, G) == (False, True)
    assert PL.density_judge(3, G) == (False, True)


def test_fine_tempos_bounds():
    rates = [8.4, 7.3, 7.9, 6.4]
    base = [1.2 * 0.9001, 1.2, 1.2, min(1.2 * 1.0999, RI.TEMPO_MAX)]                     # 옛 ±10% 규칙 배속(빠른 줄 −10%·느린 줄 +10%, 상한 1.25)
    assert RI.fine_tempos(rates, 1.2, None, 7.5, base) is None                           # 1차 판(목표 없음) = 안 함
    assert RI.fine_tempos([7.5, 7.5, 7.6, 7.5], 1.2, 0.06, 7.5, [1.2] * 4) is None       # 이미 목표 이하 = 안 함
    t = RI.fine_tempos(rates, 1.2, 0.01, 7.5, base)
    assert t and all(min(b, 1.2 * 0.92) - 1e-4 <= x <= max(b, min(1.2 * 1.08, RI.TEMPO_MAX)) + 1e-4 for x, b in zip(t, base)), t   # 배속은 4자리 반올림
    assert t[0] <= base[0] + 1e-4, "옛 규칙이 이미 더 고친 줄은 덜 고치지 않는다(10-25 ep13 0.0571→0.0636 회귀)"
    est = lambda tls: [r * x / 1.2 for r, x in zip(rates, tls)]  # noqa: E731
    import statistics as S
    cv = lambda xs: S.pstdev(xs) / S.mean(xs)  # noqa: E731
    assert cv(est(t)) <= cv(est(base)) + 1e-9
    assert RI.spread_of(ST.load("잇템로그판")) is None and RI.spread_of(ST.load("키치잇판")) is None


def _fake_narr(tmp: Path) -> Path:
    """줄 3개 꼴 가짜 목소리(소리 0.9·1.6·0.8초 + 0.3초 쉼) — ffmpeg 로 만든다(합성 아님)."""
    p = tmp / "narr_full.wav"
    f = "sine=f=220:d={d},volume=0.5"
    parts = ";".join(f"{f.format(d=d)}[s{i}];anullsrc=r=48000:cl=mono,atrim=0:0.3[z{i}]" for i, d in enumerate((0.9, 1.6, 0.8)))
    cat = "".join(f"[s{i}][z{i}]" for i in range(3))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-filter_complex", f"{parts};{cat}concat=n=6:v=0:a=1,aformat=sample_rates=48000:channel_layouts=mono[o]",
                    "-map", "[o]", str(p)], check=True)
    return p


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg 없음")
@pytest.mark.parametrize("voice,fixed", [("kr-mina-expressive", True), ("tc_61130d6cf89dd58a4c13295d", False)])
def test_make_sentences_spread_mina_untouched_typecast_fine(tmp_path, voice, fixed):
    full = _fake_narr(tmp_path)
    S = {"voice": {"voice_id": voice}, "cps_target": 8.6,
         "lines": [{"id": "N1", "kind": "tts", "tts": "가나다라마바사."}, {"id": "N2", "kind": "tts", "tts": "가나다라마바사아자차카."},
                   {"id": "N3", "kind": "tts", "tts": "가나다라마바사아자."}],
         "tts_spans": {"N1": [0.0, 0.9], "N2": [1.2, 2.8], "N3": [3.1, 3.9]}}
    R0, R1 = tmp_path / "a", tmp_path / "b"
    R0.mkdir(); R1.mkdir()
    a, ta, _ = RI.make_sentences(S, full, R0, log=lambda *x: None)
    b, tb, _ = RI.make_sentences(S, full, R1, log=lambda *x: None, spread=0.01)
    fix = json.loads((R1 / "line_cps_fix.json").read_text(encoding="utf-8"))
    if fixed:
        assert ta == tb == 1.35 and [x["tempo"] for x in a] == [x["tempo"] for x in b], "미나 = 고정 배속 그대로"
        assert fix["applied"] is False and fix["fixed_voice"] is True
    else:
        assert fix["applied"] is True and fix["cv_after_est"] < fix["cv_before"], fix
        assert all(tb * 0.9 - 1e-4 <= x["tempo"] <= min(tb * 1.1, RI.TEMPO_MAX) + 1e-4 for x in b)      # 옛 ±10% 안 · 새로 더한 몫은 ±8% 안(fine_tempos)


def test_sfx_allowed_skips_meta_keys():
    """11 보고: 판 sfx_files 의 why·_ 시작·gain_db 는 효과음 종류가 아니다."""
    st = copy.deepcopy(ST.load("잇템로그판"))
    st["placement"]["rules"]["sfx"].pop("kinds", None)
    st["sfx_files"] = {"pop": "팩01/pop.wav", "gain_db": -8, "why": "근거 글", "_note": "x"}
    assert PL._sfx_allowed(st) == ["pop"]


def test_deco_counts_hook_variant_same_ruler_as_match():
    """04(b94bcb3aa): 훅 빨강·팝 변형 = 꾸밈 — placement 도 같은 자(kal_analyze.variant_fx)로 센다."""
    assert PL._is_deco({"enter": "cut", "variant_force": "hook"}) and PL._is_deco({"enter": "cut", "variant": "hook_pop"})
    assert not PL._is_deco({"enter": "cut", "variant": ""})


def test_deco_pos_spreads_decoration_to_body_like_bench():
    """rules.deco_pos: 훅 변형만 꾸밈이던 1차(훅 1.0) → 벤치 자리 비율(훅·본문)로 본문에 강조 · 화자 꾸밈 비율은 벤치 중앙+허용 폭 안."""
    st = _no_deco_pos("잇템로그판")
    rows = _rows()
    a = PL.place(rows, st, "ep13")
    assert "deco_pos" not in a                                   # 규칙 없으면 옛 동작
    st["placement"]["rules"]["deco_pos"] = {"from": "bench"}
    p = PL.place(rows, st, "ep13")
    B = PL.bench_fx(st)
    dur = max(r["t1"] for r in p["rows"])
    from tools.calcopy.engine import kal_analyze as K
    pos = [K._pos(r, dur) for r in p["rows"] if PL._is_deco(r)]
    for k, v in B["pos"].items():
        assert abs(pos.count(k) / len(pos) - v) <= B["tol"]["fx.pos"] + 1e-9, (k, pos, B["pos"])
    for sp, nm in (("narr", "나레"), ("orig", "원음")):
        g = [r for r in p["rows"] if r["speaker"] == sp]
        assert sum(PL._is_deco(r) for r in g) / len(g) <= B["rate"][nm] + B["tol"][f"fx.rate.{nm}"] + 1e-9
    assert all(r["emph"][0]["word"] == r["key"] for r in p["rows"] if r.get("emph_by") == "deco_pos")


def test_targets_refill_after_emph_color_drops(monkeypatch):
    """강조색 규칙(㉒)이 목표 모드 강조를 '후보 전부 미달'로 지우면 다른 key 덩어리로 다시 채워 목표 개수를 지킨다."""
    st = _no_deco_pos("잇템로그판_v2")
    rows = _rows()
    dropped = []
    real = PL.emph_color_step

    def drop_once(out, style, log):
        real(out, style, log)
        if not dropped:
            for r in out:
                if r.get("emph_by") == "targets" and r.get("emph"):
                    r["emph"] = []; dropped.append(r["text"]); break
    monkeypatch.setattr(PL, "emph_color_step", drop_once)
    TG2 = {**TG, "fx_rate_narr": {**TG["fx_rate_narr"], "goal": 0.3, "cap": 0.4}}
    p = PL.place(rows, st, "ep13", targets=TG2)
    narr = [r for r in p["rows"] if r["speaker"] == "narr"]
    assert dropped and sum(_deco(r) for r in narr) == 5, (dropped, [(r["text"], r.get("emph")) for r in narr])


def test_count_filter_by_sound_mode_matches_07_grouping():
    """판 counted.filter{sound_mode} = 그 갈래 편만 센다(07 70b5bef9a 임시 묶음과 같은 값) · 필터 없으면 폴더 통째(옛 동작)."""
    for name in ("도파민썰템A판", "도파민썰템B판"):
        st = ST.load(name)
        crit = PL.count_filter(st)
        want = []
        for f in sorted((PL.ROOT / st["bench"]["line_reads"]).glob("*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            if all(d.get(k) == v for k, v in crit.items()):
                want.append(d.get("id", f.stem))
        c = PL.count(st)
        assert crit and c["filter"]["ids"] == want and c["n_videos"] == len(want), (name, crit, c["filter"], want)
        assert set(c["filter"]["ids"]) >= set(st["placement"]["counted"]["filter"]["ids"])     # 07 임시 묶음(3편)은 다 들어 있다(06 이 편을 더하면 늘어남)
        st2 = copy.deepcopy(st)
        st2["placement"]["counted"].pop("filter")
        assert PL.count(st2)["n_videos"] > c["n_videos"] and "filter" not in PL.count(st2)


def test_skeleton_over_upgrade_cap_is_conflict_not_silent():
    """㉛: 뼈대 꾸밈(훅 변형·deco_pos) > 업그레이드 상한 → 어느 쪽도 안 늘리고 conflict{axis, need, cap, cause} · check_place ×."""
    st = copy.deepcopy(ST.load("잇템로그판_v2"))
    st["placement"]["rules"]["deco_pos"] = {"from": "bench"}
    st["placement"]["rules"].pop("stickers", None)
    for x in st["script"]["audit"]:
        if x["kind"] == "tts_chars":
            x["max"] = 20                                      # 훅 줄 N1 26자 > 20 → 원인 = tts_chars
    tg = {**TG, "fx_rate_narr": {**TG["fx_rate_narr"], "goal": 0.1, "cap": 0.1, "p25": 0.05}}     # 상한 round(0.1×16)=2 < 훅 변형 3
    p = PL.place(_rows(), st, "ep13", targets=tg)
    c = p.get("conflict")
    assert c and c["axis"] == "fx_rate_narr" and c["cap"] == 2 and c["need"] >= 3, c
    assert c["cause"] == "tts_chars" and c["by"].get("variant") == 3, c
    assert not any(r.get("emph_by") in ("deco_pos", "targets") for r in p["rows"]), "conflict 면 아무것도 더하지 않는다"
    assert any("conflict" in b for b in PL.check_place(p, st)["bad"])
    # 상한 안이면 conflict 없음(옛 동작)
    p2 = PL.place(_rows(), st, "ep13", targets=TG)
    assert not p2.get("conflict")


def test_sticker_role_condition_avoid_empty_and_fail_reason():
    """07 15a9f46ed 쪽지: ① rules.stickers.<kind>.role = 그 역할 덩어리에만 ② avoid [] = 피할 것 없음(기본 face 로 안 바뀜)
    ③ 자리 검출 실패 사유가 로그에(fx_target.locator.last_why)."""
    st = copy.deepcopy(ST.load("잇템로그판"))
    st["placement"]["rules"].pop("deco_pos", None)
    st["placement"]["rules"]["stickers"] = {"circle_arrow": {"target": "face", "avoid": [], "role": ["훅"], "why": "시험"}}
    ref = dict(PL.reference(st, "ep13")); ref["stickers"] = {"circle_arrow": 1}
    st["placement"]["reference"] = ref["id"]
    for v in st["placement"]["counted"]["videos"]:
        if v["id"] == ref["id"]:
            v["stickers"] = {"circle_arrow": 1}
    seen = []

    def loc(target, row, sticker):
        seen.append((row["role_key"], list(target["avoid"])))
        return {"x": 50, "y": 40, "w": 100, "h": 100, "conf": 0.9, "face_clear": True}
    p = PL.place(_rows(), st, "ep13", locate=loc)
    assert seen and all(r == "hook" for r, _ in seen), seen
    assert all(av == [] for _, av in seen), seen

    def loc_fail(target, row, sticker):
        return None
    loc_fail.last_why = "띠 위 [460, 1086, 620, 1246] 얼굴 겹침(>0.1) · 띠 아래 창 밖"
    p2 = PL.place(_rows(), st, "ep13", locate=loc_fail)
    assert any("사유: 띠 위" in l for l in p2["log"]), [l for l in p2["log"] if "스티커" in l]
    from tools.calcopy.hybrid import fx_target as FX
    why = []
    assert FX.caption_side((160, 160), (1258, 1330), (0, 1250, 1080, 90), (), why=why) is None and len(why) == 6, why   # 가운데·좌·우 × 위·아래


def test_colorflash_vocab_and_placement_for_shark():
    """02 468380769 colorflash 장치 — 줄판독 'flash(빨강 덮기 …)' = colorflash(흰 번쩍 flash 와 다름), 샥탬판 전환 배치에 나온다."""
    assert PL.trans_key("flash(빨강 덮기 → 0.45초 사라짐)") == "colorflash"
    assert PL.trans_key("flash(흰 번쩍)") == "flash" and PL.trans_key("flash") == "flash"
    assert "colorflash" in PL.TRANS_DRAWABLE
    st = copy.deepcopy(ST.load("샥탬판"))
    st["placement"]["counted"] = PL.count(st)
    assert st["placement"]["counted"]["transition"].get("colorflash", 0) > 0.1
    st["placement"]["rules"]["transition"] = {"kinds": ["colorflash"], "cond": {"min_cut_s": 0.5}}
    rows = [{"line": f"L{i}", "j": 0, "speaker": "narr" if i % 2 else "orig", "text": "가나다", "t0": i * 1.5, "t1": i * 1.5 + 1.4} for i in range(14)]
    p = PL.place(rows, st, "seed", cuts=[{"t0": i * 1.5, "dur": 1.5} for i in range(14)])
    assert p["transitions"] and all(e["kind"] == "colorflash" for e in p["transitions"]), p["transitions"]


def test_fail_reason_reaches_log_through_wrapped_locate(monkeypatch):
    """render_bench.make_locate 처럼 locator 를 한 번 더 감싸도 실패 사유가 배치 로그에 닿는다(fx_target.LAST_WHY) — ep13 kk_doodle '사유 없음' 실측."""
    from tools.calcopy.hybrid import fx_target as FX
    st = copy.deepcopy(ST.load("잇템로그판"))
    st["placement"]["rules"].pop("deco_pos", None)
    st["placement"]["rules"]["stickers"] = {"kk_doodle": {"target": "caption_side", "why": "시험"}}
    rid = PL.reference(st, "ep13")["id"]
    st["placement"]["reference"] = rid
    for v in st["placement"]["counted"]["videos"]:
        if v["id"] == rid:
            v["stickers"] = {"kk_doodle": 1}

    def wrapped(target, row, s):          # last_why 칸 없는 감싼 함수
        monkeypatch.setattr(FX, "LAST_WHY", "띠 위 얼굴 겹침(>0.1) · 띠 아래 얼굴 겹침(>0.1)")
        return None
    p = PL.place(_rows(), st, "ep13", locate=wrapped)
    assert any("사유: 띠 위 얼굴 겹침" in l for l in p["log"]), [l for l in p["log"] if "스티커" in l]


def test_mouth_anchor_box_and_caption_side_sides():
    """① 얼굴 자리 기준점 anchor:'mouth' = 입 양끝 랜드마크 가운데(미간 아님) ② caption_side 가운데가 얼굴로 막히면 좌우 자리."""
    from tools.calcopy.hybrid import fx_target as FX
    f = {"box": [300, 365, 700, 1100], "face": [300, 600, 700, 1100], "lm": [[420, 780], [580, 780], [500, 880], [440, 990], [560, 990]]}
    b = FX.mouth_box(f)
    assert abs((b[0] + b[2]) / 2 - 500) < 1e-6 and abs((b[1] + b[3]) / 2 - 990) < 1e-6        # 입 가운데
    assert FX.mouth_box({"box": [0, 0, 10, 10]}) is None
    face = [200, 900, 880, 1700]                          # 가운데를 덮는 큰 얼굴
    why = []
    got = FX.caption_side((160, 160), (1258, 1330), (0, 486, 1080, 1434), (face,), why=why)
    assert got is not None and (got[2] <= 200 or got[0] >= 880), (got, why)               # 왼쪽 또는 오른쪽 끝
    assert len(why) >= 2 and all("얼굴 겹침" in w for w in why[:2])                         # 가운데 위·아래는 막혔다고 적힘


def test_anchor_reaches_locate_target():
    st = copy.deepcopy(ST.load("잇템로그판"))
    st["placement"]["rules"].pop("deco_pos", None)
    st["placement"]["rules"]["stickers"] = {"circle_arrow": {"target": "face", "avoid": [], "role": ["훅"], "anchor": "mouth", "why": "시험"}}
    rid = PL.reference(st, "ep13")["id"]
    st["placement"]["reference"] = rid
    for v in st["placement"]["counted"]["videos"]:
        if v["id"] == rid:
            v["stickers"] = {"circle_arrow": 1}
    seen = []
    PL.place(_rows(), st, "ep13", locate=lambda tg, row, s: seen.append(tg) or {"x": 50, "y": 50, "w": 90, "h": 90, "conf": 0.9, "face_clear": True})
    assert seen and seen[0].get("anchor") == "mouth", seen
