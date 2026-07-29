"""채널별 '쇼핑 소재 적합도' 계산 (2026-07-29).

왜: 유튜브 랭킹에 연예·이슈 클립 채널이 섞여 들어와 짜깁기 쇼핑쇼츠 소재를 못 찾는다.
실측(2026-07-29): 채널 715개 중 285개는 홈템·레시피·가전만 내고, 164개는 전부 '기타'.
사람이 지울 채널을 고를 수 있게 이 비율을 관리 보드에 보여준다.

뷰티를 분자에서 뺀 이유: 메이크업 실촬영은 짜깁기 소재로 쓰지 않는다(설계 확정).
"""

GOOD_CATEGORIES = {"홈템", "레시피", "가전"}


def channel_fitness(items):
    """랭킹 items → {채널명: {total, good, other, fitness}}.

    items는 last_run 캐시의 항목 형식(name/username/category 키를 가짐)을 그대로 받는다.
    """
    acc = {}
    for it in items:
        ch = it.get("name") or it.get("username") or "?"
        cat = it.get("category")
        row = acc.setdefault(ch, {"total": 0, "good": 0, "other": 0})
        row["total"] += 1
        if cat in GOOD_CATEGORIES:
            row["good"] += 1
        if cat == "기타":
            row["other"] += 1
    for row in acc.values():
        row["fitness"] = row["good"] / row["total"] if row["total"] else 0.0
    return acc
