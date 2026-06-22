from pipeline.atoms.db import get_conn, init_db


def test_meta_columns_exist():
    init_db()
    conn = get_conn()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(atoms)").fetchall()}
    conn.close()
    assert "source_pub" in cols
    assert "certainty" in cols
