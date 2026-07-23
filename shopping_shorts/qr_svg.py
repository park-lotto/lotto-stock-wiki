"""의존성 없는 최소 QR 인코더 → SVG 문자열. (2026-07-23, 카톡공유QR 트랙)

용도: 제작소 '폰으로 보내기'의 단축 공유링크(/s/{id}, ~45자)를 QR로. 서버측 pip 추가 없이
순수 파이썬으로. 범위를 좁혀 신뢰성 확보: **바이트 모드 · EC레벨 L · 마스크0 · 버전 1~5(단일 RS 블록)**.
버전 1~5 EC-L은 전부 단일 블록이라 인터리브가 없다(구현 단순·검증 쉬움). ~45자 URL은 v3에 들어간다.

한계: 45자를 넘는 데이터는 v5(108바이트)까지만. 그보다 길면 ValueError(호출부는 단축ID로 짧게 유지).
"""

# ── GF(256) 테이블 (QR 다항식 0x11d) ──
_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11d
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _gmul(a, b):
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _rs_generator(n):
    g = [1]
    for i in range(n):
        g2 = [0] * (len(g) + 1)
        for j in range(len(g)):
            g2[j] ^= _gmul(g[j], 1)
            g2[j + 1] ^= _gmul(g[j], _EXP[i])
        g = g2
    return g


def _rs_encode(data, n):
    gen = _rs_generator(n)
    res = list(data) + [0] * n
    for i in range(len(data)):
        coef = res[i]
        if coef != 0:
            for j in range(len(gen)):
                res[i + j] ^= _gmul(gen[j], coef)
    return res[len(data):]


# 버전별 (총 코드워드, 데이터 코드워드, EC 코드워드) — EC 레벨 L, 버전 1~5 (전부 단일 블록)
_CAP_L = {1: (26, 19, 7), 2: (44, 34, 10), 3: (70, 55, 15), 4: (100, 80, 20), 5: (134, 108, 26)}
# 정렬 패턴 중심 좌표(버전 2~5는 중심 1개). 버전 1은 없음.
_ALIGN = {1: None, 2: 18, 3: 22, 4: 26, 5: 30}
# EC-L · 마스크0 의 포맷 정보 — 아래 _place_format의 좌표 순서에 맞춘 비트열(표준 라이브러리와 셀단위 대조로 확정).
_FMT_COPY1 = "001000111110111"   # 좌상단 사본(15셀)
_FMT_COPY2 = "001000111110111"   # 우/하단 사본(15셀, 동일 비트열·다른 위치)


def _encode_bits(url, version):
    total_cw, data_cw, ec_cw = _CAP_L[version]
    b = url.encode("latin-1", "replace")
    bits = []

    def put(val, n):
        for k in range(n - 1, -1, -1):
            bits.append((val >> k) & 1)

    put(0b0100, 4)          # 바이트 모드
    put(len(b), 8)          # 문자수(버전 1~9 → 8비트)
    for byte in b:
        put(byte, 8)
    # 종료자
    cap_bits = data_cw * 8
    if len(bits) > cap_bits:
        raise ValueError("data too long for version %d" % version)
    put(0, min(4, cap_bits - len(bits)))
    # 바이트 경계 패딩
    while len(bits) % 8 != 0:
        bits.append(0)
    # 코드워드
    codewords = [int("".join(str(x) for x in bits[i:i + 8]), 2) for i in range(0, len(bits), 8)]
    # 패드 코드워드 236/17 반복
    pad = [0xEC, 0x11]
    i = 0
    while len(codewords) < data_cw:
        codewords.append(pad[i % 2])
        i += 1
    ec = _rs_encode(codewords, ec_cw)
    return codewords + ec  # 단일 블록: 데이터 뒤에 EC


def _pick_version(url):
    # v1~3만 사용(표준 라이브러리와 셀단위 대조로 스캔 검증된 경로). 프로덕션 공유링크는
    # /s/{짧은id} ~49자라 v3(바이트 53)에 넉넉히 든다. v4+는 검증범위 밖 → 호출부가 URL을 짧게 유지.
    for v in (1, 2, 3):
        _, data_cw, _ = _CAP_L[v]
        if 4 + 8 + 8 * len(url.encode("latin-1", "replace")) <= data_cw * 8:
            return v
    raise ValueError("URL too long for QR v1-3 (keep share URL short)")


def _build_matrix(url):
    version = _pick_version(url)
    size = 17 + 4 * version
    m = [[None] * size for _ in range(size)]      # None=미설정, 0/1
    reserved = [[False] * size for _ in range(size)]

    def set_fn(r, c, v):
        m[r][c] = v
        reserved[r][c] = True

    # 파인더 + 분리자
    def finder(r0, c0):
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                r, c = r0 + dr, c0 + dc
                if 0 <= r < size and 0 <= c < size:
                    if dr in (-1, 7) or dc in (-1, 7):
                        set_fn(r, c, 0)   # 분리자
                    else:
                        inner = 0 <= dr <= 6 and 0 <= dc <= 6
                        ring = dr in (0, 6) or dc in (0, 6)
                        core = 2 <= dr <= 4 and 2 <= dc <= 4
                        set_fn(r, c, 1 if (ring or core) else 0)
    finder(0, 0)
    finder(0, size - 7)
    finder(size - 7, 0)

    # 타이밍 패턴
    for i in range(8, size - 8):
        v = 1 if i % 2 == 0 else 0
        if not reserved[6][i]:
            set_fn(6, i, v)
        if not reserved[i][6]:
            set_fn(i, 6, v)

    # 정렬 패턴(버전 2~5 중심 1개)
    ap = _ALIGN[version]
    if ap is not None:
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                r, c = ap + dr, ap + dc
                ring = dr in (-2, 2) or dc in (-2, 2)
                center = dr == 0 and dc == 0
                set_fn(r, c, 1 if (ring or center) else 0)

    # 다크 모듈
    set_fn(4 * version + 9, 8, 1)

    # 포맷 정보 영역 예약(값은 나중에)
    for i in range(9):
        if not reserved[8][i]:
            reserved[8][i] = True
        if not reserved[i][8]:
            reserved[i][8] = True
    for i in range(8):
        reserved[8][size - 1 - i] = True
        reserved[size - 1 - i][8] = True

    # 데이터 배치(지그재그) + 마스크0
    data = _build_matrix._last_data
    bit_idx = 0
    col = size - 1
    upward = True
    while col > 0:
        if col == 6:
            col -= 1        # 타이밍 열 건너뜀
        rng = range(size - 1, -1, -1) if upward else range(size)
        for r in rng:
            for c in (col, col - 1):
                if reserved[r][c]:
                    continue
                bit = 0
                if bit_idx < len(data) * 8:
                    byte = data[bit_idx // 8]
                    bit = (byte >> (7 - (bit_idx % 8))) & 1
                    bit_idx += 1
                if (r + c) % 2 == 0:       # 마스크0
                    bit ^= 1
                m[r][c] = bit
        col -= 2
        upward = not upward

    # 포맷 정보 기록(EC-L·마스크0) — 좌표 순서·비트열은 표준 라이브러리와 셀단위 대조로 확정.
    coords1 = [(0, 8), (1, 8), (2, 8), (3, 8), (4, 8), (5, 8), (7, 8), (8, 8),
               (8, 7), (8, 5), (8, 4), (8, 3), (8, 2), (8, 1), (8, 0)]
    for i, (r, c) in enumerate(coords1):
        m[r][c] = int(_FMT_COPY1[i])
    coords2 = [(8, size - 1 - i) for i in range(8)] + [(size - 7 + i, 8) for i in range(7)]
    for i, (r, c) in enumerate(coords2):
        m[r][c] = int(_FMT_COPY2[i])
    return m, size


def qr_svg(url, scale=10, quiet=4):
    """URL → QR SVG 문자열. scale=모듈 px, quiet=여백(모듈)."""
    data = _encode_bits(url, _pick_version(url))
    _build_matrix._last_data = data
    m, size = _build_matrix(url)
    dim = (size + quiet * 2) * scale
    rects = []
    for r in range(size):
        for c in range(size):
            if m[r][c] == 1:
                x = (c + quiet) * scale
                y = (r + quiet) * scale
                rects.append(f'<rect x="{x}" y="{y}" width="{scale}" height="{scale}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{dim}" height="{dim}" '
            f'viewBox="0 0 {dim} {dim}" shape-rendering="crispEdges">'
            f'<rect width="{dim}" height="{dim}" fill="#fff"/>'
            f'<g fill="#000">{"".join(rects)}</g></svg>')


_build_matrix._last_data = []
