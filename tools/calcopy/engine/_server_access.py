# -*- coding: utf-8 -*-
"""우리 서버 접속 정보(우리 PC 전용) — topic_find 발굴 DB 길이 쓴다. ★고객 설치팩 엔진 묶음에 넣지 않는다(engine_bundle FORBIDDEN, 관제 234)."""
from pathlib import Path

REF_SSH = "ubuntu@3.35.251.172"
REF_KEY = str(Path.home() / "crawling_bot_client" / "LightsailDefaultKey-ap-northeast-2.pem").replace("\\", "/")  # PC 마다 홈이 다르다(CH·TheRose)
