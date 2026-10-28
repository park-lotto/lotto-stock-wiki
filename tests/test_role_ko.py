"""관제 215 — 고객 2단계 칸 이름이 영어로 새지 않는다(2026-10-15 라이브 1353판 실측 칸 이름 전부)."""
from shopping_shorts import storyboard as sb

LIVE_SLOTS = ("hook pain reveal feature escalation twist benefit closing bait escalation_2 cta escalation_1 title fame more land "
              "mistake problem method result situation react story escalate solve how limit what good price origin targets spread "
              "scale proof mechanism ease power easy extra steps texture usage witness authority reason context spec bonus source "
              "fit deal howto vs notice ask regret feature_2 cases free feature_1").split()


def test_live_slots_all_korean():
    missing = [s for s in LIVE_SLOTS if not sb.role_ko(s)]
    assert not missing, missing


def test_arc_rank_names_korean():
    names = {k.rstrip("_") for keys, _ in sb.ARC_RANK for k in keys}
    missing = sorted(n for n in names if not sb.role_ko(n))
    assert not missing, missing
