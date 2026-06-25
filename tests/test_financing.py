from home_decision_ai.models.financing import classify_price


def test_classify_price_comfortable() -> None:
    band = classify_price(920_000_000)

    assert band.id == "comfortable"


def test_classify_price_stretch() -> None:
    band = classify_price(1_045_000_000)

    assert band.id == "stretch"


def test_classify_price_over_budget() -> None:
    band = classify_price(1_700_000_000)

    assert band.id == "over_budget"
