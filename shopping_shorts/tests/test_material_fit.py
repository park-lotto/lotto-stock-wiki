# -*- coding: utf-8 -*-
"""장면↔대사 계획 매칭 루프(tools/calcopy/hybrid/material_fit.py) 시험 — 관제 263 지시서 14.

① 제약 위반 후보(원음 고정 컷과 재사용)는 **점수 전에** 빠진다(채점 그림에 안 실린다)
② 하한 9 → 루프가 3회 돌고 '멈춤(사유: 줄 …)'으로 끝난다(무한 루프·조용한 통과 0)
③ gold 10컷 실측 점수(judge_rubric, 10-25) — 틀린 자막(low)엔 어떤 그림도 하한을 못 넘고, 맞는 자막(high)엔 넘는다(혼동 0)
④ 대사↔장면 판정 한 벌 — material_auto.fit_judge 가 scene_fit.RUBRIC 으로 묻는다(옛 7/4/1 프롬프트 없음)
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.calcopy.hybrid import material_fit as MF
from tools.calcopy.engine import material_auto as MA

FIX = Path(__file__).parent / "fixtures"
pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 없음")


def _src(p: Path):
    """4색 × 5초 = 샷 4개(0~5 빨강·5~10 파랑·10~15 초록·15~20 노랑)."""
    cols = ["red", "blue", "green", "yellow"]
    args = ["ffmpeg", "-v", "error", "-y"]
    for c in cols:
        args += ["-f", "lavfi", "-i", f"color=c={c}:s=360x640:d=5:r=30"]
    args += ["-filter_complex", "".join(f"[{i}:v]" for i in range(4)) + "concat=n=4:v=1:a=0[v]", "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(p)]
    subprocess.run(args, check=True, stdin=subprocess.DEVNULL)


def _ep(tmp: Path, n2_role="본문"):
    W = tmp / "w"
    (W / "src").mkdir(parents=True)
    (W / "render").mkdir()
    D = tmp / "doc"
    D.mkdir()
    _src(W / "src" / "a.mp4")
    S = {"product": "시험 상자", "lines": [
        {"id": "N1", "kind": "tts", "role": "나레 훅", "tts": "빨간 화면이 보여요.", "caps": [{"text": "빨간 화면이"}, {"text": "보여요"}]},
        {"id": "O1", "kind": "orig", "role": "원음", "src": "a.mp4", "spans": [[6.0, 8.0]], "caps_rel": [["원음", 0.0, 2.0]]},
        {"id": "N2", "kind": "tts", "role": f"나레 {n2_role}", "tts": "초록 화면이 나와요.", "caps": [{"text": "초록 화면이"}, {"text": "나와요"}]}]}
    M = {"cand_dir": str(W / "src"), "cuts": {"N1": [{"src": "a.mp4", "ss": 0.5, "crop": [0, 0, 360, 640], "see": "빨강"}],
                                              "N2": [{"src": "a.mp4", "ss": 6.5, "crop": [0, 0, 360, 640], "see": "파랑(원음 구간 재사용 — 위반)"}]}}
    T = {"lines": {"N1": [0.0, 2.0], "O1": [2.0, 4.0], "N2": [4.0, 6.0]}, "end": 6.0,
         "rows": [{"line": "N1", "text": "빨간 화면이", "t0": 0.0, "t1": 1.0}, {"line": "N1", "text": "보여요", "t0": 1.0, "t1": 2.0},
                  {"line": "O1", "text": "원음", "t0": 2.0, "t1": 4.0},
                  {"line": "N2", "text": "초록 화면이", "t0": 4.0, "t1": 5.0}, {"line": "N2", "text": "나와요", "t0": 5.0, "t1": 6.0}],
         "cuts": [{"src": "a.mp4", "ss": 6.0, "line": "O1", "kind": "orig", "t0": 2.0, "t1": 4.0, "dur": 2.0, "crop": [0, 0, 360, 640]}]}
    (D / "대본.json").write_text(json.dumps(S, ensure_ascii=False), encoding="utf-8")
    (D / "재료.json").write_text(json.dumps(M, ensure_ascii=False), encoding="utf-8")
    (W / "render" / "timeline.json").write_text(json.dumps(T, ensure_ascii=False), encoding="utf-8")
    return D, W


class Fake:
    """샷 설명·순위·채점·고침을 흉내 — 채점 칸마다 그림 띠를 기록한다(점수 전에 빠졌나 보려고)."""

    def __init__(self, score=7, fix=True, prod=None, ident=None):
        self.score, self.fix, self.sheets, self.fit_rows, self.prod, self.ident = score, fix, 0, [], prod or {}, ident

    def __call__(self, parts, prompt, tag):
        if tag == "ma_fit:shot":
            hi = int(re.search(r"번호 0~(\d+)", prompt).group(1))
            return {"shots": [{"n": i, "desc": f"단색 화면 {i}"} for i in range(hi + 1)]}, None
        if tag == "ma_fit:product":
            hi = int(re.search(r"번호 0~(\d+)", prompt).group(1))
            return {"shots": [{"n": i, "p": self.prod.get(i, "same")} for i in range(hi + 1)]}, None
        if tag == "ma_fit:ident":
            if not self.ident:
                return None, "no"
            return self.ident, None
        if tag == "ma_fit:rewrite":
            return {"same": True, "changed": []}, None
        if tag == "ma_fit:rank":
            ids = re.findall(r"^(\w+#\d+):", prompt, re.M)
            lines = re.findall(r"^(N\d+):", prompt, re.M)
            return {"lines": [{"id": l, "shots": ids} for l in lines]}, None
        if tag == "ma_fit:fix":
            if not self.fix:
                return None, "no"
            old = re.search(r"\[원문 대사\] (.+)", prompt).group(1)
            a, b = ("가득이", "꽉이") if "가득이" in old else (("꽉이", "가득이") if "꽉이" in old else ("화면이", "화면 가득이"))
            new = old.replace(a, b)
            caps = re.search(r"\[원문 자막 덩어리\] (\[.*\])", prompt).group(1)
            cl = json.loads(caps.replace("'", '"'))
            cl[0] = cl[0].replace(a, b)
            return {"tts": new, "caps": cl, "why": "시험"}, None
        self.sheets += 1
        self.fit_rows += re.findall(r"^\d+: «", prompt, re.M)
        n = len(re.findall(r"^\d+: «", prompt, re.M))
        return {"fits": [{"n": i, "score": self.score, "seen": "단색"} for i in range(n)]}, None


def test_constraint_violation_removed_before_scoring(tmp_path):
    """사람 컷 N2(a.mp4 6.5초~) = 원음 O1(6~8초) 구간 재사용 → 제외 이유 reuse, 고르지 않는다(점수는 비교용으로만)."""
    D, W = _ep(tmp_path)
    r = MF.plan(D, W, "잇템로그판", llm=MA.LLM(Fake()), do_supplement=False)
    n2 = next(x for x in r["lines"] if x["id"] == "N2#0")
    assert any(abs(c["ss"] - 6.5) < 0.01 and "reuse" in c["why"] for c in n2["rejected"])
    assert n2["pick"] and abs(n2["pick"]["ss"] - 6.5) > 0.4            # 위반 사람 컷은 안 고른다
    # 원음 구간(6~8 ±거리) 안의 순위 후보는 채점 시트에 아예 안 실린다(사람 컷 1개만 비교용으로 실림)
    cands = json.loads((D / "장면대사_계획.json").read_text(encoding="utf-8"))
    assert cands["lines"][2]["cand_n"] >= 2


def test_floor9_loops_three_times_then_stops(tmp_path):
    """사보타주: 하한 9(어떤 후보도 못 넘음) + 대사 고침 자동 사인 → 3회 돌고 '멈춤(사유: … 줄 …)'."""
    D, W = _ep(tmp_path)
    r = MF.plan(D, W, "잇템로그판", llm=MA.LLM(Fake(score=7)), do_supplement=False, sign=True, floors={"hi": 9, "lo": 9})
    assert len(r["rounds"]) == 3 and not r["ok"]
    assert r["stop"].startswith("멈춤(사유: 3회") and "N1" in r["stop"] and "N2" in r["stop"]
    assert r["needs_tts"]                      # 고친 대사 = 새 합성 필요 목록(합성은 안 한다)


def test_floor_default_passes_and_writes_material(tmp_path):
    D, W = _ep(tmp_path)
    r = MF.plan(D, W, "잇템로그판", llm=MA.LLM(Fake(score=10)), do_supplement=False)
    assert r["ok"] and len(r["rounds"]) == 1 and r["stop"] is None
    M2 = json.loads((D / "재료_계획.json").read_text(encoding="utf-8"))
    assert all(c.get("fit") == 10 and c.get("cand_n") for c in M2["cuts"]["N2"])
    assert not (D / "재료_사람.json").exists()                          # --apply 없으면 재료.json 안 바꿈


def test_floor_of_roles():
    assert MF.floor_of("나레 공개") == 7 and MF.floor_of("증거") == 7 and MF.floor_of("나레 훅(빨강)") == 5
    assert MF.floor_of("끝 — 전언") == 5 and MF.floor_of("이음") == 5 and MF.floor_of("나레 성분") == 7


def test_gold_real_scores_no_confusion():
    """합격 ①: gold 10컷 그림이 후보인 칸 — 틀린 자막(low 3)엔 최고점이 하한(7) 미만이라 '통과'로 안 고르고, 맞는 자막(high 3)엔 하한 넘는 컷을 고른다.
    점수 = 10-25 judge_rubric 실측(Claude 소넷 2회 중앙값, fixtures/material_fit_gold_scores.json)."""
    G = json.loads((FIX / "material_fit_gold_scores.json").read_text(encoding="utf-8"))
    assert len(G["rows"]) == 6
    for r in G["rows"]:
        slot = {"id": f"L{r['cap_of']}#0", "line": f"L{r['cap_of']}", "kind": "tts", "role": "본문", "t0": 0.0, "t1": 1.0,
                "cands": [{"src": f"g{k}.mp4", "ss": 0.0, "dur": 1.0, "score": s, "from": f"rank{k}"} for k, s in enumerate(r["scores"]) if s is not None]}
        sel = MF.select([slot], {})[0]
        if r["gold"] == "low":
            assert sel["below"], (r["piece"], r["scores"])
        else:
            assert not sel["below"], (r["piece"], r["scores"])


def test_fit_judge_is_rubric_shell(tmp_path):
    """대사↔장면 프롬프트 한 벌 — fit_judge 가 scene_fit.RUBRIC(기준점 10/7/5/3/1)으로 묻는다."""
    from tools.calcopy.oneshot import scene_fit as SF
    seen = []

    def fake(parts, prompt, tag):
        seen.append(prompt)
        return {"fits": [{"n": 0, "score": 7, "seen": "a"}]}, None
    r = MA.fit_judge([{"img": "", "piece": "x", "line": "x"}], tmp_path, MA.LLM(fake), tag="t")
    assert r[0]["score"] == 7 and seen and all(p.startswith(SF.RUBRIC.split("\n")[0]) for p in seen)
    assert not hasattr(MA, "FIT_PROMPT")


def test_outside_source_with_burned_text_rejected(tmp_path):
    """원본 밖 재료(보충) 샷에 덧씌운 글자가 있거나 판독을 못 했으면 채점 전 제외(text_box) — 10-25 ep13 남의 자막 두 겹 렌더."""
    table = {"sup_/x.mp4": {"dur": 20.0, "shots": [{"i": 0, "a": 0.0, "b": 10.0}, {"i": 1, "a": 10.0, "b": 20.0}]}}
    cand = {"src": "sup_/x.mp4", "ss": 2.0, "dur": 2.0, "t0": 0.0, "t1": 2.0, "line": "N1", "shot": "x#0", "_path": tmp_path / "x.mp4"}
    out = {"sup_/x.mp4"}
    MF._FACE_LOCK  # 얼굴 검사는 work=None 이면 건너뜀
    assert "text_box" in MF.constraint_flags(cand, table, [], {}, out, None, {"x#0": True})["reject"]
    assert "text_box" in MF.constraint_flags(cand, table, [], {}, out, None, {})["reject"]          # 판독 못 함 = 못 씀
    assert "text_box" not in MF.constraint_flags(cand, table, [], {}, out, None, {"x#0": False})["reject"]
    assert "text_box" not in MF.constraint_flags({**cand, "src": "d2.mp4"}, {"d2.mp4": table["sup_/x.mp4"]}, [], {}, out, None, {})["reject"]   # 원본은 안 봄


def test_other_product_and_exclude_removed_before_scoring(tmp_path):
    """하드 제약 층(표준 §11-4 ㉔ⓔ): 제품 판정 'other' 샷(초록 10~15초)·사람 제외 구간(노랑 15~20초)은 후보에서 빠진다 — 금색 캡슐 통 재발 방지."""
    D, W = _ep(tmp_path)
    M = json.loads((D / "재료.json").read_text(encoding="utf-8"))
    M["exclude"] = [{"src": "a.mp4", "t0": 15.0, "t1": 20.0, "why": "노랑 = 다른 제품(사람 메모)"}]
    (D / "재료.json").write_text(json.dumps(M, ensure_ascii=False), encoding="utf-8")
    r = MF.plan(D, W, "잇템로그판", llm=MA.LLM(Fake(score=10, prod={2: "other"})), do_supplement=False)
    picks = [x["pick"] for x in r["lines"] if x["kind"] == "tts" and x["pick"]]
    assert picks and all(not (10.0 - 2 < p["ss"] < 20.0) for p in picks), picks
    why = [w for x in r["lines"] for c in x["rejected"] for w in c["why"]]
    assert "other_product" in why and "excluded" in why


def test_dead_end_stops_not_violates(tmp_path):
    """막다른 칸(제약 안 후보 0)은 위반 컷을 남기지 않고 범위를 넓힌 뒤에도 없으면 '멈춤(사유: 막다른 칸 …)' — 조용한 통과 0."""
    D, W = _ep(tmp_path)
    M = json.loads((D / "재료.json").read_text(encoding="utf-8"))
    M["exclude"] = [{"src": "a.mp4", "t0": 0.0, "t1": 20.0, "why": "전부 제외(시험)"}]
    (D / "재료.json").write_text(json.dumps(M, ensure_ascii=False), encoding="utf-8")
    r = MF.plan(D, W, "잇템로그판", llm=MA.LLM(Fake(score=10)), do_supplement=False)
    assert not r["ok"] and "막다른 칸" in (r["stop"] or "")
    assert all(x["pick"] is None for x in r["lines"] if x["kind"] == "tts")


def test_rewrite_check_keeps_info_words():
    """㉖ 뜻 유지 — 원문 + 덧붙임만 통과. 10-25 실제 제안 3개는 걸러져야 한다."""
    ok = MF.rewrite_check("댓글 보니까 캡슐은 한두 알이면 충분하다던데,", "댓글 보니까 이 캡슐은 한두 알이면 충분하다던데,")
    assert ok["ok"]
    for old, new in [("댓글 보니까 캡슐은 한두 알이면 충분하다던데,", "댓글 보니까 이 알갱이가 얼굴에 붙는다던데,"),
                     ("딸기 버블티 펄 같다는 사람도 있다고 하고.", "딸기 버블티 펄 닮았다는 사람도 있다고 하고."),
                     ("캡슐은 두알이면 충분", "캡슐은 세알이면 충분")]:
        assert not MF.rewrite_check(old, new)["ok"], new
    def no(parts, prompt, tag):
        return {"same": False, "changed": ["충분"]}, None
    assert not MF.rewrite_check("캡슐은 두 알이면 충분", "이 캡슐은 두 알이면 충분", llm=MA.LLM(no))["ok"]    # 역검증 0/2 실패
    seq = iter([{"same": True, "changed": []}, {"same": False, "changed": ["얼굴에"]}, {"same": True, "changed": []}])
    r = MF.rewrite_check("캡슐은 두 알이면 충분", "이 캡슐은 두 알이면 충분", llm=MA.LLM(lambda p, q, t: (next(seq), None)))
    assert r["ok"] and len(r["reverse"]) == 3                                                          # 1/2 로 갈리면 3회째 → 2/3 통과(㊳)


def test_identity_other_person_line_skips_same_person(tmp_path):
    """㊱ 인물 동일성 = 점수 전 제약: '다른 사람' 줄(N2)엔 앞 원음(O1, 파랑 샷 = P1)과 같은 사람 샷이 못 온다 → P2(초록 10~15초)만."""
    D, W = _ep(tmp_path)
    ident = {"shots": [{"n": 0, "person": "P1", "objects": []}, {"n": 1, "person": "P1", "objects": []},
                       {"n": 2, "person": "P2", "objects": []}, {"n": 3, "person": "P1", "objects": []}],
             "lines": [{"id": "N1", "person": "any", "object": "none"}, {"id": "O1", "person": "any", "object": "none"},
                       {"id": "N2", "person": "other", "object": "none"}]}
    r = MF.plan(D, W, "잇템로그판", llm=MA.LLM(Fake(score=10, ident=ident)), do_supplement=False)
    n2 = next(x for x in r["lines"] if x["id"] == "N2#0")
    assert n2["pick"] and 10.0 <= n2["pick"]["ss"] < 15.0, n2["pick"]
    assert any("identity" in c["why"] for c in n2["rejected"])


def test_rewrite_check_length_mode_n1():
    """㉛ 보강: 글자 수 수정 = length 모드(정보 낱말·조사 유지·facts·tts_chars·audit). ep13 N1 ①'(연결어 '만든' 접기) ○ · ①(조사 제거) ×(A13)."""
    old = "연어로 만든 한국 크림을 얼굴에 바르고 경악한 외국인이 있다는데요?"
    ok = MF.rewrite_check(old, "한국 연어 크림을 얼굴에 바르고 경악한 외국인이 있다는데요?", mode="length", audit_ok=True, max_chars=26)
    assert ok["ok"], ok
    bad = MF.rewrite_check(old, "연어로 만든 한국 크림 얼굴에 바르고 경악한 외국인 있다는데요?", mode="length", audit_ok=True, max_chars=26)
    assert not bad["ok"] and not bad["checks"]["particles_kept"]
    assert not MF.rewrite_check(old, "한국 크림을 얼굴에 바르고 경악한 외국인이 있다는데요?", mode="length", audit_ok=True, max_chars=26)["ok"]   # '연어' 빠짐
    assert not MF.rewrite_check(old, "한국 연어 크림을 얼굴에 바르고 경악한 외국인이 있다는데요?", mode="length", audit_ok=False, max_chars=26)["ok"]
    assert not MF.rewrite_check(old, "한국 연어 크림을 얼굴에 바르고 경악한 외국인이 있다는데요?", mode="scene")["ok"]                     # 장면 모드는 어순 보존이라 ×
