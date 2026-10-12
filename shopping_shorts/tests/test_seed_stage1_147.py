"""1단계 씨앗 고르기 + 스토리보드 재료·씨앗 신선도(관제 147, 2026-10-06 사장님).

실사고(work ef07493ca035): 외국 영상 5편이 마지막(3번째) 분석 시도를 도는 중인데 '포기'로 판정돼
스토리보드 미리 만들기가 씨앗 1편 재료로 돌았다 → 장면 목록이 씨앗 조각뿐으로 굳고, AI 자동 보드 9칸이 전부 씨앗,
렌더 뒤 다시 만든 보드는 쓸 조각 0이라 '장면 0초'. 여기 테스트는 전부 **고치기 전 코드에서 실패**한다.
"""
import json
import pathlib
import re

from shopping_shorts import app as ap, mix_pipeline, storyboard as sb

HTML = (pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


def _src(vid, n=3):
    return {"segments": [{"seg_id": f"{vid}-{i}", "start": i * 2.0, "end": i * 2.0 + 2.0, "scene_desc": f"{vid} 장면{i}"}
                         for i in range(n)]}


class _FakeStore:
    def __init__(self, att, err="", age=None):
        self.info = {"attempts": att, "last_error": err, "age_sec": age}

    def get_script(self, code):
        return None

    def autoload_status(self, codes):
        return {codes[0]: self.info}

    def queue_has_pending(self, *a):
        return False


# ── ① 마지막 시도가 도는 중이면 '포기'가 아니다 ──
def test_last_attempt_running_is_not_gave_up():
    _d, st = ap._analysis_state(_FakeStore(3, age=86), "grab_instagram_x")      # 실측: 시작 86초 뒤
    assert st["state"] != "gave_up"


def test_last_attempt_stalled_long_is_gave_up():
    _d, st = ap._analysis_state(_FakeStore(3, age=ap._AUTOLOAD_STALL_SEC + 1), "grab_instagram_x")
    assert st["state"] == "gave_up"


def test_hard_error_still_gives_up_immediately():
    _d, st = ap._analysis_state(_FakeStore(3, err="boom", age=5), "grab_instagram_x")
    assert st["state"] == "gave_up"


# ── ② 장면 목록 = 씨앗 포함 재료 전체 + 재료 지문 ──
def _patch_sb(monkeypatch, tmp_path, calls):
    fam = {"names": ["시험 스타일"], "roles": ["hook", "result"], "chain": [], "tpl": {}, "fit": set(), "arc": "", "sit": ""}
    monkeypatch.setattr(sb, "_ro", lambda p: None)
    monkeypatch.setattr(sb, "_families", lambda db: [(5, fam, "  5: 시험")])
    monkeypatch.setattr(sb, "_state_path", lambda jid: str(tmp_path / ("%s.json" % jid)))

    def fake_call(prompt, schema, note=None, vertex=False):
        if "groups" in json.dumps(schema):
            ids = re.findall(r"^\s+(\S+-\d+) \|", prompt, re.M)
            calls.append(("inv", ids))
            return {"kind": "뷰티", "groups": [{"name": "묶음", "ids": ids}], "tags": [], "missing": []}
        return {"styles": []}
    monkeypatch.setattr(sb.sg, "_call_json", fake_call)

    def fake_board(fam_, pan, r1, groups_txt, star, segs, texts, **kw):
        calls.append(("board", groups_txt, set(segs)))
        return {"slots": [{"slot": "hook", "ids": [next(iter(segs))], "line": "x"}]}
    monkeypatch.setattr(sb, "_board", fake_board)


def test_inventory_groups_include_seed_and_record_mat_sig(monkeypatch, tmp_path):
    calls = []
    _patch_sb(monkeypatch, tmp_path, calls)
    ex = {"SEED": _src("SEED"), "B": _src("B")}
    mix_pipeline.mark_seed_sources(ex, ["SEED"])
    R = sb.inventory(None, "w-t", ex=ex)
    got = {c for g in R["inventory"]["groups"] for c in g["ids"]}
    assert {"SEED-0", "B-0"} <= got                           # 씨앗과 무관하게 재료 전체로 묶는다
    assert R["mat_sig"] == sb.mat_sig(ex) and sb.inventory_fresh(R, ex)


def test_make_boards_rebuilds_stale_inventory_and_drops_seed(monkeypatch, tmp_path):
    calls = []
    _patch_sb(monkeypatch, tmp_path, calls)
    early = {"SEED": _src("SEED")}                               # 사고 그대로: 외국 영상이 들어오기 전 씨앗만
    sb.inventory(None, "w-t", ex=early)
    full = {"SEED": _src("SEED"), "B": _src("B")}
    mix_pipeline.mark_seed_sources(full, ["SEED"])
    out = sb.make_boards(None, "w-t", ["5"], ex=full)
    invs = [c for c in calls if c[0] == "inv"]
    assert "B-0" not in invs[0][1] and "B-0" in invs[-1][1]     # 낡은 목록이면 지금 재료로 다시 묶는다
    board = [c for c in calls if c[0] == "board"][-1]
    assert not any(s.startswith("SEED-") for s in board[2])     # 보드 후보엔 씨앗 조각이 없다
    assert "SEED-" not in board[1]
    assert out["5"]["seed_sig"] == "SEED"


def test_seed_only_group_name_not_offered(monkeypatch, tmp_path):
    calls = []
    _patch_sb(monkeypatch, tmp_path, calls)
    full = {"SEED": _src("SEED"), "B": _src("B")}
    R = {"inventory": {"groups": [{"name": "⭐ 씨앗만", "ids": ["SEED-0"]}, {"name": "B묶음", "ids": ["B-0", "B-1"]}], "tag_of": {}},
         "styles": [], "mat_sig": sb.mat_sig(full)}
    mix_pipeline.mark_seed_sources(full, ["SEED"])
    sb.make_boards(None, "w-t", ["5"], R=R, ex=full)
    groups_txt = [c for c in calls if c[0] == "board"][-1][1]
    assert "씨앗만" not in groups_txt and "B묶음" in groups_txt  # 실으면 모델이 묶음 이름을 장면 번호 자리에 적는다


def test_seed_sig_tracks_seed_choice():
    a = {"A": _src("A"), "B": _src("B")}
    b = {"A": _src("A"), "B": _src("B")}
    mix_pipeline.mark_seed_sources(a, ["A"])
    mix_pipeline.mark_seed_sources(b, ["B"])
    assert sb.seed_sig(a) != sb.seed_sig(b) and sb.mat_sig(a) == sb.mat_sig(b)


# ── ③ 화면: 씨앗 표식의 주인은 seedSync 하나, 미리 만들기는 씨앗·재료가 바뀌면 다시 묻는다 ──
def test_seed_flag_has_one_owner_in_html():
    sets = [m.start() for m in re.finditer(r"seedNoAuto\s*=\s*true", HTML)]
    owner = HTML.index("function seedSync(")
    migrate = HTML.index("function _migrateSeedFlags(")
    assert all(owner < p < owner + 1500 or migrate < p < migrate + 400 for p in sets), sets
    for fn in ("function pickFootage(", "function s2PickSeed(", "function dropFootage("):
        body = HTML[HTML.index(fn): HTML.index(fn) + 900]
        assert "seedSync()" in body, fn
    ai = HTML.index("window._aiPick = d;")
    assert "seedSync()" in HTML[ai: ai + 200]                   # 자동 AI PICK 도 씨앗


def test_prepare_key_follows_seed_and_retries_while_waiting():
    body = HTML[HTML.index("async function sbPrepare("): HTML.index("async function sbMakeInventory(")]
    assert "_sbPrepKey(" in body and "d.waiting" in body
    assert "_SB_PREP===j" not in body                           # 종전: 작업당 한 번만 → 씨앗이 바뀌어도 안 물었다
