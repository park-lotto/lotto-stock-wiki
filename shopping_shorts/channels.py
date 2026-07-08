"""벤치마킹 엑셀 → 채널 목록 로더."""
import re
from openpyxl import load_workbook
from shopping_shorts.config import EXCEL_PATH

_IG_RE = re.compile(r"instagram\.com/([A-Za-z0-9_.]+)")


def username_from_url(url):
    """인스타 URL에서 username 추출. 인스타 URL 아니면 None."""
    if not url:
        return None
    m = _IG_RE.search(str(url).strip())
    if not m:
        return None
    return m.group(1).strip("/")


def parse_rows(rows):
    """엑셀 rows(values_only) → 채널 dict 리스트. 헤더 1행 스킵, 무효 URL 제외."""
    channels = []
    for row in rows[1:]:
        name = row[0]
        url = row[1] if len(row) > 1 else None
        followers = row[2] if len(row) > 2 else None
        inpock = row[3] if len(row) > 3 else None
        username = username_from_url(url)
        if not username:
            continue
        channels.append({
            "name": name,
            "username": username,
            "followers": int(followers) if followers else 0,
            "inpock": inpock or "",
        })
    return channels


def load_channels(excel_path=EXCEL_PATH):
    """엑셀 파일 열어 채널 리스트 반환."""
    wb = load_workbook(excel_path, data_only=True, read_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    return parse_rows(rows)
