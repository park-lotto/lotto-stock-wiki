"""설치판·업데이트 묶음 수리(11-02) — 부품 검사 순서·_vendor 오탐·금색 로고·판독 모델 자리."""
import ast
import io
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "claude_portal"))
import engine_bundle as EB  # noqa: E402
import engine_deps_check as DC  # noqa: E402
import publish_update as PU  # noqa: E402

OVERLAY = ROOT / EB.OVERLAY_SRC


def _main_calls() -> list[str]:
    tree = ast.parse((ROOT / "installer/win/build_win.py").read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    return [n.func.id for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]


def test_부품검사는_묶음을_만들기_전에_한_번():
    calls = _main_calls()
    assert calls.count("vendor_and_check") == 1
    i = calls.index("vendor_and_check")
    assert i > calls.index("build_engine")
    assert i < calls.index("make_pack_zip") and i < calls.index("nsis") and i < calls.index("build_mcpb")


def test_부품검사는_vendor_안을_재지_않고_엔진은_잰다(tmp_path, capsys):
    (tmp_path / "_vendor" / "pk").mkdir(parents=True)
    (tmp_path / "_vendor" / "pk" / "__init__.py").write_text("import aiohttp_없는것\n", encoding="utf-8")
    (tmp_path / "a.py").write_text("import pk\n", encoding="utf-8")
    assert DC.main(str(tmp_path)) == 0
    (tmp_path / "b.py").write_text("import 없는_부품\n", encoding="utf-8")
    assert DC.main(str(tmp_path)) == 1
    assert "없는_부품" in capsys.readouterr().out


def test_부품검사_vendor_이름이_엔진_빈칸을_가리지_않는다(tmp_path):
    (tmp_path / "_vendor" / "pk").mkdir(parents=True)
    (tmp_path / "_vendor" / "pk" / "helper_only_in_vendor.py").write_text("", encoding="utf-8")
    (tmp_path / "a.py").write_text("import helper_only_in_vendor\n", encoding="utf-8")
    assert DC.main(str(tmp_path)) == 1


@pytest.mark.skipif(not OVERLAY.is_file(), reason="프리셋 폴더 없음")
def test_금색로고_축소본은_로고만_있고_노하우가_없다():
    src = EB.member_overlay(OVERLAY.read_text(encoding="utf-8"))
    names = {n.name for n in ast.parse(src).body if isinstance(n, ast.FunctionDef)}
    assert names == {"_font", "star", "gold", "logo_layer"}
    for word in ("to_frame", "title_layer", "watermark_layer", "실측 근거", "Cafe24Ohsquare", "calcopy_frame"):
        assert word not in src
    assert EB.forbidden(EB.OVERLAY_DST) is None
    assert EB.forbidden(EB.OVERLAY_SRC) == "channel/*"
    assert not [x for x in EB.data_extra(ROOT) if x.startswith("channel/")]


def test_금색로고_조각이_없어지면_빌드가_멈춘다():
    with pytest.raises(SystemExit):
        EB.member_overlay("W, H = 1, 2\n")


@pytest.mark.skipif(not OVERLAY.is_file() or not (ROOT / "out/scene-style-ui-showcase.html").is_file(), reason="프리셋·화면 없음")
def test_금색로고_축소본_그림이_원본과_같다():
    sys.path.insert(0, str(OVERLAY.parent))
    orig = __import__("spr_overlay")
    a = Image.new("RGBA", (1080, 1920), (0, 0, 0, 255))
    orig.logo_layer(a, "얜샷템")
    ns = {"__file__": str(ROOT / EB.OVERLAY_DST), "__name__": "member_overlay"}
    exec(compile(EB.member_overlay(OVERLAY.read_text(encoding="utf-8")), "member", "exec"), ns)
    b = Image.new("RGBA", (1080, 1920), (0, 0, 0, 255))
    ns["logo_layer"](b, "얜샷템")
    assert ImageChops.difference(a, b).getbbox() is None
    assert a.getbbox() and a.convert("L").getextrema()[1] > 200          # 빈 그림끼리 같은 것이 아니다


def _stage(tmp_path) -> Path:
    s = tmp_path / "stage"
    for rel in ("server/index.js", "engine/tools/calcopy/make.py", "engine/models/old.onnx", "models/ppocrv5_server_det.onnx",
                "models/whisper/small/model.bin"):
        (s / rel).parent.mkdir(parents=True, exist_ok=True)
        (s / rel).write_bytes(b"x")
    return s


def _names(data: bytes) -> set:
    return set(zipfile.ZipFile(io.BytesIO(data)).namelist())


def test_마지막판을_정하기_전엔_모델을_engine_models_로_싣는다(tmp_path, monkeypatch):
    monkeypatch.setattr(PU, "MODELS_LAST", None)
    monkeypatch.setattr(PU, "vision_model_source", lambda n: tmp_path / "없음" / n)
    names = _names(PU.make_zip(_stage(tmp_path), "1.0.34"))
    assert {"engine/models/old.onnx", "engine/models/ppocrv5_server_det.onnx"} <= names
    assert not [n for n in names if n.startswith("models/")]


def test_마지막판_다음부터는_모델을_뺀다(tmp_path, monkeypatch):
    monkeypatch.setattr(PU, "MODELS_LAST", "1.0.9")
    s = _stage(tmp_path)
    assert "engine/models/ppocrv5_server_det.onnx" in _names(PU.make_zip(s, "1.0.9"))
    names = _names(PU.make_zip(s, "1.0.10"))                                # 숫자 비교(글자 비교면 1.0.10 < 1.0.9)
    assert not [n for n in names if "models/" in n]
    assert "engine/tools/calcopy/make.py" in names


def test_실제_무대에_모델이_없으면_다리판을_만들지_않는다(tmp_path, monkeypatch):
    monkeypatch.setattr(PU, "MODELS_LAST", None)
    monkeypatch.setattr(PU, "vision_model_source", lambda n: tmp_path / "없음" / n)
    s = tmp_path / "s2"
    for rel in ("server/index.js", "engine/tools/calcopy/hybrid/render_bench.py"):
        (s / rel).parent.mkdir(parents=True, exist_ok=True)
        (s / rel).write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit):
        PU.make_zip(s, "1.0.34")


def _member_home(tmp_path) -> Path:
    """실제 파일을 설치본 자리로 복사한 가짜 회원 폴더."""
    home = tmp_path / "Shortem"
    for rel in ("shopping_shorts/channelkit/vision/__init__.py", "tools/calcopy/hybrid/common.py"):
        (home / "engine" / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, home / "engine" / rel)
    return home


def _probe(home: Path, code: str, tmp_path) -> str:
    env = {k: v for k, v in os.environ.items() if k not in ("SHORTEM_MODELS", "CALCOPY_FACE_MODEL")}
    env.update(OPENBLAS_NUM_THREADS="1", SHORTEM_MODELS=str(tmp_path / "빈자리"), PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", CALCOPY_FACE_MODEL=str(tmp_path / "빈자리" / "x.onnx"))
    r = subprocess.run([sys.executable, "-c", code, str(home / "engine")], capture_output=True, text=True, encoding="utf-8", env=env)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip().splitlines()[-1]


VISION = ("import sys,importlib.util as u;p=sys.argv[1]+'/shopping_shorts/channelkit/vision/__init__.py';s=u.spec_from_file_location('v',p);"
          "m=u.module_from_spec(s);s.loader.exec_module(m);print(m.model(m.YUNET))")
COMMON = ("import sys,importlib.util as u;p=sys.argv[1]+'/tools/calcopy/hybrid/common.py';s=u.spec_from_file_location('c',p);"
          "m=u.module_from_spec(s);s.loader.exec_module(m);print(m.FACE_MODEL)")
NAME = "face_detection_yunet_2023mar.onnx"


@pytest.mark.parametrize("code", [VISION, COMMON])
def test_설치폴더_models_가_먼저고_옛_engine_models_도_찾는다(tmp_path, code):
    home = _member_home(tmp_path)
    (home / "engine" / "models").mkdir()
    (home / "engine" / "models" / NAME).write_bytes(b"x")
    assert Path(_probe(home, code, tmp_path)) == home / "engine" / "models" / NAME      # 지금 회원
    (home / "models").mkdir()
    (home / "models" / NAME).write_bytes(b"x")
    assert Path(_probe(home, code, tmp_path)) == home / "models" / NAME                 # 옮긴 뒤
    shutil.rmtree(home / "engine" / "models")
    assert Path(_probe(home, code, tmp_path)) == home / "models" / NAME                 # engine 이 바뀐 뒤


def test_빌드_모델_자리는_설치폴더():
    src = (ROOT / "installer/win/build_win.py").read_text(encoding="utf-8")
    assert 'vm = stage / "models"' in src and 'stage / "engine" / "models"' not in src
    assert "models" in json.dumps(sorted(ast.literal_eval(next(
        n.value for n in ast.parse(src).body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "STAGE_TOP"))), ensure_ascii=False)
