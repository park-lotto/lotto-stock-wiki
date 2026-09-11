"""Integration contracts for the read-only company catalog (real files and SQLite)."""
import hashlib
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from creative_library.catalog import Catalog
from creative_library.schema import AccessContext, Dependency, LibraryConfig, Rights
from creative_library.adapters.common import open_readonly


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def source(tmp_path):
    repo = tmp_path / "repo"
    base = repo / "shopping_shorts"
    write_json(base / "static/fonts.json", [
        {"name": "한글 훅", "file": "Hook.otf", "css": "HCHook", "group": "impact"},
        {"name": "없는 글꼴", "file": "Missing.otf", "css": "HCMissing", "group": "gothic"},
    ])
    (base / "static/fonts").mkdir()
    (base / "static/fonts/Hook.otf").write_bytes(b"fixture-font-v1")
    write_json(base / "assets/motion/manifest.json", {"assets": [
        {"id": "swipe", "file": "swipe.mov", "type": "transition", "default": {"x": 50}},
    ]})
    (base / "assets/motion/swipe.mov").write_bytes(b"fixture-alpha-movie")
    write_json(base / "assets/motion/packs.json", {"packs": [
        {"id": "minimal", "name": "미니멀", "transition": {"asset_id": "swipe", "dur": .4}},
    ]})
    (base / "deco_frame.py").write_text(
        'from this_module_does_not_exist import never_import\n'
        'raise RuntimeError("must not execute module")\n'
        'def _hc(font, size):\n    return {"font": font, "size": min(size, 90)}\n'
        'def _cap(color):\n    return {"color": color}\n'
        'PRESETS = {"clean": {"name": "깨끗한 틀", "headcopy": _hc("Hook.otf", 110),'
        ' "caption": _cap("#FFFFFF")}}\n', encoding="utf-8")
    write_json(base / "assets/voice_presets.json", [
        {"preset_id": "kr-demo", "name": "공용 성우", "lang": "KR", "origin": "curated",
         "base_voice_id": "provider-demo", "model_id": "voice-model", "sample_file": "demo.mp3",
         "voice_settings": {"stability": .5}, "default_speed": 1.2},
    ])
    (base / "assets/voice_samples").mkdir()
    (base / "assets/voice_samples/demo.mp3").write_bytes(b"fixture-voice")
    db = tmp_path / "reference.db"
    with sqlite3.connect(db) as conn:
        conn.executescript('''
            CREATE TABLE scene_assets(id INTEGER PRIMARY KEY, customer_id INTEGER,
              asset_type TEXT, media_path TEXT, title TEXT, role TEXT, source_ref TEXT);
            INSERT INTO scene_assets VALUES (1, 0, 'sfx', 'hit.wav', '관리자 개인음', '훅', 'own');
            INSERT INTO scene_assets VALUES (2, 7, 'clip', 'private.mov', '칠번 비밀영상', '본문', 'own');
            INSERT INTO scene_assets VALUES (3, 8, 'clip', 'other.mov', '팔번 비밀영상', '본문', 'own');
            CREATE TABLE spine(id INTEGER PRIMARY KEY, name TEXT, status TEXT,
              beat_roles_json TEXT, templates_json TEXT, fit_categories_json TEXT);
            INSERT INTO spine VALUES (11, '검토 중 구조', 'pending', '["hook"]',
              '{"hook":["{제품}의 차이"]}', '["홈템"]');
            INSERT INTO spine VALUES (12, '기존 승인 구조', 'approved', '["hook","info"]', '{}', '[]');
            CREATE TABLE voice_presets(preset_id TEXT, name TEXT, origin TEXT,
              owner_customer_id INTEGER, base_voice_id TEXT, voice_settings_json TEXT);
            INSERT INTO voice_presets VALUES ('private-7', '칠번 개인성우', 'generated', 7, 'secret-voice-7', '{}');
            INSERT INTO voice_presets VALUES ('private-8', '팔번 개인성우', 'generated', 8, 'secret-voice-8', '{}');
        ''')
    return repo, db


def load(source, tenant=None, admin=False):
    repo, db = source
    return Catalog.load(LibraryConfig(repo=repo, db=db), AccessContext(tenant_id=tenant, is_admin=admin))


def test_six_adapters_read_real_sources_without_importing_the_application(source):
    catalog = load(source, tenant=7)
    items = catalog.search()
    assert {item.domain for item in items} == {"font", "scene", "motion", "layout", "script", "voice"}
    assert len(items) == 10
    assert {r.adapter for r in catalog.reports} == {"fonts", "scene_assets", "motion_packs", "deco", "spines", "voices"}
    assert catalog.get("legacy/layout/clean").parameters["headcopy"]["size"] == 90


def test_private_metadata_never_reaches_other_tenants_or_public_summaries(source):
    public = load(source)
    seven = load(source, tenant=7)
    admin = load(source, admin=True)
    assert not [i for i in public.search() if i.domain == "scene"]
    assert public.get("legacy/scene/2") is None
    assert seven.get("legacy/scene/2").name == "칠번 비밀영상"
    assert seven.get("legacy/scene/3") is None
    assert seven.get("legacy/voice/private-8") is None
    assert admin.get("legacy/scene/1").owner.tenant_id == "0"
    assert admin.get("legacy/scene/3") is not None
    public_json = json.dumps(public.to_dict(), ensure_ascii=False)
    assert "칠번" not in public_json and "팔번" not in public_json and "secret-voice" not in public_json


def test_approval_and_rights_are_not_invented_when_importing_legacy(source):
    catalog = load(source)
    assert catalog.get("legacy/script/11").status == "pending"
    assert catalog.get("legacy/script/12").status == "approved"
    decision = catalog.explain("legacy/script/12")
    assert not decision.usable
    assert "rights_unverified" in decision.reasons
    assert not catalog.search(usable_only=True)


def test_korean_search_and_legacy_lookup_preserve_identity(source):
    catalog = load(source)
    assert [i.id for i in catalog.search("한글 훅", domain="font")] == ["legacy/font/Hook.otf"]
    assert catalog.get_legacy("fonts.json", "HCHook").id == "legacy/font/Hook.otf"
    assert catalog.get_legacy("spine", "12").status == "approved"


def test_missing_file_is_visible_with_rejection_reason(source):
    catalog = load(source)
    item = catalog.get("legacy/font/Missing.otf")
    assert item.artifacts[0].exists is False
    assert "artifact_missing" in catalog.explain(item.id).reasons


def test_file_hash_and_version_change_with_binary_content_not_location(source, tmp_path):
    first = load(source)
    font = first.get("legacy/font/Hook.otf")
    assert font.artifacts[0].sha256 == hashlib.sha256(b"fixture-font-v1").hexdigest()
    assert first.fingerprint == load(source).fingerprint
    (source[0] / "shopping_shorts/static/fonts/Hook.otf").write_bytes(b"fixture-font-v2")
    second = load(source)
    assert second.get(font.id).version != font.version
    assert second.fingerprint != first.fingerprint


def test_motion_pack_dependencies_are_exact_and_change_when_asset_changes(source):
    first = load(source)
    pack = first.get("legacy/motion-pack/minimal")
    asset = first.get("legacy/motion/swipe")
    assert [(d.id, d.version) for d in pack.dependencies] == [(asset.id, asset.version)]
    (source[0] / "shopping_shorts/assets/motion/swipe.mov").write_bytes(b"updated-alpha")
    second = load(source)
    assert second.get(pack.id).version != pack.version


def test_database_is_read_only_and_missing_database_is_never_created(source, tmp_path):
    db = source[1]
    before = db.read_bytes()
    with open_readonly(db) as conn:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM spine")
    load(source, admin=True)
    assert db.read_bytes() == before
    missing = tmp_path / "missing.db"
    with pytest.raises(FileNotFoundError):
        LibraryConfig(repo=source[0], db=missing)
    assert not missing.exists()


def test_db_omission_is_reported_instead_of_creating_or_guessing_one(source):
    catalog = Catalog.load(LibraryConfig(repo=source[0]), AccessContext())
    reports = {r.adapter: r for r in catalog.reports}
    assert reports["scene_assets"].state == "skipped"
    assert reports["spines"].state == "skipped"
    assert catalog.get("legacy/voice/kr-demo") is not None


def test_relative_database_media_needs_explicit_media_root(source, tmp_path):
    unresolved = load(source, tenant=0).get("legacy/scene/1")
    assert unresolved.artifacts[0].issue == "media_root_required"
    media = tmp_path / "media"
    media.mkdir()
    (media / "hit.wav").write_bytes(b"real-hit")
    catalog = Catalog.load(LibraryConfig(repo=source[0], db=source[1], media_root=media), AccessContext(tenant_id=0))
    assert catalog.get("legacy/scene/1").artifacts[0].exists


def test_path_traversal_cannot_read_an_unrelated_file(source):
    repo = source[0]
    write_json(repo / "shopping_shorts/static/fonts.json", [
        {"name": "bad", "file": "../../../outside.txt", "css": "bad"},
    ])
    catalog = load(source)
    bad = catalog.search("bad")[0]
    assert bad.artifacts[0].issue == "path_outside_root"
    assert bad.artifacts[0].sha256 is None


def test_invalid_private_json_does_not_break_or_leak_into_public_catalog(source):
    with sqlite3.connect(source[1]) as conn:
        conn.execute("UPDATE voice_presets SET voice_settings_json='secret-invalid-json' WHERE owner_customer_id=8")
    public = load(source)
    assert all(r.state != "error" for r in public.reports)
    assert "secret-invalid-json" not in json.dumps(public.to_dict())


def test_owner_zero_library_voice_is_admin_account_private(source):
    with sqlite3.connect(source[1]) as conn:
        conn.execute("INSERT INTO voice_presets VALUES ('account-zero', '사장님 계정 성우', 'library', 0, 'zero-secret', '{}')")
    assert load(source).get("legacy/voice/account-zero") is None
    assert load(source, tenant=7).get("legacy/voice/account-zero") is None
    assert load(source, tenant=0).get("legacy/voice/account-zero").owner.scope == "tenant"
    assert load(source, admin=True).get("legacy/voice/account-zero") is not None


def test_tuning_workbench_voice_is_not_a_shared_voice_card(source):
    with sqlite3.connect(source[1]) as conn:
        conn.execute("INSERT INTO voice_presets VALUES ('scratch', '임시 튜닝', 'tuned', 0, 'draft-voice', '{}')")
    assert load(source).get("legacy/voice/scratch") is None
    assert load(source, tenant=7).get("legacy/voice/scratch") is None
    item = load(source, tenant=0).get("legacy/voice/scratch")
    assert "legacy_picker_hidden" in item.constraints


def test_curated_database_orphan_is_marked_as_source_drift(source):
    with sqlite3.connect(source[1]) as conn:
        conn.execute("INSERT INTO voice_presets VALUES ('old-curated', '예전 큐레이션', 'curated', 0, 'old', '{}')")
    item = load(source).get("legacy/voice/old-curated")
    assert "curated_entry_missing_from_file" in item.constraints


def test_private_spine_is_filtered_before_parsing(source):
    with sqlite3.connect(source[1]) as conn:
        conn.execute("ALTER TABLE spine ADD COLUMN customer_id INTEGER")
        conn.execute("UPDATE spine SET customer_id=8, templates_json='private malformed payload' WHERE id=11")
        conn.execute("UPDATE spine SET customer_id=7 WHERE id=12")
    catalog = load(source, tenant=7)
    assert catalog.get("legacy/script/12") is not None
    assert catalog.get("legacy/script/11") is None
    assert next(r for r in catalog.reports if r.adapter == "spines").state == "ok"


def test_cli_runs_as_readonly_json_process_and_reports_missing_source(source):
    repo, db = source
    cmd = [sys.executable, "-m", "creative_library", "--repo", str(repo), "--db", str(db)]
    run = subprocess.run(cmd + ["search", "한글"], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr
    data = json.loads(run.stdout)
    assert [i["id"] for i in data["items"]] == ["legacy/font/Hook.otf"]
    hidden = subprocess.run(cmd + ["get", "legacy/scene/2"], capture_output=True, text=True, encoding="utf-8")
    assert hidden.returncode == 1
    assert "칠번" not in hidden.stdout


def verified(item):
    return replace(item, status="approved", review_refs=("review:fixture",),
                   rights=Rights(status="verified", evidence_refs=("rights:fixture",), commercial_use=True),
                   capabilities=("render_verified",))


def test_approved_pack_cannot_hide_unapproved_dependency(source):
    source_catalog = load(source)
    pack = verified(source_catalog.get("legacy/motion-pack/minimal"))
    asset = source_catalog.get("legacy/motion/swipe")
    catalog = Catalog([pack, asset], [], AccessContext())
    assert not catalog.explain(pack.id).usable
    assert "dependency_not_usable" in catalog.explain(pack.id).reasons


def test_exact_dependency_version_mismatch_cannot_silently_repin(source):
    source_catalog = load(source)
    asset = verified(source_catalog.get("legacy/motion/swipe"))
    pack = replace(verified(source_catalog.get("legacy/motion-pack/minimal")),
                   dependencies=(Dependency(asset.id, "sha256:previous-version"),))
    catalog = Catalog([pack, asset], [], AccessContext())
    assert catalog.get(pack.id).dependencies[0].version == "sha256:previous-version"
    assert "dependency_version_mismatch" in catalog.explain(pack.id).reasons


def test_dependency_cycle_is_rejected_and_does_not_recurse_forever(source):
    source_catalog = load(source)
    first = replace(verified(source_catalog.get("legacy/motion-pack/minimal")),
                    dependencies=(Dependency("legacy/pack/second"),))
    second = replace(first, id="legacy/pack/second", dependencies=(Dependency(first.id),), legacy_refs=())
    catalog = Catalog([first, second], [], AccessContext())
    assert "dependency_cycle" in catalog.explain(first.id).reasons
    assert not catalog.search(usable_only=True)


def test_verified_rights_without_commercial_permission_cannot_be_usable(source):
    item = verified(load(source).get("legacy/font/Hook.otf"))
    item = replace(item, rights=replace(item.rights, commercial_use=False))
    catalog = Catalog([item], [], AccessContext())
    assert not catalog.explain(item.id).usable
    assert "commercial_use_not_verified" in catalog.explain(item.id).reasons


def test_unresolved_constraints_block_an_otherwise_verified_item(source):
    item = verified(load(source).get("legacy/font/Hook.otf"))
    catalog = Catalog([item], [], AccessContext())
    assert not catalog.explain(item.id).usable
    assert "constraints_unverified" in catalog.explain(item.id).reasons
    cleared = Catalog([replace(item, constraints=())], [], AccessContext())
    assert cleared.explain(item.id).usable


def test_caller_cannot_mutate_versioned_catalog_parameters(source):
    original = load(source).get("legacy/layout/clean")
    catalog = Catalog([original], [], AccessContext())
    original.parameters["headcopy"]["size"] = 1
    fetched = catalog.get(original.id)
    fetched.parameters["headcopy"]["size"] = 2
    result = catalog.search()[0]
    result.parameters["headcopy"]["size"] = 3
    assert catalog.get(original.id).parameters["headcopy"]["size"] == 90


def test_company_access_mismatch_is_denied_even_for_admin(source):
    with pytest.raises(PermissionError):
        Catalog.load(LibraryConfig(repo=source[0], company_id="company-a"),
                     AccessContext(company_id="company-b", is_admin=True))


def test_broken_source_reports_partial_catalog_instead_of_successful_empty_list(source):
    (source[0] / "shopping_shorts/static/fonts.json").write_text("not json", encoding="utf-8")
    catalog = load(source)
    assert next(r for r in catalog.reports if r.adapter == "fonts").state == "error"
    assert catalog.get("legacy/layout/clean") is not None
    cmd = [sys.executable, "-m", "creative_library", "--repo", str(source[0]), "summary"]
    run = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 2
    assert json.loads(run.stdout)["visible_items"] > 0
