"""관계그래프 엣지 저장소(atom_edges). Phase 2 예측망의 그래프-홉 귀속에 쓰인다.

Increment 1은 LLM 0회 — stock_sector_map.json(종목→섹터),
foreign_sector_map.json(해외엔티티→섹터)으로 섹터 엣지를 시드한다.
LLM 정밀 공급망/테마 엣지(source_atom_id 채움)는 Increment 2(후속).
"""
import json
import pathlib
from datetime import datetime

from pipeline.atoms import db as _db

_ATOMS_DIR = pathlib.Path(__file__).parent


def init_edges() -> None:
    conn = _db.get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS atom_edges(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            src TEXT NOT NULL, dst TEXT NOT NULL,
            relation_type TEXT NOT NULL, source_atom_id TEXT,
            source TEXT, confidence REAL DEFAULT 1.0, created_at TEXT NOT NULL,
            UNIQUE(src, dst, relation_type)
        )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_dst ON atom_edges(dst)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_src ON atom_edges(src)")
    conn.commit()
    conn.close()


def insert_edge(src, dst, relation_type, source, source_atom_id=None, confidence=1.0) -> None:
    conn = _db.get_conn()
    conn.execute(
        """INSERT OR IGNORE INTO atom_edges
        (src,dst,relation_type,source_atom_id,source,confidence,created_at)
        VALUES (?,?,?,?,?,?,?)""",
        (src, dst, relation_type, source_atom_id, source, confidence,
         datetime.now().isoformat()))
    conn.commit()
    conn.close()


def assets_in_sector(sector: str) -> list:
    init_edges()  # 테이블 미생성 시에도 [] 안전 반환(그래프-홉 미작동, 침묵 금지 유지)
    conn = _db.get_conn()
    rows = conn.execute("SELECT DISTINCT src FROM atom_edges WHERE dst=?", (sector,)).fetchall()
    conn.close()
    return [r[0] for r in rows]


def sectors_of_asset(asset: str) -> list:
    init_edges()
    conn = _db.get_conn()
    rows = conn.execute("SELECT DISTINCT dst FROM atom_edges WHERE src=?", (asset,)).fetchall()
    conn.close()
    return [r[0] for r in rows]


def related_assets(asset: str) -> list:
    """asset과 같은 (큰)섹터에 속한 다른 자산들. 그래프 2홉: asset→섹터→자산.
    히트맵의 세부섹터명("반도체 설계 및 파운드리")에 의존하지 않고, 시드된
    종목→큰섹터("반도체") 멤버십으로 관련자산을 찾는다."""
    out = set()
    for sec in sectors_of_asset(asset):
        for a in assets_in_sector(sec):
            if a != asset:
                out.add(a)
    return sorted(out)


def _as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def seed_sector_edges(stock_sector_map: dict, foreign_sector_map: dict) -> int:
    """종목→섹터, 해외엔티티→섹터 엣지를 삽입. 반환=삽입 시도 수."""
    init_edges()
    n = 0
    for stock, secs in (stock_sector_map or {}).items():
        for sec in _as_list(secs):
            insert_edge(stock, sec, "sector_member", "sector_map")
            n += 1
    for ent, secs in (foreign_sector_map or {}).items():
        for sec in _as_list(secs):
            insert_edge(ent, sec, "foreign_sector", "foreign_map")
            n += 1
    return n


def seed_from_files() -> int:
    """실데이터 JSON에서 섹터 엣지 시드(impure 엔트리)."""
    def _load(name):
        p = _ATOMS_DIR / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return seed_sector_edges(_load("stock_sector_map.json"), _load("foreign_sector_map.json"))
