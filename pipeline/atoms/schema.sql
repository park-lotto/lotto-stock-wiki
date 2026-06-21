CREATE TABLE IF NOT EXISTS atoms (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL,

    -- 소스
    source_type TEXT NOT NULL,
    source_name TEXT,
    source_trust TEXT DEFAULT 'D',
    raw_file TEXT,

    -- 분류
    layer TEXT,
    sector TEXT,
    asset TEXT,
    asset_level TEXT DEFAULT 'sector',

    -- 신호
    signal TEXT NOT NULL DEFAULT 'neutral',
    event_type TEXT DEFAULT 'news',
    magnitude TEXT DEFAULT 'minor',
    content_type TEXT DEFAULT 'fact',
    strength_score INTEGER DEFAULT 1,

    -- 유효기간
    validity_type TEXT DEFAULT 'permanent',
    validity_until TEXT,
    is_active INTEGER DEFAULT 1,

    -- 내용 (원문 보존)
    content TEXT NOT NULL,

    -- 관계 그래프 (JSON: [{type, target_id}])
    relations TEXT DEFAULT '[]',

    -- 텔레그램 2층 모델 필드
    stance_key TEXT,
    mention_channels TEXT,
    mention_count INTEGER DEFAULT 1,
    msg_ts TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_atoms_date ON atoms(date);
CREATE INDEX IF NOT EXISTS idx_atoms_sector ON atoms(sector);
CREATE INDEX IF NOT EXISTS idx_atoms_signal ON atoms(signal);
CREATE INDEX IF NOT EXISTS idx_atoms_asset ON atoms(asset);
CREATE INDEX IF NOT EXISTS idx_atoms_is_active ON atoms(is_active);
CREATE INDEX IF NOT EXISTS idx_atoms_validity ON atoms(validity_until);
CREATE INDEX IF NOT EXISTS idx_atoms_source_trust ON atoms(source_trust);
CREATE INDEX IF NOT EXISTS idx_atoms_stance_key ON atoms(stance_key);
