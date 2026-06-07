SIGNAL_TYPES = [
    "bullish",   # 상승 재료
    "bearish",   # 하락 재료
    "neutral",   # 현황/팩트 (방향 없음)
    "risk",      # 리스크 (방향 미결)
    "catalyst",  # 트리거 (곧 터질 이벤트)
    "conflict",  # 충돌 (상반된 신호, 둘 다 보존)
    "data",      # 순수 수치
]

EVENT_TYPES = [
    "earnings",   # 실적/어닝/가이던스
    "policy",     # 정책/규제/금리
    "supply",     # 수급 (외국인·기관 매매)
    "demand",     # 제품·서비스 수요
    "consensus",  # 컨센서스·TP 변화
    "momentum",   # 가속화·모멘텀
    "macro",      # 매크로 지표
    "news",       # 뉴스·이슈·공시
    "report",     # 리포트·분석
    "event",      # IR·컨퍼런스·일정
]

ASSET_LEVELS = [
    "stock",   # 개별 종목
    "sector",  # 섹터
    "market",  # 시장 전체
    "macro",   # 매크로 지표
    "theme",   # 사이클·서사
]

CONTENT_TYPES = [
    "fact",      # 검증된 사실 → 그대로 반영
    "data",      # 수치 데이터 → 그대로 반영
    "analysis",  # 공식 분석 → 출처 명시 후 반영
    "opinion",   # 개인 의견 → 교차검증 후 반영
]

SOURCE_TRUST = {
    "A": "증권사 공식 리포트",
    "B": "텔레그램 유료 채널",
    "C": "텔레그램 일반 채널",
    "D": "뉴스·블로그",
    "E": "소셜·미확인",
}

VALIDITY_TYPES = [
    "event",      # 특정 이벤트 기반 만료
    "date",       # 날짜 기반 만료
    "permanent",  # 계속 유효
]

MAGNITUDE_TYPES = ["major", "minor"]

SECTOR_LIST = [
    "반도체", "조선", "로봇", "방산", "바이오",
    "전력", "2차전지", "자동차", "통신", "AI소프트웨어",
    "우주", "소비내수", "미용", "LNG", "신재생", "기타"
]

SOURCE_TRUST_BY_PATH = {
    "wisereport": "A",
    "report": "A",
    "신한": "B",
    "태린이": "B",
    "crawling_bot": "B",
    "telegram": "C",
    "news": "D",
    "blog": "D",
    "market": "D",
}
