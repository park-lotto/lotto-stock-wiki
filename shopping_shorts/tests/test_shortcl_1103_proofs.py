"""11-03 숏클 수리 증명 시험(관제 318, 대기실 전수조사 11-04).

같이 넣었던 시험 셋은 수리를 되돌려도 통과하거나(08·09) 이름 때문에만 실패했다(13), 14 는 시험이 없었다.
여기 시험은 전부 '수리를 되돌린 코드에서 실패'를 실측한 뒤 넣었다 — 결함이 다시 생기면 이 시험이 막는다.
"""
import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

from tools.calcopy.hybrid import material_fit as MF


def _gray(p: Path, sec: int = 10) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=gray:s=64x64:d={sec}:r=30",
                    "-c:v", "libx264", "-preset", "ultrafast", str(p)], check=True)


@pytest.mark.parametrize("ss_b", [1.0, 1.5])
def test_08_reuse_only_cut_stays_when_another_shot_is_free(monkeypatch, tmp_path, ss_b):
    """A-08 f005627b5(김만기·김형관 팥→크림): 다른 샷에 빈자리가 있어도 재사용(B13, 경고)만 걸린 컷은 옮기지 않는다.
    빈 구간이 [0,3]·[5,10] 둘이어야 수리 전 코드가 5.4초(다른 샷)로 옮긴다 — 하나뿐이면 수리 전에도 못 옮겨 아무것도 안 잰다."""
    from tools.calcopy.hybrid import runner_ops as R
    _gray(tmp_path / "v.mp4")
    monkeypatch.setattr(R, "jump_free_spans", lambda src, spans, **k: [[0.0, 3.0], [5.0, 10.0]])
    monkeypatch.setattr(R, "_cut_jumps", lambda *a, **k: [])
    a = {"line": "E1", "t0": 0.0, "t1": 1.0, "dur": 1.0, "kind": "tts", "src": "v.mp4", "ss": 1.0}
    b = {"line": "E2", "t0": 1.0, "t1": 2.0, "dur": 1.0, "kind": "tts", "src": "v.mp4", "ss": ss_b, "reuse_unfixed": ["겹침"]}
    cuts = [a, b]
    MF.relocate_cuts(cuts, tmp_path, set(), log=lambda m: None, end=2.0)
    assert cuts == [a, b]
    assert b["ss"] == ss_b and "ss_moved" not in b


def test_09_engine_swap_waits_for_other_window_rent():
    """A-09 c1d656289(김효준 '판이 없다' 3번): 엔진 통째 교체(applyUpdate)는 engine/ 안의 빌린 판(styles)을 없앤다 —
    그래서 교체 신호와 받자마자 교체 둘 다 이 PC 어느 창이든 빌림 중(renting = rent.lock)이면 미뤄야 한다."""
    root = Path(__file__).resolve().parents[2] / "shortem_client" / "server"
    idx = (root / "index.js").read_text(encoding="utf-8")
    upd = (root / "updater.js").read_text(encoding="utf-8")
    swap = [ln for ln in idx.splitlines() if "process.send({ swap: 1 })" in ln]
    assert swap and all("!renting()" in ln for ln in swap), swap
    apply = [ln for ln in upd.splitlines() if ln.strip().startswith("applyDownloaded(")]
    assert apply and all("renting()" in ln for ln in apply), apply


def test_09_swap_really_drops_rented_styles(tmp_path):
    """09 의 전제 실측 — applyUpdate 가 engine 폴더를 바꾸면 빌린 판 폴더가 사라진다(이 전제가 바뀌면 위 미루기 판단도 다시 본다)."""
    probe = tmp_path / "probe.mjs"
    sup = (Path(__file__).resolve().parents[2] / "shortem_client" / "server" / "supervisor.js").as_uri()
    probe.write_text("""
import fs from 'node:fs'; import path from 'node:path';
const home = process.argv[2];
const mk = (p, t='x') => { fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, t); };
mk(path.join(home, 'engine/tools/calcopy/make.py'));
mk(path.join(home, 'engine/tools/calcopy/hybrid/styles/rented_v2/frame.json'));
mk(path.join(home, 'engine/tools/calcopy/hybrid/styles/.rented'));
mk(path.join(home, 'server/index.js'));
for (const d of ['server/index.js', 'engine/tools/calcopy/make.py']) mk(path.join(home, '_update/9.9.9', d));
mk(path.join(home, '_update/9.9.9/app_version.json'), '{"version":"9.9.9"}');
mk(path.join(home, '_update/pending.json'), JSON.stringify({ version: '9.9.9', dir: '9.9.9' }));
process.env.SHORTEM_HOME = home;
const S = await import(process.argv[3]);
const v = S.applyUpdate(home);
console.log(JSON.stringify({ v, after: fs.existsSync(path.join(home, 'engine/tools/calcopy/hybrid/styles/rented_v2/frame.json')) }));
""", encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir()
    r = subprocess.run(["node", str(probe), str(home), sup], capture_output=True, text=True, encoding="utf-8", timeout=60)
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out == {"v": "9.9.9", "after": False}


def test_13_basic_key_sends_basic_from_second_episode(tmp_path, monkeypatch):
    """A-13 c1ede660a(사장님 11-03): 고급이 거절된 키는 편 3개 = [고급,기본]·[기본]·[기본]. 수리 전 = 편마다 [고급,기본]."""
    from tools.calcopy import vmake_clean as VC
    kf = tmp_path / "vmake"
    kf.write_text("old:key", encoding="utf-8")
    monkeypatch.setattr(VC, "MEMBER_KEY_FILE", kf)
    if hasattr(VC, "TIER_FILE"):
        monkeypatch.setattr(VC, "TIER_FILE", tmp_path / "vmake.tier")
    monkeypatch.setattr(VC, "paid_off", lambda: False)
    monkeypatch.delenv("VMAKE_API_KEY", raising=False)
    sent = []

    def remove_subtitles(src, key, dst, tier="pro", resume_key=""):
        sent.append(tier)
        if tier != "basic":
            raise RuntimeError("Switch to New API")
        open(dst, "wb").write(b"x")
    fake = types.SimpleNamespace(remove_subtitles=remove_subtitles)
    import shopping_shorts
    monkeypatch.setitem(sys.modules, "shopping_shorts.vmake_client", fake)
    monkeypatch.setattr(shopping_shorts, "vmake_client", fake, raising=False)
    monkeypatch.setattr(VC, "swap_in", lambda f, tmp: None)
    monkeypatch.setattr(VC, "log_entry", lambda *a, **k: None)
    monkeypatch.setattr(VC, "_sent", lambda f: {})
    f = tmp_path / "a.mp4"
    f.write_bytes(b"v")
    eps = []
    for _ in range(3):
        sent.clear()
        VC.member_clean([f], "old:key", log=lambda *_: None, tier="pro")
        eps.append(list(sent))
    assert eps == [["pro", "basic"], ["basic"], ["basic"]]


def test_14_erase_gate_counts_text_under_blur(tmp_path):
    """A-14 5ae67c81c(#3344·#3445 김준용 VMake 0회): 지우는 판 관문④는 흐림 칸에 덮인 글자도 지울 컷으로 센다.
    진짜 영상·진짜 글자 인식 — 수리 전 코드는 흐림 칸이 있으면 erase [] (VMake 0회)."""
    from tools.calcopy.hybrid import render_bench as RB
    cand = tmp_path / "cand"
    cand.mkdir()
    font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf"
    if not font.exists():
        pytest.skip("글자 박을 글꼴 없음")
    (tmp_path / "f.ttf").write_bytes(font.read_bytes())       # drawtext 는 짧은 상대 경로가 안전하다(드라이브 콜론·한글 경로)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x406080:s=720x1280:d=6:r=30",
                    "-vf", "drawtext=fontfile=f.ttf:text='COSTCO SALE 13990 WON':fontsize=64:fontcolor=white:borderw=4:x=(w-tw)/2:y=1050",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(cand / "a.mp4")], check=True, cwd=tmp_path)
    T = {"cuts": [{"src": "a.mp4", "ss": 1.0, "t0": 0.0, "t1": 2.0, "dur": 2.0, "line": "L1", "kind": "tts"}], "end": 2.0}
    st = {"frame": {"kind": "window", "window": [0, 0, 720, 1280]}}
    got = {}
    for name, blur in (("plain", None), ("blurred", [[0, 1000, 720, 180, 0.0, 6.0]])):
        M = {"cand_dir": str(cand)}
        if blur:
            M["blur"] = {"a.mp4": blur}
        erase = []
        RB.cut_content_gate(T, M, st, None, None, log=lambda *a: None, erase=erase)
        got[name] = erase
    assert got["plain"] == [0], got          # 글자 인식이 이 글자를 잡는다(못 잡으면 아래 비교가 아무것도 안 잰다)
    assert got["blurred"] == [0], got


def test_318_server_leaves_shot_cap_to_render(tmp_path):
    """관제 318 '컷 길이·장면 경계 3번 연속'(#2976 외 6명): 서버 fill_shot_max 가 거친 샷 표로 max 를 채우면
    렌더 shot_cap(관문과 같은 경계 shot_starts — max 가 비었을 때만 돈다)이 막히고 회원이 줄인 max 를 다시 늘린다.
    → 서버는 max 를 쓰지 않고, 회원이 직접 적은 max 는 그대로 둔다. 렌더는 비어 있는 max 에 관문 경계 한도를 붙인다."""
    from tools.calcopy.hybrid import rules as RU
    from tools.calcopy.hybrid import render_bench as RB
    shots = {"o": [{"i": 0, "a": 0.0, "b": 20.0, "who": "main", "cx": 0.5}]}       # 거친 샷 표: 0~20초 한 샷
    M = {"cuts": {"N1": [{"src": "o.mp4", "ss": 5.6}], "N2": [{"src": "o.mp4", "ss": 1.0, "max": 1.5}]}}
    RU.fill_shot_max(M, None, {"o.mp4": [1920, 1080]}, shots, 9 / 16)
    assert "max" not in M["cuts"]["N1"][0]                 # 수리 전: 14.4(샷 표 끝까지)
    assert M["cuts"]["N2"][0]["max"] == 1.5                # 회원이 적은 한도는 그대로(수리 전: 19.0 으로 늘림)
    # 렌더 쪽: 비어 있는 max 에 shot_starts(관문 경계)로 한도 — 0~3·3~10 두 샷 영상
    v = tmp_path / "o.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x180:d=3:r=30", "-f", "lavfi", "-i",
                    "color=c=white:s=320x180:d=7:r=30", "-filter_complex", "[0][1]concat=n=2:v=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(v)], check=True)
    c = {"src": "o.mp4", "ss": 1.0}
    RB.shot_cap(c, v)
    assert c.get("max_auto") and c["max"] is not None and abs(c["max"] - 2.0) < 0.1, c


def test_318_jamo_line_cache_survives_edit(tmp_path, monkeypatch):
    """관제 318 #3253(임영미 썰템쇼 '반복 막힘'): 회원 목소리 길(make_synth)은 ㅋㅋ·ㄷㄷ 를 빼고 합성한다 — 돌려받은 글자 시각을
    원문(대본 tts) 글자로 되끼우지 않으면 1회차는 소리 없이 어긋나고(24자 vs 27자), 다른 줄을 고친 2회차에 그 줄 캐시가
    '글자 시각이 줄 글과 안 맞는다'로 막힌다. 진짜 tts_by_line 으로 두 번 돈다(합성만 가짜 — 받은 글의 글자 시각)."""
    from tools.calcopy.engine import voice_synth as VS
    from tools.calcopy.hybrid import render_bench as RB
    monkeypatch.setenv("CALCOPY_CUSTOMER_MODE", "1")
    sent = []

    def fake_make(provider, voice, tempo, emotion):
        def synth(text, out):
            sent.append(text)
            n = len(text)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=f=300:d={max(0.5, n * 0.08):.2f}",
                            "-c:a", "libmp3lame", str(out)], check=True)
            return {"characters": list(text), "character_start_times_seconds": [i * 0.08 for i in range(n)],
                    "character_end_times_seconds": [(i + 1) * 0.08 for i in range(n)]}
        return synth
    monkeypatch.setattr(VS, "_make_synth", fake_make)
    S = {"voice": {"voice_id": "abcSearchVoice01", "provider": "elevenlabs", "tempo": 1.0},
         "lines": [{"id": "L1", "kind": "tts", "tts": "이거 진짜 대박이다.", "caps": [{"text": "이거 진짜 대박이다."}]},
                   {"id": "L2", "kind": "tts", "tts": "아 또 사러 가야겠다 ㅋㅋ.", "caps": [{"text": "아 또 사러 가야겠다 ㅋㅋ."}]}]}
    R = tmp_path / "R"
    R.mkdir()
    _, align = RB.tts_by_line(S, R, log=lambda m: None)
    assert "".join(align["characters"]) == " ".join(l["tts"] for l in S["lines"])      # 수리 전: 24자(낱자 빠짐) vs 27자
    assert all("ㅋ" not in t for t in sent)                                            # 목소리에는 여전히 빼고 보낸다
    S["lines"][0]["tts"] = "이거 진짜 대박이네."
    _, align = RB.tts_by_line(S, R, log=lambda m: None)                                  # 수리 전: L2 줄 캐시 StageError
    assert "".join(align["characters"]) == " ".join(l["tts"] for l in S["lines"])


def test_318_foreign_origin_low_res_refinds_once_then_stops(monkeypatch):
    """관제 318 #3360(김효준 해외원본형): 480x360 옛 리뷰가 원본으로 정해져 제품 확인까지 감 — 하한이 자막노래형 길에만 있었다.
    받은 원본 높이 < 하한(판 min_h, 없으면 720)이면 빼고, 다 빠지면 원본 확인 탈락과 같은 길로 한 번 더 찾고, 그래도면 멈춘다."""
    from tools.calcopy.hybrid import flow as F
    monkeypatch.setattr(F, "_style", lambda v: {})
    st = {"fmt": "해외원본형", "version": "x", "log": [], "tries": {}, "origins": [{"id": "gPyUKlicXXY", "how": "찾기 같은 촬영분"}]}
    r = F.f_of_fetched(st, {"og_0": {"files": [{"name": "gPyUKlicXXY.mp4", "w": 480, "h": 360, "dur": 60}]}}, {}, {})
    assert r == {"goto": "of_find"} and st["skip_ids"] == ["gPyUKlicXXY"] and "720" in st["of_find_why"] and st["origins"] == []
    st["origins"] = [{"id": "B", "how": "찾기 같은 촬영분"}]
    with pytest.raises(F._Stop):
        F.f_of_fetched(st, {"og_0": {"files": [{"name": "B.mp4", "h": 480, "dur": 60}]}}, {}, {})
    st2 = {"fmt": "해외원본형", "version": "x", "log": [], "tries": {}, "origins": [{"id": "lo", "how": "같은 제품 다른 해외 반응"}, {"id": "hi", "how": "같은 제품 다른 해외 반응"}]}
    F.f_of_fetched(st2, {"og_0": {"files": [{"name": "lo.mp4", "h": 360, "dur": 30}]}, "og_1": {"files": [{"name": "hi.mp4", "h": 1080, "dur": 30}]}}, {}, {})
    assert [o["id"] for o in st2["origins"]] == ["hi"]          # 높은 화질만 남긴다
    st3 = {"fmt": "연예인형", "version": "x", "log": [], "tries": {}, "origins": [{"id": "z", "how": "같은 제품 다른 해외 반응"}]}
    F.f_of_fetched(st3, {"og_0": {"files": [{"name": "z.mp4", "h": 360, "dur": 30}]}}, {}, {})
    assert [o["id"] for o in st3["origins"]] == ["z"]            # 하한 없는 형식은 그대로
