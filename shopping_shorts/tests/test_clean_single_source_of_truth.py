# -*- coding: utf-8 -*-
"""자막제거 관련 판단은 **각각 한 곳**에만 있어야 한다 (2026-08-27).

★하루에 같은 뿌리로 회귀가 다섯 번 났다. 전부 "판단이 여러 군데 적혀 있어서"였다:
    1. clean_thumb  — AFTER 칸 404(검은 화면)
    2. poster       — 5단계 배경에 원본 자막
    3. beatframe    — 6단계 꾸미기 배경에 원본 자막·워터마크
    4. capcut       — 캡컷 내보내기에 원본 자막
    5. 좌우 어긋남   — 세 번 고쳐서야 컷 단위에 도달

  2단계를 완성본 1편 청소로 바꾸자 clean_sources가 비었는데, 그걸 '자막제거 했나'의
  판정으로 쓰던 곳들이 **조용히 원본을 보여줬다**. 한 곳을 고치면 다음이 나왔다.

  이 파일은 그 판단들이 다시 흩어지지 않게 **모양을 고정**한다. 실패하면
  "새 코드가 판단을 또 손으로 적었다"는 뜻이다 — 공용 함수를 쓰게 고쳐라.
"""
import inspect

from shopping_shorts import app as A
from shopping_shorts import mix_pipeline as mp


def _src(fn):
    return inspect.getsource(fn)


class Test판단은_각각_한곳:
    def test_청소_단위_판정은_clean_strategy만(self):
        """완성본이냐 소스별이냐 — _FINAL_CLEAN을 직접 읽는 곳은 정의와 그 함수뿐."""
        text = inspect.getsource(mp)
        reads = [l.strip() for l in text.splitlines()
                 if "_FINAL_CLEAN" in l and not l.strip().startswith("#")]
        assert len(reads) == 2, f"_FINAL_CLEAN을 직접 읽는 곳이 늘었다: {reads}"

    def test_화면재료_판정은_beat_materials만(self):
        """scene_override 우선 + alternates 포함 규칙을 손으로 또 적으면 안 된다."""
        text = inspect.getsource(mp)
        needle = ".get(" + chr(34) + "scene_override" + chr(34) + ")"
        reads = [l.strip() for l in text.splitlines()
                 if needle in l and not l.strip().startswith("#")]
        assert len(reads) == 1, f"재료 판정이 또 손으로 적혔다: {reads}"

    def test_화면출처_판정은_clean_frame_src만(self):
        """poster·beatframe이 clean_sources를 직접 보면 원본이 새어 나간다.

        ★2026-08-30: 프레임을 뜨는 몸통이 `_beatframe_file`로 빠졌다(썸네일로 보내기가
          같은 그림을 써야 해서). 판단은 **한 곳으로 더 모인 것**이라 가드의 뜻은 그대로다 —
          이제 그 함수가 공용 판단을 쓰는지 본다. 엔드포인트는 그 함수만 부르면 된다.
        """
        for fn in (A._beatframe_file,):
            body = _src(fn)
            assert "_clean_frame_src" in body, f"{fn.__name__}이 공용 판단을 안 쓴다"
            assert 'get("clean_sources")' not in body, \
                f"{fn.__name__}이 clean_sources를 또 직접 본다"
        # 엔드포인트는 스스로 판정하지 않는다 — 몸통에 맡긴다(두 벌 방지)
        ep = _src(A.api_produce_mix_beatframe)
        assert "_beatframe_file" in ep, "beatframe 엔드포인트가 공용 몸통을 안 쓴다"
        assert 'get("clean_sources")' not in ep and "_clean_frame_src" not in ep, \
            "엔드포인트가 출처 판정을 또 적었다"

    def test_컷_계획은_video_assemble_한곳에서(self):
        """★렌더·캡컷·ZIP·썸네일이 같은 계획을 봐야 화면이 안 갈린다."""
        body = _src(mp.final_clip_pairs)
        assert "plan_beat_clips_for" in body, \
            "컷 계획을 직접 계산하면 렌더와 어긋난다"


class Test완성본_경로에서_화면이_새지_않는다:
    """clean_sources가 비어도(=완성본 1편 청소) 화면은 청소본을 봐야 한다."""

    def _job(self, tmp_path):
        cvp = tmp_path / "clean_preview.mp4"
        cvp.write_text("x")
        return {"clean_sources": None, "clean_status": "ready",
                "clean_video_path": str(cvp),
                "edit_plan": {"beats": [
                    {"beat_idx": 0, "target_seconds": 3.0,
                     "primary": {"video_id": "s0", "start": 0.0, "end": 3.0},
                     "alternates": []}]}}

    def test_소스별이_없어도_완성본을_가리킨다(self, tmp_path, monkeypatch):
        monkeypatch.setattr(A, "_resolve_sources", lambda j, w: {})
        srcs, final, ratio, tag, _fresh = A._clean_frame_src(self._job(tmp_path), tmp_path, 0)
        assert srcs == {}
        assert final is not None, "완성본을 안 쓰면 원본 자막이 화면에 남는다"
        assert tag.startswith("_clean"), "캐시 이름을 안 가르면 청소 전 그림이 재사용된다"

    def test_청소_전이면_아무것도_안_준다(self, tmp_path):
        j = self._job(tmp_path); j["clean_status"] = None
        assert A._clean_frame_src(j, tmp_path, 0) [:4] == ({}, None, None, "")

    def test_소스별이_있으면_그걸_쓴다(self, tmp_path):
        j = self._job(tmp_path); j["clean_sources"] = {"s0": "/c/s0.mp4"}
        srcs, final, _, tag, _fresh = A._clean_frame_src(j, tmp_path, 0)
        assert srcs and final is None and tag == "_clean"


class Test캡컷도_청소본을_쓴다:
    # ★2026-09-27: 캡컷·ZIP 의 재료 판단이 mix_pipeline.export_sources_for 한 곳으로 옮겨갔다(clean_route = 렌더와 같은 규칙).
    #   종전 소스 글자 검사(라우트 본문에 split_final… 글자가 있나)는 호출이 옮겨가면 거짓으로 깨지고 글자만 남기면 통과한다
    #   → **실제 job 으로 불러서** 확인한다.
    def test_완성본_조각으로_갈아끼운다(self, monkeypatch, tmp_path):
        """소스별 청소본이 없으면 청소 완성본을 컷별로 잘라 넘긴다 — 캡컷·ZIP 둘 다, 원본이 나가면 안 된다."""
        import json
        from pathlib import Path
        from shopping_shorts.store import Store
        from shopping_shorts.tests.test_app_export import _mk_video, _seed
        client = _seed(monkeypatch, tmp_path)
        store = Store(A.DB_PATH)
        store.update_mix_job("j1", subtitle_removal=1, clean_status="ready", clean_video_path=None)
        _mk_video(A._MIX_WORK_DIR / "j1" / f"final_clean_{mp._clean_sig(store.get_mix_job('j1'))}.mp4", 4)
        r = client.get("/api/mix/capcut/j1", params={"base": "C:/capcutproject/CapCut Drafts"})
        assert r.status_code == 200, r.text
        vids = [m for m in json.loads(r.json()["texts"]["draft_content.json"])["materials"]["videos"]
                if m["type"] == "video"]
        assert vids and {m["material_name"] for m in vids} == {"s0"}, \
            "캡컷 미디어가 소스 영상별(s0)이 아니다"
        ex = mp.export_sources_for(store, store.get_mix_job("j1"), "j1", A._MIX_WORK_DIR / "j1", 0)
        assert ex["route"] == "final" and all(Path(p).name.startswith("capcut_src_") for p in ex["source_video_paths"].values()), "청소 완성본 조각을 안 쓴다 — 원본 자막이 살아난다"

    def test_자르기_실패는_원본으로_폴백하지_않는다(self, monkeypatch, tmp_path):
        """★조용한 폴백이 최악이다 — 자막 남은 결과물을 캡컷에서야 알게 된다. 캡컷 500 · ZIP 조각 409."""
        from shopping_shorts.store import Store
        from shopping_shorts.tests.test_app_export import _mk_video, _seed
        client = _seed(monkeypatch, tmp_path)
        store = Store(A.DB_PATH)
        store.update_mix_job("j1", subtitle_removal=1, clean_status="ready", clean_video_path=None)
        _mk_video(A._MIX_WORK_DIR / "j1" / f"final_clean_{mp._clean_sig(store.get_mix_job('j1'))}.mp4", 4)

        def boom(*a, **k):
            raise RuntimeError("자르기 실패")
        monkeypatch.setattr(mp, "_build_source_file", boom)
        r = client.get("/api/mix/capcut/j1", params={"base": "C:/capcutproject/CapCut Drafts"})
        assert r.status_code == 500, "자르기 실패를 막지 않는다"
        r2 = client.get("/api/mix/export/j1", params={"part": "sources"})
        assert r2.status_code == 409, "ZIP 이 자르기 실패 뒤 원본 조각으로 폴백했다"
