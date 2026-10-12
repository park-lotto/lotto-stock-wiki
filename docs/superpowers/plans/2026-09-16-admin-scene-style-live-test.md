# Admin Scene Style Live Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 실제 서버 작업의 TTS·자막 시간표·자막제거 청소본을 읽되 원본 job은 수정하지 않는 관리자 전용 장면꾸미기 시험판을 만들고, 훅 말자막 숨김이 미리보기·MP4·CapCut·시험 랜딩까지 동일하게 전달되는지 검증한다.

**Architecture:** 최신 `main`의 라이브 함수를 시험판에서도 직접 호출하고 별도 `scene_style_lab` manifest만 시험 상태의 주인으로 둔다. 훅 숨김은 빈 문자열이 아니라 `caption_visible` 계약으로 표현하며, 모든 출력은 동일 manifest와 편성 서명을 읽는다. 청소본이 없거나 서명이 낡으면 원본 미리보기로 폴백하지 않고 차단한다.

**Tech Stack:** FastAPI, vanilla HTML/JavaScript, Python 3, ffmpeg/ffprobe, Puppeteer, CapCut draft JSON, pytest

---

### Task 1: 최신 라이브 기준선으로 트랙 갱신

**Files:**
- Verify: `shopping_shorts/app.py`
- Verify: `shopping_shorts/mix_pipeline.py`
- Verify: `shopping_shorts/video_assemble.py`
- Verify: `shopping_shorts/capcut_draft.py`
- Modify by merge: `.tracks/장면꾸미기UI코덱스/**`

- [ ] **Step 1: 서버 기준선과 로컬 main을 다시 측정**

Run:

```powershell
nslookup shoppingshorts.duckdns.org
ssh -o ConnectTimeout=15 -o StrictHostKeyChecking=no -i 'C:\Users\CH\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem' ubuntu@3.35.251.172 "cd /home/ubuntu/lotto-stock-wiki && git rev-parse HEAD && git branch --show-current && git status --short && sha256sum shopping_shorts/app.py shopping_shorts/mix_pipeline.py shopping_shorts/video_assemble.py shopping_shorts/capcut_draft.py"
Get-FileHash -Algorithm SHA256 -LiteralPath 'shopping_shorts/app.py','shopping_shorts/mix_pipeline.py','shopping_shorts/video_assemble.py','shopping_shorts/capcut_draft.py'
```

Expected: 서버 브랜치는 `main`; tracked 수정 파일은 없음; 네 파일의 SHA-256은 로컬 `main`과 동일.

- [ ] **Step 2: 장면꾸미기 트랙에 최신 main 병합**

Run:

```powershell
git -C '.tracks/장면꾸미기UI코덱스' merge --no-edit main
```

Expected: merge commit 생성. 충돌이 나면 `app.py`, `produce.html`, `video_assemble.py`의 최신 main 동작을 보존하고 장면꾸미기 추가 배선만 다시 얹는다.

- [ ] **Step 3: 병합 뒤 핵심 회귀 테스트 실행**

Run:

```powershell
py -m pytest .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_caption_sync_wiring.py .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_clean_single_source_of_truth.py .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_capcut_draft.py .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_scene_style.py -q
```

Expected: `test_caption_sync_wiring.py`, `test_clean_single_source_of_truth.py`, `test_capcut_draft.py`, `test_scene_style.py` 모두 PASS.

- [ ] **Step 4: 병합 상태 확인**

Run:

```powershell
git -C '.tracks/장면꾸미기UI코덱스' status --porcelain
git -C '.tracks/장면꾸미기UI코덱스' log -3 --oneline
```

Expected: 충돌 표식 없음; 의도하지 않은 미추적 파일 없음.

### Task 2: 원본을 수정하지 않는 시험 manifest

**Files:**
- Create: `shopping_shorts/scene_style_lab.py`
- Create: `shopping_shorts/tests/test_scene_style_lab_manifest.py`

- [ ] **Step 1: 청소본 없이는 복사하지 않고 원본 dict를 변경하지 않는 실패 테스트 작성**

```python
def test_create_lab_copy_requires_fresh_clean_and_keeps_source_unchanged(tmp_path, monkeypatch):
    from copy import deepcopy
    from shopping_shorts import scene_style_lab as lab

    job = {"edit_plan": {"beats": [{"beat_idx": 0, "narration": "훅", "tts_path": "a.mp3"}]}}
    before = deepcopy(job)
    monkeypatch.setattr(lab, "resolve_clean_contract", lambda *_: None)

    with pytest.raises(lab.LabPreconditionError, match="청소본"):
        lab.create_copy("job1", job, tmp_path)
    assert job == before
```

- [ ] **Step 2: 테스트가 실패하는지 실행**

Run:

```powershell
py -m pytest .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_scene_style_lab_manifest.py -q
```

Expected: `ImportError` 또는 `ModuleNotFoundError`로 FAIL.

- [ ] **Step 3: 시험 복사본과 안전한 파일 경계 구현**

```python
class LabPreconditionError(RuntimeError):
    pass

def lab_dir(work_root: Path, lab_id: str) -> Path:
    if not re.fullmatch(r"lab_[0-9a-f]{12}", lab_id):
        raise ValueError("잘못된 시험 번호")
    return Path(work_root) / "_scene_style_lab" / lab_id

def create_copy(job_id: str, job: dict, work_root: Path) -> dict:
    plan = copy.deepcopy(job.get("edit_plan") or {})
    if not plan.get("beats"):
        raise LabPreconditionError("편집안이 없습니다")
    clean = resolve_clean_contract(job, Path(work_root) / job_id)
    if clean is None:
        raise LabPreconditionError("현재 편성과 일치하는 자막제거 청소본이 없습니다")
    lab_id = "lab_" + secrets.token_hex(6)
    manifest = {
        "version": 1,
        "lab_id": lab_id,
        "source_job_id": job_id,
        "source_plan_signature": mix_pipeline.plan_signature(plan),
        "edit_plan": plan,
        "headcopy": copy.deepcopy(job.get("headcopy")),
        "caption_style": copy.deepcopy(job.get("caption_style")),
        "deco": copy.deepcopy(job.get("deco") or {}),
        "clean": clean,
        "hook_caption_mode": "hidden",
        "outputs": {},
    }
    target = lab_dir(work_root, lab_id)
    target.mkdir(parents=True, exist_ok=False)
    write_manifest(target, manifest)
    return manifest
```

`resolve_clean_contract()`는 `clean_sources`가 모두 존재하면 `kind="sources"`와 `paths`를 반환하고, 아니면 `mix_pipeline.clean_final_path_for_plan(job, work)` 결과만 `kind="final"`과 `path`로 반환한다. `preview_path`와 `video_path`는 읽지 않는다.

- [ ] **Step 4: stale 감지와 경로순회 테스트 추가**

```python
def test_assert_fresh_rejects_changed_plan():
    manifest = {"source_plan_signature": "old"}
    with pytest.raises(LabPreconditionError, match="바뀌었습니다"):
        assert_fresh(manifest, {"edit_plan": {"beats": []}})

@pytest.mark.parametrize("bad", ["../x", "lab_x", "", "lab_1234/xx"])
def test_lab_dir_rejects_bad_id(tmp_path, bad):
    with pytest.raises(ValueError):
        lab_dir(tmp_path, bad)
```

- [ ] **Step 5: manifest 테스트 실행 및 커밋**

Run:

```powershell
py -m pytest .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_scene_style_lab_manifest.py -q
git -C '.tracks/장면꾸미기UI코덱스' add -A
git -C '.tracks/장면꾸미기UI코덱스' commit -m "시험용 장면꾸미기 복사본 격리"
```

Expected: PASS 후 커밋 생성.

### Task 3: 훅 말자막 숨김을 명시적 계약으로 추가

**Files:**
- Modify: `shopping_shorts/scene_style.py:1-220`
- Modify: `out/precision20-ui.js:37-58, 96-116, 500-540, 740-800`
- Modify: `shopping_shorts/static/scene-style-produce.js:1-110`
- Create: `shopping_shorts/tests/test_scene_style_hook_caption.py`

- [ ] **Step 1: 훅은 숨고 본문 시간은 유지되는 실패 테스트 작성**

```python
def test_context_marks_only_hook_captions_hidden(monkeypatch):
    monkeypatch.setattr(va, "caption_schedule", lambda beat: [(beat["narration"], beat["t0"], beat["t0"] + beat["dur"])])
    timeline = [
        {"beat_idx": 0, "t0": 0.0, "dur": 1.8, "narration": "훅 대사"},
        {"beat_idx": 1, "t0": 1.8, "dur": 2.0, "narration": "본문 대사"},
    ]
    ctx = scene_style.context_for(timeline, snapshot={"hookCaptionMode": "hidden"})
    assert ctx["scenes"][0]["caption"] == "훅 대사"
    assert ctx["scenes"][0]["caption_visible"] is False
    assert ctx["scenes"][1]["caption_visible"] is True
    assert ctx["scenes"][1]["start"] == 1.8
```

- [ ] **Step 2: 테스트 실패 확인**

Run:

```powershell
py -m pytest .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_scene_style_hook_caption.py -q
```

Expected: `caption_visible` 키가 없어 FAIL.

- [ ] **Step 3: 서버 context와 스냅샷 허용 키 구현**

```python
allowed = {"version", "mode", "presetId", "sceneIndex", "frameKind", "hookMotion",
           "hookMotionSpeed", "hookCaptionMode", "branding", "text", "fontScales",
           "textOffsets", "colors", "fixedLayouts", "fixedColors", "captionTexts",
           "captionDrags", "captionPositions", "captionLayouts", "effects"}

hook_hidden = (snapshot or {}).get("hookCaptionMode") == "hidden"
visible = not (index == 0 and hook_hidden)
scenes.append({
    "start": a, "end": b, "caption": caption,
    "caption_visible": visible,
    "beat_idx": beat["beat_idx"],
    "kind": "hook" if index == 0 else "body",
})
```

기존 스냅샷에는 키가 없으므로 기본값은 표시 유지다. 말자막 문구와 시간표는 지우지 않는다.

- [ ] **Step 4: 브라우저가 명시적 표시값만 따르게 구현**

```javascript
const captionVisible=()=>sceneContext?.scenes?.[sceneIndex]?.caption_visible!==false;
const hasEditableCaption=()=>captionVisible()&&(mode==='continuous'||kind==='body');

function renderCaption(frame){
  if(!captionVisible()) return;
  // 기존 렌더 코드 그대로
}
```

`snapshot()`에는 `hookCaptionMode`를 포함하고, 시험판이 로드할 때만 `hidden`을 넣는다. 일반 제작소의 기존 저장본은 동작이 바뀌지 않는다.

- [ ] **Step 5: JS 정적 계약 테스트와 Python 테스트 실행**

```python
def test_ui_never_uses_empty_string_as_hook_policy():
    js = Path("out/precision20-ui.js").read_text(encoding="utf-8")
    assert "caption_visible!==false" in js
    assert "hookCaptionMode" in js
```

Run:

```powershell
py -m pytest .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_scene_style_hook_caption.py .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_scene_style.py -q
git -C '.tracks/장면꾸미기UI코덱스' add -A
git -C '.tracks/장면꾸미기UI코덱스' commit -m "훅 말자막 숨김 계약 추가"
```

Expected: PASS 후 커밋 생성.

### Task 4: 관리자 전용 실데이터 시험 페이지와 API

**Files:**
- Modify: `shopping_shorts/app.py:13902, 17750-17835`
- Create: `shopping_shorts/static/scene_style_lab.html`
- Create: `shopping_shorts/static/scene-style-lab.js`
- Create: `shopping_shorts/tests/test_scene_style_lab_api.py`

- [ ] **Step 1: 비관리자는 404, 관리자는 복사 가능한 실패 테스트 작성**

```python
def test_lab_page_is_admin_only(client, monkeypatch):
    monkeypatch.setattr(app_mod, "_is_admin", lambda _cid: False)
    assert client.get("/scene_style_lab.html").status_code == 404

def test_create_lab_copy_does_not_update_job(client, monkeypatch, sample_job):
    monkeypatch.setattr(app_mod, "_is_admin", lambda _cid: True)
    before = deepcopy(sample_job)
    result = client.post("/api/admin/scene-style-lab", json={"job_id": "j1"})
    assert result.status_code == 200
    assert sample_job == before
```

- [ ] **Step 2: 실패 확인**

Run:

```powershell
py -m pytest .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_scene_style_lab_api.py -q
```

Expected: 경로가 없어 FAIL.

- [ ] **Step 3: 모든 시험 경로에 같은 관리자 가드 구현**

```python
def _lab_admin(request: Request):
    if not _is_admin(getattr(request.state, "customer_id", None)):
        raise HTTPException(status_code=404, detail="Not Found")

@app.get("/scene_style_lab.html", response_class=HTMLResponse)
def scene_style_lab_page(request: Request):
    _lab_admin(request)
    return FileResponse(STATIC / "scene_style_lab.html")

@app.post("/api/admin/scene-style-lab")
def api_scene_style_lab_create(request: Request, body: dict):
    _lab_admin(request)
    job_id = str(body.get("job_id") or "")
    job = Store(DB_PATH).get_mix_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="작업 없음")
    try:
        return {"ok": True, "manifest": scene_style_lab.create_copy(job_id, job, _MIX_WORK_DIR)}
    except scene_style_lab.LabPreconditionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
```

같은 `_lab_admin()`을 목록, 조회, 저장, 렌더, CapCut, 랜딩 미디어에 모두 적용한다.

- [ ] **Step 4: 최근 작업 선택과 사전 조건 표시 UI 구현**

```html
<select id="job"></select>
<button id="clone">시험 복사본 만들기</button>
<dl id="checks"></dl>
<iframe id="editor" title="장면꾸미기"></iframe>
<section id="outputs"></section>
<script src="/scene-style-lab.js"></script>
```

```javascript
async function createCopy(){
  const response=await fetch('/api/admin/scene-style-lab',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:job.value})});
  const data=await response.json();
  if(!response.ok) throw Error(data.detail||'시험 복사본을 만들지 못했습니다');
  current=data.manifest;
  editor.src='/api/produce/scene-style/assets/out/scene-style-ui-showcase.html?embedded=1&lab=1';
  renderChecks(current);
}
```

- [ ] **Step 5: API와 기존 인증 회귀 테스트 실행 및 커밋**

Run:

```powershell
py -m pytest .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_scene_style_lab_api.py .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_p0_security_guards.py -q
git -C '.tracks/장면꾸미기UI코덱스' add -A
git -C '.tracks/장면꾸미기UI코덱스' commit -m "관리자 전용 장면꾸미기 시험 페이지"
```

Expected: PASS 후 커밋 생성.

### Task 5: 청소본만 쓰는 시험 MP4 렌더

**Files:**
- Modify: `shopping_shorts/scene_style_lab.py`
- Modify: `shopping_shorts/app.py`
- Create: `shopping_shorts/tests/test_scene_style_lab_render.py`

- [ ] **Step 1: 원본 폴백 금지와 출력 격리 실패 테스트 작성**

```python
def test_render_uses_only_manifest_clean_inputs(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(video_assemble, "assemble", lambda plan, tts, sources, out, **kw: calls.append((sources, out, kw)))
    manifest = sample_manifest(clean={"kind": "sources", "paths": {"v1": "clean.mp4"}})
    render_copy(manifest, sample_job(), tmp_path)
    assert calls[0][0] == {"v1": "clean.mp4"}
    assert "_scene_style_lab" in calls[0][1]
    assert calls[0][2]["deco"]["scene_style"]["hookCaptionMode"] == "hidden"
```

- [ ] **Step 2: 실패 확인**

Run:

```powershell
py -m pytest .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_scene_style_lab_render.py -q
```

Expected: `render_copy`가 없어 FAIL.

- [ ] **Step 3: 라이브 조립 함수를 호출하는 렌더 어댑터 구현**

```python
def render_copy(manifest: dict, source_job: dict, work_root: Path) -> Path:
    assert_fresh(manifest, source_job)
    target = lab_dir(work_root, manifest["lab_id"])
    plan = copy.deepcopy(manifest["edit_plan"])
    timeline = video_assemble._beat_timeline(plan, tts_paths(plan))
    sources = clean_sources_for_render(manifest["clean"], plan, timeline, target)
    deco = copy.deepcopy(manifest.get("deco") or {})
    snapshot = copy.deepcopy(deco.get("scene_style") or {})
    snapshot["hookCaptionMode"] = manifest["hook_caption_mode"]
    deco["scene_style"] = snapshot
    out = target / "lab-final.mp4"
    video_assemble.assemble(plan, tts_paths(plan), sources, str(out),
                            headcopy=manifest.get("headcopy"),
                            caption_style=manifest.get("caption_style"),
                            deco=deco)
    return out
```

완성본 1편 청소 방식은 기존 `split_final_into_beat_clips()`와 `plan_using_beat_clips()`를 사용한다.

- [ ] **Step 4: 백그라운드 렌더 API와 상태 저장 구현**

```python
@app.post("/api/admin/scene-style-lab/{lab_id}/render")
def api_lab_render(lab_id: str, request: Request, background_tasks: BackgroundTasks):
    _lab_admin(request)
    background_tasks.add_task(_run_scene_style_lab_render, lab_id)
    return {"ok": True, "status": "queued"}
```

렌더 성공 시 manifest `outputs.mp4`만 갱신하고 원본 job은 갱신하지 않는다.

- [ ] **Step 5: 테스트 실행 및 커밋**

Run:

```powershell
py -m pytest .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_scene_style_lab_render.py .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_clean_single_source_of_truth.py -q
git -C '.tracks/장면꾸미기UI코덱스' add -A
git -C '.tracks/장면꾸미기UI코덱스' commit -m "청소본 기반 시험 MP4 렌더"
```

Expected: PASS 후 커밋 생성.

### Task 6: 장면꾸미기 레이어를 CapCut 시험 초안까지 전달

**Files:**
- Modify: `shopping_shorts/scene_style.py:154-216`
- Modify: `shopping_shorts/capcut_draft.py:405-654, 697-862`
- Modify: `shopping_shorts/scene_style_lab.py`
- Create: `shopping_shorts/tests/test_scene_style_lab_capcut.py`

- [ ] **Step 1: 이중 자막 금지와 오버레이 시간 일치 실패 테스트 작성**

```python
def test_scene_overlay_replaces_native_caption_track():
    draft, _ = capcut_draft.build_draft(
        plan=plan(), timeline=timeline(), source_video_paths={"v":"v.mp4"},
        tts_paths={0:"a.mp3",1:"b.mp3"}, asset_paths={},
        scene_overlay_layers=[
            {"path":"hook.png","t0":0.0,"dur":1.8,"caption_visible":False},
            {"path":"body.png","t0":1.8,"dur":2.0,"caption_visible":True},
        ],
    )
    text_tracks = [t for t in draft["tracks"] if t.get("type") == "text"]
    overlay_tracks = [t for t in draft["tracks"] if t.get("name") == "scene-style-overlay"]
    assert text_tracks == []
    assert [s["target_timerange"]["start"] for s in overlay_tracks[0]["segments"]] == [0, 1_800_000]
```

- [ ] **Step 2: 실패 확인**

Run:

```powershell
py -m pytest .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_scene_style_lab_capcut.py -q
```

Expected: `scene_overlay_layers` 인자가 없어 FAIL.

- [ ] **Step 3: 브라우저 레이어 생성을 재사용 가능한 함수로 분리**

```python
def render_layers(timeline, snapshot, output, headcopy=None):
    context = context_for(timeline, headcopy, snapshot)
    request = Path(output) / "scene-style-request.json"
    request.write_text(json.dumps({"snapshot": snapshot, "context": context,
                                   "output": str(output)}, ensure_ascii=False), encoding="utf-8")
    run_layer_renderer(request)
    return context, json.loads((Path(output) / "scene-style-layers.json").read_text(encoding="utf-8"))
```

`compose()`도 이 함수를 호출하도록 바꿔 레이어 생성 판단을 한 곳에 둔다.

- [ ] **Step 4: CapCut 조립기에 선택적 오버레이 입력 구현**

`build_draft()`의 keyword-only 인자 끝에 `scene_overlay_layers=None`을 추가한다. 현재 `txt_track`을 채우는 `caption_schedule()` 루프는 `if not scene_overlay_layers:` 안에서만 실행한다. 그 다음 아래 트랙을 만든다.

```python
overlay_track = {"id": _uid(), "type": "video", "attribute": 0, "flag": 0,
                 "name": "scene-style-overlay", "is_default_name": False,
                 "segments": []}
for layer in scene_overlay_layers or []:
    overlay_path = asset_paths.get(layer["path"])
    if not overlay_path:
        continue
    assets_to_copy.append((layer["path"], overlay_path))
    material = _photo_material(overlay_path, Path(overlay_path).name, cw, ch)
    mats["videos"].append(material)
    segment = _base_segment(material["id"], _us(layer["t0"]), _us(layer["dur"]),
                            source_start=0, source_dur=_us(layer["dur"]),
                            render_index=0, volume=0.0)
    segment["track_render_index"] = 3
    overlay_track["segments"].append(segment)
```

마지막 `tracks` tuple에 `overlay_track`을 `txt_track`과 같은 위치에 추가한다. `scene_overlay_layers` 기본값이 `None`이면 현재 `txt_track`과 출력이 바이트 단위로 유지되어야 한다.

각 PNG/프레임 시퀀스는 `assemble_draft_folder()`가 프로젝트 폴더로 복사하고 CapCut 절대경로로 바꾼다. 일반 내보내기는 `scene_overlay_layers=None`이므로 기존 네이티브 캡션 동작을 유지한다.

- [ ] **Step 5: 생성 JSON 역검증 구현**

```python
def verify_capcut(draft: dict, expected: list[dict]) -> list[str]:
    actual = scene_overlay_segments(draft)
    errors = []
    for want, got in zip(expected, actual, strict=True):
        if got["start"] != round(want["t0"] * 1_000_000):
            errors.append(f"start:{want['t0']}!={got['start']}")
        if got["duration"] != round(want["dur"] * 1_000_000):
            errors.append(f"duration:{want['dur']}!={got['duration']}")
    return errors
```

- [ ] **Step 6: 테스트 실행 및 커밋**

Run:

```powershell
py -m pytest .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_scene_style_lab_capcut.py .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_capcut_draft.py .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_capcut_clean_clips.py -q
git -C '.tracks/장면꾸미기UI코덱스' add -A
git -C '.tracks/장면꾸미기UI코덱스' commit -m "장면꾸미기 레이어를 CapCut 시험 초안에 전달"
```

Expected: 신규·기존 테스트 모두 PASS.

### Task 7: 공개 기록을 만들지 않는 시험 랜딩

**Files:**
- Modify: `shopping_shorts/app.py:8037-8176`
- Create: `shopping_shorts/static/scene_style_lab_landing.html`
- Create: `shopping_shorts/tests/test_scene_style_lab_landing.py`

- [ ] **Step 1: 관리자 가드와 정확한 MP4 경로 실패 테스트 작성**

```python
def test_lab_landing_is_private_and_streams_lab_output(client, monkeypatch, lab_manifest):
    monkeypatch.setattr(app_mod, "_is_admin", lambda _cid: True)
    page = client.get(f"/scene-style-lab/{lab_manifest['lab_id']}")
    assert page.status_code == 200
    video = client.get(f"/api/admin/scene-style-lab/{lab_manifest['lab_id']}/video")
    assert video.status_code == 200
    assert video.headers["x-scene-style-lab"] == lab_manifest["lab_id"]
```

- [ ] **Step 2: 실패 확인**

Run:

```powershell
py -m pytest .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_scene_style_lab_landing.py -q
```

Expected: 경로가 없어 FAIL.

- [ ] **Step 3: 시험 랜딩과 미디어 경로 구현**

```python
@app.get("/scene-style-lab/{lab_id}", response_class=HTMLResponse)
def lab_landing(lab_id: str, request: Request):
    _lab_admin(request)
    scene_style_lab.read_manifest(_MIX_WORK_DIR, lab_id)
    return FileResponse(STATIC / "scene_style_lab_landing.html",
                        headers={"X-Robots-Tag": "noindex, nofollow, noarchive"})

@app.get("/api/admin/scene-style-lab/{lab_id}/video")
def lab_video(lab_id: str, request: Request):
    _lab_admin(request)
    path = scene_style_lab.output_path(_MIX_WORK_DIR, lab_id, "mp4")
    return FileResponse(path, media_type="video/mp4",
                        headers={"X-Scene-Style-Lab": lab_id, "Cache-Control": "no-store"})
```

랜딩 HTML은 현재 `lab_id`의 위 API만 `<video>`에 연결하며 공개 `/api/share/*`를 호출하지 않는다.

- [ ] **Step 4: 테스트 실행 및 커밋**

Run:

```powershell
py -m pytest .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_scene_style_lab_landing.py .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_share_thumb_bundle.py -q
git -C '.tracks/장면꾸미기UI코덱스' add -A
git -C '.tracks/장면꾸미기UI코덱스' commit -m "관리자 전용 시험 랜딩 추가"
```

Expected: 신규 테스트와 기존 `test_share_thumb_bundle.py` 모두 PASS.

### Task 8: 네 출구 비교표와 로컬 실제 렌더

**Files:**
- Modify: `shopping_shorts/scene_style_lab.py`
- Modify: `shopping_shorts/static/scene-style-lab.js`
- Modify: `shopping_shorts/static/scene_style_lab.html`
- Create: `tools/scene_style_lab_probe.py`
- Create: `tools/open_scene_style_lab.py`
- Create: `shopping_shorts/tests/test_scene_style_lab_compare.py`
- Create: `shopping_shorts/tests/fixtures/scene_style_lab_two_beats.json`

- [ ] **Step 1: 1프레임 오차와 훅 0개 계약 실패 테스트 작성**

```python
def test_compare_outputs_requires_zero_hook_captions_and_one_frame_tolerance():
    expected = {"hook_caption_count": 0, "body_first_start": 1.800}
    assert compare_contract(expected, {"hook_caption_count": 0, "body_first_start": 1.833})["ok"]
    assert not compare_contract(expected, {"hook_caption_count": 1, "body_first_start": 1.800})["ok"]
    assert not compare_contract(expected, {"hook_caption_count": 0, "body_first_start": 1.850})["ok"]
```

- [ ] **Step 2: 비교기와 화면 구현**

```python
FRAME_TOLERANCE = 0.034

def compare_contract(expected: dict, actual: dict) -> dict:
    checks = {
        "hook_caption_count": actual["hook_caption_count"] == 0,
        "body_first_start": abs(actual["body_first_start"] - expected["body_first_start"]) <= FRAME_TOLERANCE,
        "clean_signature": actual["clean_signature"] == expected["clean_signature"],
    }
    return {"ok": all(checks.values()), "checks": checks}
```

UI 표는 `미리보기`, `MP4`, `CapCut`, `랜딩` 열과 `훅 자막`, `본문 첫 시작`, `청소본`, `위치` 행을 표시하고 불일치는 빨간색으로 표시한다.

- [ ] **Step 3: 전체 자동 테스트 실행**

Run:

```powershell
py -m pytest .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_scene_style_lab_manifest.py .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_scene_style_hook_caption.py .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_scene_style_lab_api.py .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_scene_style_lab_render.py .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_scene_style_lab_capcut.py .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_scene_style_lab_landing.py .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/test_scene_style_lab_compare.py -q
```

Expected: 모두 PASS.

- [ ] **Step 4: 로컬 실제 MP4를 렌더하고 프레임 추출**

`tools/scene_style_lab_probe.py`는 fixture의 두 비트와 테스트 TTS/청소본을 로드해 `scene_style_lab.create_copy()`와 `render_copy()`만 호출하고, 생성된 `lab_id`와 MP4 경로를 JSON으로 출력한다. `tools/open_scene_style_lab.py`는 트랙의 FastAPI를 `127.0.0.1:8765`에 띄우고 Playwright로 `/scene_style_lab.html`과 생성된 시험 랜딩을 열어 스크린샷을 `out/scene-style-lab-probe/` 아래에 남긴다.

Run:

```powershell
py .tracks/장면꾸미기UI코덱스/tools/scene_style_lab_probe.py --fixture .tracks/장면꾸미기UI코덱스/shopping_shorts/tests/fixtures/scene_style_lab_two_beats.json --out .tracks/장면꾸미기UI코덱스/out/scene-style-lab-probe
ffmpeg -y -i .tracks/장면꾸미기UI코덱스/out/scene-style-lab-probe/lab-final.mp4 -vf "select='eq(n,27)+eq(n,53)+eq(n,54)+eq(n,70)',scale=360:-1,tile=4x1" -frames:v 1 .tracks/장면꾸미기UI코덱스/out/scene-style-lab-probe/boundary.jpg
```

Expected: 훅 프레임에는 말자막 없음; 본문 첫 프레임부터 자막 표시; 배경에 원본 자막 없음.

- [ ] **Step 5: 브라우저로 관리자 페이지와 랜딩 확인**

Run:

```powershell
py .tracks/장면꾸미기UI코덱스/tools/open_scene_style_lab.py
```

Expected: 관리자 페이지가 열리고 실제 청소본 표시, 시험 MP4 재생, CapCut 비교 초록, 시험 랜딩 재생이 모두 눈으로 확인됨.

- [ ] **Step 6: 검증 결과 기록 및 커밋**

```markdown
## 2026-09-16 로컬 실측
- 훅 말자막: 0개
- 본문 첫 자막: manifest 시작초와 1프레임 이내
- 배경: 현재 편성 청소본 서명 일치
- CapCut: 오버레이 시작/길이/위치 일치
- 랜딩: lab-final.mp4 직접 재생
```

Run:

```powershell
git -C '.tracks/장면꾸미기UI코덱스' add -A
git -C '.tracks/장면꾸미기UI코덱스' commit -m "장면꾸미기 시험판 네 출구 검증"
```

Expected: 검증 증거와 구현이 커밋됨.

### Task 9: 트랙 완료·서버 배포·실데이터 최종 확인

**Files:**
- Modify: `handoff/장면꾸미기UI코덱스.md`
- Modify: `wiki/log.d/장면꾸미기UI코덱스.md`

- [ ] **Step 1: 완료 기록 작성**

기록에는 변경 이유, 관리자 URL, 시험 산출물 위치, 훅/본문 경계 실측, CapCut 역검증, 랜딩 확인, 고객 화면 미노출을 적는다.

- [ ] **Step 2: 트랙 상태와 전체 관련 테스트 확인**

Run:

```powershell
git -C '.tracks/장면꾸미기UI코덱스' status --porcelain
py -m pytest .tracks/장면꾸미기UI코덱스/shopping_shorts/tests -q
```

Expected: worktree clean; 전체 테스트 PASS. 기존 환경 의존 테스트가 있으면 실패 원문과 이번 변경 무관 근거를 기록하되 신규 시험판 테스트는 전부 PASS여야 한다.

- [ ] **Step 3: 완료 직전 코드 리뷰와 검증 스킬 수행**

Run: `superpowers:requesting-code-review`, 이어서 `superpowers:verification-before-completion` 절차를 적용한다.

Expected: 치명 결함 없음; 검증 명령과 실제 화면 증거 확보.

- [ ] **Step 4: 트랙을 main에 병합**

Run:

```powershell
py tools/track.py finish 장면꾸미기UI코덱스
```

Expected: 검사 통과 후 `main` 병합. 실패하면 배포하지 않고 트랙에서 수정한다.

- [ ] **Step 5: main push 후 자동 배포 확인**

Run:

```powershell
git push origin main
ssh -o ConnectTimeout=15 -o StrictHostKeyChecking=no -i 'C:\Users\CH\crawling_bot_client\LightsailDefaultKey-ap-northeast-2.pem' ubuntu@3.35.251.172 "cd /home/ubuntu/lotto-stock-wiki && git rev-parse HEAD && systemctl is-active shopping-shorts && tail -20 /tmp/auto_deploy.log"
```

Expected: 서버 HEAD가 push한 main 커밋과 같고 서비스 `active`.

- [ ] **Step 6: 관리자 본인 작업 한 건을 서버에서 실제 시험**

관리자 전용 페이지에서 자막제거 완료 작업 하나를 선택하고 복사본을 만든다. 훅 말자막 숨김 상태로 시험 MP4와 CapCut 초안 및 시험 랜딩을 생성한다.

Expected:

```text
미리보기  PASS
MP4       PASS
CapCut    PASS
랜딩      PASS
원본 job 변경 0건
```

- [ ] **Step 7: 실제 산출물을 눈으로 확인하고 최종 기록**

훅 중간, 경계 직전, 본문 첫 자막 프레임을 열어 확인한다. CapCut 앱에서 시험 초안을 실제로 열고, 브라우저에서 시험 랜딩을 실제 재생한다. 확인 결과를 handoff와 log에 추가 커밋하고 push한다.
