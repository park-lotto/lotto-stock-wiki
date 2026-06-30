"""KIS 실시간 WebSocket — 코스피·코스닥 지수 스트림.

서버 시작 시 백그라운드 스레드로 실행.
최신값은 _LIVE dict에 보관 → server.py에서 직접 읽음.

_LIVE = {
    "0001": {"price": 2848.11, "change_rate": -0.20, "ts": 1710000000.0},
    "1001": {"price": 923.45,  "change_rate":  0.13, "ts": 1710000000.1},
}
"""
import json, os, time, threading, logging, requests
from dotenv import load_dotenv

load_dotenv()

_KEY    = os.getenv("KIS_APP_KEY", "")
_SECRET = os.getenv("KIS_APP_SECRET", "")

WS_URL = "ws://ops.koreainvestment.com:21000"
REST   = "https://openapi.koreainvestment.com:9443"

# 구독 목록: (TR_ID, TR_KEY, 저장키)
# H0UPCNT0 = 국내주식 업종지수 실시간체결
# H0ZFCNT0 = 코스피200 야간선물 실시간체결 (101W9=근월물 자동해석)
SUBS = [
    ("H0UPCNT0", "0001",  "0001"),     # 코스피
    ("H0UPCNT0", "1001",  "1001"),     # 코스닥
    ("H0ZFCNT0", "101W9", "101W9"),    # 코스피200 야간선물
]

# 수신 데이터 필드 위치 (caret 구분) — H0UPCNT0 / H0ZFCNT0 공통
_F_CODE  = 0   # 종목/업종코드
_F_PRICE = 2   # 현재가(지수/선물가격)
_F_SIGN  = 3   # 전일대비부호 (2=상승, 5=보합, 4=하락)
_F_DIFF  = 4   # 전일대비
_F_RATE  = 5   # 등락률

_LIVE: dict = {}   # 외부에서 읽는 실시간 데이터 저장소
_running      = False
_ws_thread: threading.Thread | None = None
_connected    = False
_sub_ok: set  = set()
_AES_KEYS: dict = {}   # tr_key → {"key": bytes, "iv": bytes}  (암호화 구독용)

logger = logging.getLogger("kis_ws")


def _aes_decrypt(data_b64: str, key_str: str, iv_str: str) -> str:
    """KIS WebSocket AES-256-CBC 복호화."""
    import base64
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    key = key_str.encode("utf-8")   # 32 bytes → AES-256
    iv  = iv_str.encode("utf-8")    # 16 bytes → CBC IV
    raw = base64.b64decode(data_b64)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    dec = cipher.decryptor()
    plain = dec.update(raw) + dec.finalize()
    # PKCS7 unpad
    pad = plain[-1]
    return plain[:-pad].decode("utf-8")


# ── WebSocket 승인키 발급 ──────────────────────────────────
def _get_approval_key() -> str:
    r = requests.post(
        f"{REST}/oauth2/Approval",
        json={"grant_type": "client_credentials", "appkey": _KEY, "secretkey": _SECRET},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["approval_key"]


# ── 구독 메시지 생성 ──────────────────────────────────────
def _sub_msg(approval_key: str, tr_id: str, tr_key: str) -> str:
    return json.dumps({
        "header": {
            "approval_key": approval_key,
            "custtype": "P",
            "tr_type": "1",      # 1=등록
            "content-type": "utf-8",
        },
        "body": {"input": {"tr_id": tr_id, "tr_key": tr_key}},
    })


# ── 수신 메시지 파싱 ──────────────────────────────────────
# TR_ID → 저장키 매핑 (구독 등록 시 채움)
_TR_KEY_MAP: dict = {}   # tr_key(수신값) → store_key


def _parse(raw: str):
    """0|H0UPCNT0|001|0001^2848.11^... → _LIVE 업데이트."""
    if raw.startswith("{"):
        try:
            d = json.loads(raw)
            if d.get("header", {}).get("tr_id") == "PINGPONG":
                return "PING"
        except Exception:
            pass
        return None

    parts = raw.split("|")
    if len(parts) < 4:
        return None
    tr_id = parts[1]
    if tr_id not in {t for t, _, __ in SUBS}:
        return None

    fields = parts[3].split("^")
    try:
        raw_code = fields[_F_CODE]
        store_key = _TR_KEY_MAP.get(raw_code, raw_code)  # 야간선물은 실제코드→101W9로 매핑
        price = float(fields[_F_PRICE])
        sign  = fields[_F_SIGN]
        # 업종지수(H0UPCNT0) 필드 배열: 2=현재가 3=부호 4=전일대비 5=누적거래량 ... 9=전일대비율(등락률)
        # ⚠️ 등락률은 field 9 (field 5는 거래량). 다른 TR은 기존 위치 유지.
        rate_idx = 9 if tr_id == "H0UPCNT0" else _F_RATE
        rate = float(fields[rate_idx])
        if sign == "4":
            rate = -abs(rate)
        elif sign == "2":
            rate = abs(rate)
        _LIVE[store_key] = {"price": price, "change_rate": rate, "ts": time.time()}
    except (IndexError, ValueError):
        pass
    return None


# ── WebSocket 루프 (재연결 포함) ──────────────────────────
def _ws_loop():
    import websocket as _wsc

    while _running:
        try:
            approval_key = _get_approval_key()
        except Exception as e:
            logger.warning(f"[KIS_WS] 승인키 발급 실패: {e} — 30초 후 재시도")
            time.sleep(30)
            continue

        logger.info("[KIS_WS] 연결 중...")

        def on_open(ws):
            global _connected
            for tr_id, tr_key, store_key in SUBS:
                _TR_KEY_MAP[tr_key] = store_key
                ws.send(_sub_msg(approval_key, tr_id, tr_key))
            _connected = True
            logger.info(f"[KIS_WS] 구독 요청: {[(t,k) for t,k,_ in SUBS]}")

        def on_message(ws, msg):
            global _connected
            if '"SUBSCRIBE SUCCESS"' in msg:
                try:
                    d = json.loads(msg)
                    hdr = d.get("header", {})
                    tr_key = hdr.get("tr_key", "")
                    out    = d.get("body", {}).get("output", {})
                    if tr_key:
                        _sub_ok.add(tr_key)
                        if out.get("key") and out.get("iv"):
                            _AES_KEYS[tr_key] = {"key": out["key"], "iv": out["iv"]}
                            logger.info(f"[KIS_WS] 구독 확인(암호화): {tr_key}")
                        else:
                            logger.info(f"[KIS_WS] 구독 확인(평문): {tr_key}")
                except Exception:
                    pass
                return
            # 암호화 메시지: 1|TR_ID|count|base64data
            if not msg.startswith("{") and msg.startswith("1|"):
                try:
                    parts = msg.split("|", 3)
                    if len(parts) == 4:
                        tr_id = parts[1]
                        enc_data = parts[3]
                        # _AES_KEYS는 tr_key 기준이므로 tr_id로 매핑 필요
                        for sub_tr_id, sub_key, store_key in SUBS:
                            if sub_tr_id == tr_id and sub_key in _AES_KEYS:
                                aes = _AES_KEYS[sub_key]
                                plain = _aes_decrypt(enc_data, aes["key"], aes["iv"])
                                fake_msg = f"0|{tr_id}|001|{plain}"
                                _parse(fake_msg)
                                break
                except Exception as e:
                    logger.debug(f"[KIS_WS] 복호화 실패: {e}")
                return
            result = _parse(msg)
            if result == "PING":
                ws.send(msg)  # PONG

        def on_error(ws, err):
            global _connected
            _connected = False
            logger.warning(f"[KIS_WS] 오류: {err}")

        def on_close(ws, code, msg):
            global _connected
            _connected = False
            logger.info(f"[KIS_WS] 연결 끊김 ({code}) — 5초 후 재연결")

        ws = _wsc.WebSocketApp(
            WS_URL,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        ws.run_forever(ping_interval=30, ping_timeout=10)

        if not _running:
            break
        time.sleep(5)  # 재연결 대기


# ── 공개 API ─────────────────────────────────────────────
def start():
    """서버 시작 시 한 번 호출 → 백그라운드 스레드 가동."""
    global _running, _ws_thread
    if _ws_thread and _ws_thread.is_alive():
        return
    if not _KEY or not _SECRET:
        logger.warning("[KIS_WS] KIS_APP_KEY/SECRET 없음 — WebSocket 비활성")
        return
    _running = True
    _ws_thread = threading.Thread(target=_ws_loop, daemon=True, name="kis-ws")
    _ws_thread.start()
    logger.info("[KIS_WS] 백그라운드 스레드 시작")


def stop():
    global _running
    _running = False


def get(code: str) -> dict | None:
    """최신 실시간값 반환. 데이터 없으면 None."""
    d = _LIVE.get(code)
    if d and time.time() - d["ts"] < 60:  # 60초 이내 수신분만 신뢰
        return d
    return None


def is_alive() -> bool:
    return bool(_ws_thread and _ws_thread.is_alive() and _connected)


def status() -> dict:
    """디버그용 상태 반환."""
    return {
        "thread": bool(_ws_thread and _ws_thread.is_alive()),
        "connected": _connected,
        "subscribed": sorted(_sub_ok),
        "live_keys": list(_LIVE.keys()),
    }
