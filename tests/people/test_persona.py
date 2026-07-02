from pipeline.people.persona import decide_verdict


def test_verdict_toppick_leading_and_vacuum():
    assert decide_verdict(leading=True, vac=True, up_ok=False) == "탑픽 후보"
    assert decide_verdict(leading=True, vac=False, up_ok=True) == "탑픽 후보"


def test_verdict_interest_leading_only():
    assert decide_verdict(leading=True, vac=False, up_ok=False).startswith("관심")


def test_verdict_watch_vacuum_consensus_no_lead():
    assert decide_verdict(leading=False, vac=True, up_ok=True).startswith("관망")


def test_verdict_out_of_scope():
    assert decide_verdict(leading=False, vac=False, up_ok=False).startswith("그의 기준 밖")
    assert decide_verdict(leading=False, vac=True, up_ok=False).startswith("그의 기준 밖")
