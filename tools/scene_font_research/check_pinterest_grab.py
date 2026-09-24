"""핀터레스트 담기가 **앱 공유 링크(pin.it)·나라별 주소**도 알아보나 (2026-09-24 고객 "담기가 안 된다").

원인 실측: `_GRAB_DOMAINS`의 핀터레스트 칸에 `pinterest.com` 하나뿐이라, 휴대폰 공유 버튼이 주는
`pin.it/...`과 `pinterest.co.kr` 등이 통째로 막혔다(담기 API는 12시간 호출 0건이었다).
내려받기(`media_download`)도 같은 목록을 따로 들고 있어 한쪽만 고치면 다시 막힌다(0순위-B).
"""
import sys, pathlib, urllib.parse
ROOT = pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from shopping_shorts.app import _grab_platform
from shopping_shorts.media_download import _is_pinterest_host
fails = []
def need(ok, msg):
    print(('  통과  ' if ok else '★ 실패  ') + msg)
    if not ok: fails.append(msg)
PIN = ['https://pin.it/abc123', 'https://www.pinterest.com/pin/1/', 'https://kr.pinterest.com/pin/1/',
       'https://www.pinterest.co.kr/pin/1/', 'https://www.pinterest.jp/pin/1/', 'https://br.pinterest.com/pin/1/']
for u in PIN:
    host = urllib.parse.urlparse(u).hostname
    need(_grab_platform(u) == 'pinterest', f'① 담기가 알아본다 — {u}')
    need(_is_pinterest_host(host), f'② 내려받기도 알아본다 — {u}')
# 남의 주소를 핀터레스트로 오해하지 않는다
for u in ['https://www.youtube.com/watch?v=1', 'https://www.tiktok.com/@a/video/1', 'https://pinterest.evil.com/x']:
    need(_grab_platform(u) != 'pinterest', f'③ 핀터레스트가 아닌 주소는 안 걸린다 — {u}')
print('\n결과:', '전부 통과' if not fails else f'실패 {len(fails)}건')
sys.exit(1 if fails else 0)
