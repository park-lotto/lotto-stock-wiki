"""회사 운영실에서 사용하는 고정 카탈로그."""

COMPANIES = [
    {
        "id": "makers",
        "name": "메이커스랩",
        "subtitle": "AI 프로그램을 만들고 운영하는 회사",
        "products": [
            {"name": "숏템메이커", "status": "고객 운영·보완 중"},
            {"name": "추가 쇼츠 자동화 프로그램", "status": "개발 중"},
            {"name": "인스타 카드뉴스 자동화 프로그램", "status": "개발 중"},
            {"name": "블로그 자동화 프로그램", "status": "개발 중"},
        ],
        "revenue": [
            "— 프로그램 판매: 대표 설명이며 매출·수익 확정 사실이 아님(회계 미연결)",
            "— 운영 구조: 설치·컨설팅 계획, 매출 데이터 미연결",
        ],
    },
    {
        "id": "hnl",
        "name": "에이치엔엘글로벌",
        "subtitle": "중고폰 수출을 오프라인 중심으로 운영하는 직원 2명 회사",
        "products": [
            {"name": "중고폰 수출", "status": "오프라인 운영·직원 2명"},
            {"name": "기관물량연결", "status": "계획"},
            {"name": "폐폰 수익화", "status": "계획"},
            {"name": "재고관리", "status": "계획"},
        ],
        "revenue": [
            "— 사업 세부회계 미연결",
            "— 플랫폼·재고관리 과금 계획, 방식 미정",
        ],
    },
    {
        "id": "stock",
        "name": "스탁브레인",
        "subtitle": "시장 자료를 인사이트로 연결하는 회사",
        "products": [
            {"name": "섹터맵", "status": "개발 중·미출시"},
            {"name": "인사이트", "status": "개발 중·미출시"},
        ],
        "revenue": ["— 수익모델 미확정·출시전, 매출 데이터 미연결"],
    },
]

TEAMS = [
    {"id": "new", "name": "신규개발팀", "description": "승인된 신규 제품 개발과 시제품 검증"},
    {"id": "improve", "name": "제품개선팀", "description": "기존 제품의 UI·기능·템플릿 개선"},
    {"id": "cs", "name": "CS팀", "description": "문의 분류와 고객 불편 처리 추적"},
    {"id": "ops", "name": "서비스운영팀", "description": "고객 작업 실패와 서비스 장애 관찰"},
    {"id": "qa", "name": "품질검증팀", "description": "변경사항과 실제 사용 결과 검증"},
]

ROLES = [
    {"id": "astra", "name": "Astra", "group": "planning", "role": "기획 책임", "status": "계획 책임 미연결"},
    {"id": "claude", "name": "Claude", "group": "planning", "role": "기획 책임", "status": "계획 책임 미연결"},
    {"id": "opus", "name": "Opus", "group": "execution", "role": "실행 리더", "status": "실행 리더 미연결"},
    {"id": "codex", "name": "Codex", "group": "execution", "role": "실행 리더", "status": "실행 리더 미연결"},
]

STAGE_DEFINITIONS = [
    {"id": "intake", "label": "접수"},
    {"id": "design", "label": "설계"},
    {"id": "build", "label": "구현"},
    {"id": "verify", "label": "검증"},
    {"id": "done", "label": "완료"},
]
STAGE_IDS = tuple(stage["id"] for stage in STAGE_DEFINITIONS)

INTEGRATIONS = [
    {"id": "ai-execution", "name": "AI 실행", "status": "미연결"},
    {"id": "accounting", "name": "회계", "status": "미연결"},
]

COMPANY_IDS = {item["id"] for item in COMPANIES}
TEAM_IDS = {item["id"] for item in TEAMS}
