# -*- coding: utf-8 -*-
"""channelkit.registry — 엔진 모듈이 보는 `spec`은 현재 채널 spec으로 위임되는 프록시다."""
import importlib
import sys
import types

import pytest

from shopping_shorts.channelkit import registry, spec


def _fake_channel(name, **consts):
    """테스트용 채널 spec 모듈을 sys.modules에 심는다."""
    mod = types.ModuleType(f"shopping_shorts.channel_presets.{name}.spec")
    for k, v in consts.items():
        setattr(mod, k, v)
    pkg = types.ModuleType(f"shopping_shorts.channel_presets.{name}")
    pkg.__path__ = []
    sys.modules[f"shopping_shorts.channel_presets.{name}"] = pkg
    sys.modules[f"shopping_shorts.channel_presets.{name}.spec"] = mod
    return mod


@pytest.fixture(autouse=True)
def _restore():
    yield
    registry.use(registry.DEFAULT)


def test_default_is_brainbulb():
    registry.use(registry.DEFAULT)
    assert registry.current().__name__ == "shopping_shorts.channel_presets.brainbulb.spec"
    assert spec.CANVAS_W == 1080 and spec.CANVAS_H == 1920


def test_use_switches_proxy():
    _fake_channel("fakech", CANVAS_W=720, CANVAS_H=1280)
    registry.use("fakech")
    assert spec.CANVAS_W == 720
    registry.use(registry.DEFAULT)
    assert spec.CANVAS_W == 1080


def test_missing_attr_raises_and_getattr_default_works():
    _fake_channel("fakech2", CANVAS_W=1)
    registry.use("fakech2")
    with pytest.raises(AttributeError):
        spec.NO_SUCH_CONSTANT
    assert getattr(spec, "FACE_MODEL", None) is None


def test_fonts_dir_moved_with_channel():
    registry.use(registry.DEFAULT)
    import os
    assert os.path.isfile(os.path.join(spec.FONTS_DIR, "SBAggroB.ttf"))
    assert "channel_presets" in spec.FONTS_DIR.replace("\\", "/")


def test_steps_come_from_channel_spec(tmp_path):
    from shopping_shorts.channelkit import pipeline
    registry.use(registry.DEFAULT)
    assert pipeline.steps()[0] == "setup" and "review" in pipeline.steps()

    calls = []

    def _echo(job, d, wd, kw):
        calls.append(kw.get("source_text"))
        d["echo"] = {"n": len(calls)}
        return None                       # None = 정상 진행

    _fake_channel("stepch", STEPS=["setup", "echo"], STEP_HANDLERS={"echo": _echo},
                  FONTS_DIR=registry.use(registry.DEFAULT).FONTS_DIR, STYLE_FONT=registry.current().STYLE_FONT)
    registry.use("stepch")
    r = pipeline.run_step(str(tmp_path), "setup", source_text="소재")
    assert r["status"] == "ok" and r["next_step"] == "echo"
    r = pipeline.run_step(str(tmp_path), "echo", source_text="소재")
    assert r["status"] == "ok" and r["next_step"] is None
    assert pipeline.load(str(tmp_path))["data"]["echo"] == {"n": 1}


def test_run_step_channel_kwarg_switches(tmp_path):
    from shopping_shorts.channelkit import pipeline
    _fake_channel("kwch", STEPS=["setup"], STEP_HANDLERS={},
                  FONTS_DIR=registry.use(registry.DEFAULT).FONTS_DIR, STYLE_FONT=registry.current().STYLE_FONT)
    pipeline.run_step(str(tmp_path), "setup", source_text="x", channel="kwch")
    assert registry.name() == "kwch"


def test_lint_rules_chosen_by_channel():
    from shopping_shorts.channelkit import lint
    registry.use(registry.DEFAULT)
    assert [r.id for r in lint.rules()] == list(registry.current().LINT_RULES)
    assert len(lint.rules()) == 24

    bb = registry.current()
    _fake_channel("lintch", LINT_RULES=["title_punct", "comma"],
                  **{k: getattr(bb, k) for k in dir(bb) if k.isupper() and k != "LINT_RULES"})
    registry.use("lintch")
    assert [r.id for r in lint.rules()] == ["title_punct", "comma"]
    issues, _ = lint.lint({"title": {"h1": "제목?", "h2": "둘째"}, "groups": []}, do_layout=False)
    assert {i.rule for i in issues} <= {"title_punct", "comma"}
    assert "title_punct" in {i.rule for i in issues}
    assert "- " in lint.prompt_block() and lint.prompt_block().count("\n") == 1


def _plain_channel(name, steps, handlers):
    bb = registry.use(registry.DEFAULT)
    return _fake_channel(name, STEPS=steps, STEP_HANDLERS=handlers, LINT_RULES=[],
                         FONTS_DIR=bb.FONTS_DIR, STYLE_FONT=bb.STYLE_FONT)


def test_handler_overrides_builtin_and_first_step_from_spec(tmp_path):
    from shopping_shorts.channelkit import pipeline
    seen = []

    def seed(job, d, wd, kw):
        seen.append("seed"); d["seed"] = {"x": 1}

    def setup(job, d, wd, kw):            # 기본 setup(폰트 검사)을 덮어쓴다
        seen.append("setup"); d["setup"] = {"mine": True}

    _plain_channel("ovch", ["seed", "setup"], {"seed": seed, "setup": setup})
    registry.use("ovch")
    wd = str(tmp_path)
    assert pipeline.next_step(wd) == "seed"
    r = pipeline.run_all(wd)
    assert r["status"] == "ok" and seen == ["seed", "setup"]
    assert pipeline.load(wd)["data"]["setup"] == {"mine": True}


def test_job_remembers_channel_on_resume(tmp_path):
    from shopping_shorts.channelkit import pipeline

    def a(job, d, wd, kw):
        d["a"] = 1

    def b(job, d, wd, kw):
        d["b"] = registry.name()

    _plain_channel("memch", ["a", "b"], {"a": a, "b": b})
    wd = str(tmp_path)
    pipeline.run_step(wd, "a", channel="memch")
    registry.use(registry.DEFAULT)                 # 다른 채널로 바뀐 뒤 재개
    r = pipeline.run_step(wd, "b")
    assert r["status"] == "ok"
    assert pipeline.load(wd)["channel"] == "memch" and pipeline.load(wd)["data"]["b"] == "memch"


def test_register_channel_rule():
    from shopping_shorts.channelkit import lint
    rule = lint.Rule("zz_test_rule", lint.WARN, "테스트", lambda s, ctx: [])
    lint.register(rule)
    assert lint.ALL_RULES["zz_test_rule"] is rule
