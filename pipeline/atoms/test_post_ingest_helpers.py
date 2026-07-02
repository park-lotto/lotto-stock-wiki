import pytest
from pathlib import Path
import pipeline.atoms.db as dbmod
from pipeline.atoms.post_ingest import _parse_post_header, get_done_post_files, get_pending_post


@pytest.fixture(autouse=True)
def _temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "t.db")
    yield


def test_parse_header_blog_label(tmp_path):
    p = tmp_path / "2026-06-21_0900_바이오.md"
    p.write_text(
        "# 바이오\n- **출처**: pokara61 블로그\n- **날짜**: 2026-06-21\n"
        "- **링크**: [원문](https://blog.naver.com/pokara61/1)\n## 본문\n내용",
        encoding="utf-8")
    h = _parse_post_header(p, "출처")
    assert h["source_name"] == "pokara61"
    assert h["date"] == "2026-06-21"
    assert "blog.naver.com/pokara61/1" in h["link"]


def test_parse_header_youtube_label(tmp_path):
    p = tmp_path / "2026-06-05_0905_주식.md"
    p.write_text(
        "# 주식\n- **채널**: UP_CYCLE_STOCK\n- **날짜**: 2026-06-05\n"
        "- **링크**: [유튜브](https://www.youtube.com/watch?v=abc)\n## 핵심 요약\n내용",
        encoding="utf-8")
    h = _parse_post_header(p, "채널")
    assert h["source_name"] == "UP_CYCLE_STOCK"
    assert h["date"] == "2026-06-05"
    assert "youtube.com/watch?v=abc" in h["link"]


def test_get_done_post_files_by_source_type(tmp_path):
    dbmod.init_db(); dbmod.migrate_db()
    import uuid
    from datetime import datetime
    conn = dbmod.get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO atoms (id,date,source_type,source_name,source_trust,"
        "raw_file,layer,sector,asset,asset_level,signal,event_type,magnitude,"
        "content_type,strength_score,content,relations,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), "2026-06-05", "youtube", "UP_CYCLE_STOCK", 3,
         "raw/yt/2026-06-05_0905_주식.md", "L5", "반도체", "반도체", "sector",
         "neutral", "report", "minor", "fact", 2, "x", "[]", datetime.now().isoformat()),
    )
    conn.commit(); conn.close()
    done = get_done_post_files("youtube")
    assert "2026-06-05_0905_주식.md" in done


def test_parse_header_news_individual(tmp_path):
    """개별기사: 출처 있음 → source_name = 언론사"""
    p = tmp_path / "2026-06-21_0001_방산기사.md"
    p.write_text(
        "# 방산\n- **출처**: 아시아경제\n- **키워드**: 방산\n- **날짜**: 2026-06-21\n",
        encoding="utf-8")
    h = _parse_post_header(p, ["출처", "키워드"])
    assert h["source_name"] == "아시아경제"


def test_parse_header_news_bundle(tmp_path):
    """묶음: 출처 없음, 키워드만 → source_name = 키워드"""
    p = tmp_path / "2026-06-21_0002_호르무즈묶음.md"
    p.write_text(
        "# 호르무즈\n- **키워드**: 호르무즈\n- **날짜**: 2026-06-21\n",
        encoding="utf-8")
    h = _parse_post_header(p, ["출처", "키워드"])
    assert h["source_name"] == "호르무즈"


def test_parse_header_blog_str_regression(tmp_path):
    """blog 회귀: header_label 문자열 그대로 동작"""
    p = tmp_path / "2026-06-21_0003_블로그.md"
    p.write_text(
        "# 블로그\n- **출처**: pokara61 블로그\n- **날짜**: 2026-06-21\n",
        encoding="utf-8")
    h = _parse_post_header(p, "출처")
    assert h["source_name"] == "pokara61"


def test_get_pending_post_excludes_non_pattern_files(tmp_path, monkeypatch):
    """_FNAME 패턴 안 맞는 파일(스크립트 등)은 제외"""
    dbmod.init_db(); dbmod.migrate_db()
    import pipeline.atoms.post_ingest as pi
    monkeypatch.setattr(pi, "_ROOT", tmp_path)

    # 테스트용 소스 디렉토리 생성
    d = tmp_path / "raw" / "yt"
    d.mkdir(parents=True)

    # 정상 파일 (YYYY-MM-DD_NNNN_제목 패턴)
    (d / "2026-06-06_1801_real_video.md").write_text("x", encoding="utf-8")
    # 스크립트 파일 (패턴 미매치 → 제외되어야 함)
    (d / "script_소부장자금순환_20260604_gemini.md").write_text("x", encoding="utf-8")

    cfg = {
        "source_type": "youtube",
        "dir": "raw/yt",
        "header_label": "채널",
        "registry": "youtube_registry.json"
    }

    names = [p.name for p in get_pending_post(cfg)]
    assert "2026-06-06_1801_real_video.md" in names
    assert "script_소부장자금순환_20260604_gemini.md" not in names


def test_ingest_post_routes_youtube_daytrading_profile(monkeypatch, tmp_path):
    import json
    from pipeline.atoms import post_ingest, profiles

    monkeypatch.setattr(profiles, "youtube_channel_profile", lambda name: "데이트레이딩")

    called = {}

    def fake_extract_daytrading(md_path):
        called["path"] = md_path
        return {"trades": [{"name": "삼성전자", "entry_price": "71000",
                             "stop_loss": "69500", "quote": "진입"}]}

    monkeypatch.setattr(post_ingest, "_extract_daytrading", fake_extract_daytrading)
    monkeypatch.setattr(post_ingest, "insert_atom", lambda a: called.setdefault("inserted", []).append(a))
    monkeypatch.setattr(post_ingest, "embed_and_store", lambda a: None)
    monkeypatch.setattr(post_ingest, "_mark_processed", lambda *a, **k: None)
    monkeypatch.setattr(post_ingest, "_save_artifact", lambda *a, **k: None)

    md = tmp_path / "2026-07-02_1_테스트채널.md"
    md.write_text("**채널**: 테스트채널\n**날짜**: 2026-07-02\n", encoding="utf-8")
    cfg = {"source_type": "youtube", "dir": "raw/yt", "header_label": "채널",
           "registry": "youtube_registry.json"}

    n = post_ingest.ingest_post(md, cfg)
    assert n == 1
    assert called["inserted"][0]["asset"] == "삼성전자"
    assert json.loads(called["inserted"][0]["structured_fields"])["entry_price"] == "71000"


def test_ingest_post_falls_back_to_general_when_daytrading_finds_no_trades(monkeypatch, tmp_path):
    """하이브리드 오버라이드: 채널은 데이트레이딩 프로필이지만 이 영상은 매매
    언급이 없으면(trades 빈 배열) 일반 POST_PROMPT 경로로 폴백해야 한다."""
    from pipeline.atoms import post_ingest, profiles

    monkeypatch.setattr(profiles, "youtube_channel_profile", lambda name: "데이트레이딩")
    monkeypatch.setattr(post_ingest, "_extract_daytrading", lambda p: {"trades": []})
    monkeypatch.setattr(post_ingest, "extract_post",
                         lambda p: {"target_kind": "market", "market_direction": "혼조"})
    called = {}
    monkeypatch.setattr(post_ingest, "insert_atom", lambda a: called.setdefault("inserted", []).append(a))
    monkeypatch.setattr(post_ingest, "embed_and_store", lambda a: None)
    monkeypatch.setattr(post_ingest, "_mark_processed", lambda *a, **k: None)
    monkeypatch.setattr(post_ingest, "_save_artifact", lambda *a, **k: None)

    md = tmp_path / "2026-07-02_1_테스트채널.md"
    md.write_text("**채널**: 테스트채널\n**날짜**: 2026-07-02\n", encoding="utf-8")
    cfg = {"source_type": "youtube", "dir": "raw/yt", "header_label": "채널",
           "registry": "youtube_registry.json"}

    n = post_ingest.ingest_post(md, cfg)
    assert n == 1
    assert called["inserted"][0]["asset_level"] == "market"


def test_ingest_post_non_daytrading_profile_falls_through_to_general(monkeypatch, tmp_path):
    """게이트 협소화 회귀 테스트: YOUTUBE_PROFILES에 존재하지만 '데이트레이딩'이
    아닌 프로필(미래에 추가될 신규 프로필 시뮬레이션)은 데이트레이딩 추출 경로를
    타지 않고 일반 extract_post 경로로 빠져야 한다."""
    from pipeline.atoms import post_ingest, profiles

    monkeypatch.setattr(post_ingest, "YOUTUBE_PROFILES",
                         {**post_ingest.YOUTUBE_PROFILES, "가짜프로필": {"prompt": "x"}})
    monkeypatch.setattr(profiles, "youtube_channel_profile", lambda name: "가짜프로필")

    def boom(md_path):
        raise AssertionError("_extract_daytrading should NOT be called for non-daytrading profile")

    monkeypatch.setattr(post_ingest, "_extract_daytrading", boom)

    called = {}

    def fake_extract_post(md_path):
        called["extract_post"] = True
        return {"target_kind": "market", "market_direction": "혼조"}

    monkeypatch.setattr(post_ingest, "extract_post", fake_extract_post)
    monkeypatch.setattr(post_ingest, "insert_atom", lambda a: called.setdefault("inserted", []).append(a))
    monkeypatch.setattr(post_ingest, "embed_and_store", lambda a: None)
    monkeypatch.setattr(post_ingest, "_mark_processed", lambda *a, **k: None)
    monkeypatch.setattr(post_ingest, "_save_artifact", lambda *a, **k: None)

    md = tmp_path / "2026-07-02_1_테스트채널.md"
    md.write_text("**채널**: 테스트채널\n**날짜**: 2026-07-02\n", encoding="utf-8")
    cfg = {"source_type": "youtube", "dir": "raw/yt", "header_label": "채널",
           "registry": "youtube_registry.json"}

    n = post_ingest.ingest_post(md, cfg)
    assert n == 1
    assert called.get("extract_post") is True
    assert called["inserted"][0]["asset_level"] == "market"
