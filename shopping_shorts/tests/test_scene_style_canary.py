from pathlib import Path
import subprocess


STATIC = Path(__file__).parents[1] / "static"


def test_produce_canary_is_explicit_admin_exact_job_and_fail_closed():
    html = (STATIC / "produce.html").read_text(encoding="utf-8")
    script = (STATIC / "scene-style-produce.js").read_text(encoding="utf-8")

    assert "scene_style_canary=1" not in html
    assert "scene-style-canary-active" in script
    assert "get('scene_style_canary')" in script
    assert "canaryParam==='1'" in script
    assert "localStorage.setItem(canaryKey,'1')" in script
    assert "localStorage.getItem(canaryKey)==='1'" in script
    assert "localStorage.removeItem(canaryKey)" in script
    assert "requested!==currentMixJob()" in script
    assert "typeof MIX_JOB==='undefined'" in script
    assert ".find(row=>String(row.job_id)===requested)" in script
    assert "다른 작업으로 대신 열지 않습니다" in script
    assert "panel?.classList.remove('scene-style-canary-active')" in script


def test_lab_job_query_locks_to_exact_job_without_first_job_fallback():
    script = (STATIC / "scene-style-lab.js").read_text(encoding="utf-8")

    assert "const requestedJob=query.get('job')" in script
    assert ".find(row=>String(row.job_id)===requestedJob)" in script
    assert "jobs=[exact];job.disabled=true" in script
    assert "sourceJobId=requestedJob||job.value" in script
    assert "JSON.stringify({job_id:sourceJobId})" in script
    assert "jobs[0]" not in script


def test_embedded_canary_opens_editor_only_and_reuses_exact_job_copy():
    html = (STATIC / "scene_style_lab.html").read_text(encoding="utf-8")
    script = (STATIC / "scene-style-lab.js").read_text(encoding="utf-8")

    assert "html.embedded-tab #editor" in html
    assert "html.embedded-tab #outputs" in html
    assert "height:100%" in html
    assert "query.get('embedded')==='tab'" in script
    assert "scene-style-canary-lab:${requestedJob||''}" in script
    assert "sessionStorage.getItem(rememberedLabKey())" in script
    assert "source_job_id" in script
    assert "openLabCopy" in script


def test_canary_template_tabs_keep_legacy_and_new_editors_separate():
    html = (STATIC / "produce.html").read_text(encoding="utf-8")
    host = (STATIC / "scene-style-produce.js").read_text(encoding="utf-8")
    lab = (STATIC / "scene-style-lab.js").read_text(encoding="utf-8")
    editor = (STATIC.parents[1] / "out" / "precision20-ui.js").read_text(encoding="utf-8")

    for label in ("템플릿 없이", "기존 스타일", "썰쇼핑형", "전장면 고정형"):
        assert label in html or label in editor
    assert 'data-template-mode="manual"' in editor
    assert 'data-template-mode="legacy"' in editor
    assert "scene-style-host-mode" in editor
    assert "scene-style-host-mode" in lab
    assert "scene-style-select-template-mode" in lab
    assert "scene-style-select-template-mode" in host
    assert "legacyStylePresets" in html
    assert "presets.hidden=mode==='manual'" in host
    assert "기존 화면은 현재 원본 작업에 저장됩니다" in host


def test_canary_runtime_activates_only_for_the_exact_current_job():
    result = subprocess.run(
        ["node", str(Path(__file__).parent / "js" / "scene_style_canary_runtime.js")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
