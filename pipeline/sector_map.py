"""미장 11섹터 ↔ 태린이 섹터 ↔ wiki L5 섹터명 매핑. 셋이 이름이 달라 1회 정의."""
SECTOR_MAP = [
    {"us": "Semiconductors", "taerini": "반도체",   "wiki": "반도체"},
    {"us": "Technology",     "taerini": "기판",     "wiki": "반도체"},
    {"us": "Industrials",    "taerini": "조선",     "wiki": "조선"},
    {"us": "Industrials",    "taerini": "전력기기", "wiki": "전력기기"},
    {"us": "Industrials",    "taerini": "로봇",     "wiki": "로봇"},
    {"us": "Health Care",    "taerini": "바이오",   "wiki": "바이오"},
    {"us": "Industrials",    "taerini": "2차전지",  "wiki": "2차전지ESS"},
]


def wiki_for(taerini_name: str):
    for row in SECTOR_MAP:
        if row["taerini"] == taerini_name:
            return row["wiki"]
    return None
